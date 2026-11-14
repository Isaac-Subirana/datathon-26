"""
agent.py
Agent de control òptim (MPC 24h amb Programació Lineal) per a la Datathon 2026 - UPC Sostenible.
Optimitzat per a: Score = max(0, 0.70 * ΔCO2(%) + 0.30 * ΔCost(%) - 0.20 * Infraccions)
"""

from math import sqrt
import numpy as np
import pandas as pd
from scipy.optimize import linprog


class BatteryAgent:
    def __init__(self) -> None:
        """Inicialització de l'agent i dels paràmetres físics i de normalització."""
        self.potencia_nominal_kw: float = 500.0
        self.soc_kwh_max: float = 2000.0
        self.rendiment_anada_tornada: float = 0.90
        self.rendiment: float = round(sqrt(self.rendiment_anada_tornada), 10)

        # Pesos exactes de la funció d'avaluació
        self.pes_co2: float = 0.70
        self.pes_cost: float = 0.30

        # Mitjanes mensuals de referència per normalitzar ΔCO2(%) i ΔCost(%) des de la primera hora
        self.ref_preu_mensual: list[float] = [
            0.1464, 0.1136, 0.1425, 0.1229, 0.1198, 0.1270,
            0.1599, 0.1653, 0.1331, 0.1454, 0.1333, 0.1467,
        ]
        self.ref_co2_mensual: list[float] = [
            0.08763, 0.05093, 0.06796, 0.06840, 0.07592, 0.07476,
            0.09645, 0.10407, 0.09517, 0.11387, 0.08897, 0.10278,
        ]

        # Acumuladors per adaptar les mitjanes a la distribució real del període avaluat
        self.suma_co2: float = 0.0
        self.suma_preu: float = 0.0
        self.hores_observades: int = 0

    def act(self, obs: dict) -> float:
        """Determina la consigna de potència activa (kW) per a l'hora actual."""
        soc_kwh = float(obs["soc_kwh"])
        co2_actual = float(obs["co2_actual"])
        preu_actual = float(obs["preu_actual"])
        mes = pd.to_datetime(obs["timestamp"]).month - 1

        # Actualitzem l'estadística històrica en línia
        self.suma_co2 += co2_actual
        self.suma_preu += preu_actual
        self.hores_observades += 1

        # Estimació robusta de les mitjanes globals (combinant prior mensual + dades observades)
        pes_prior = 48.0
        mitjana_co2 = (pes_prior * self.ref_co2_mensual[mes] + self.suma_co2) / (
            pes_prior + self.hores_observades
        )
        mitjana_preu = (pes_prior * self.ref_preu_mensual[mes] + self.suma_preu) / (
            pes_prior + self.hores_observades
        )

        # Seqüència completa: hora actual + properes 24 hores
        co2_futur = [float(x) for x in obs.get("co2_properes_24h", [])]
        preu_futur = [float(x) for x in obs.get("preus_properes_24h", [])]
        h_futur = min(len(co2_futur), len(preu_futur))

        co2_seq = np.array([co2_actual] + co2_futur[:h_futur], dtype=float)
        preu_seq = np.array([preu_actual] + preu_futur[:h_futur], dtype=float)

        # Funció de cost normalitzada que reflecteix exactament 0.70*ΔCO2(%) + 0.30*ΔCost(%)
        cost_normalitzat = (
            self.pes_co2 * (co2_seq / max(mitjana_co2, 1e-6))
            + self.pes_cost * (preu_seq / max(mitjana_preu, 1e-6))
        )

        consigna = self._resol_mpc(soc_kwh, cost_normalitzat)
        return self._aplica_seguretat_fisica(consigna, soc_kwh)

    def _resol_mpc(self, soc_inicial: float, cost_horari: np.ndarray) -> float:
        """Resol el despatx òptim sobre l'horitzó disponible mitjançant HiGHS (LP)."""
        H = len(cost_horari)
        if H <= 1:
            return 0.0

        eta = self.rendiment
        inv_eta = 1.0 / eta
        soc_segur = float(np.clip(soc_inicial, 0.0, self.soc_kwh_max))

        # Variables (3*H): [p_carrega (0..H-1), p_descarrega (H..2H-1), soc (2H..3H-1)]
        # Petit terme de regularització (1e-6) per evitar càrrega i descàrrega simultànies
        eps = 1e-6
        c = np.zeros(3 * H)
        c[:H] = cost_horari + eps
        c[H : 2 * H] = -cost_horari + eps

        # Valor de reserva per l'energia que queda a la bateria al final de les 24h
        valor_terminal = float(np.percentile(cost_horari, 60)) * eta
        c[3 * H - 1] = -valor_terminal

        # Balanç energètic horari: soc[t] - soc[t-1] - eta*p_c[t] + (1/eta)*p_d[t] = 0
        A_eq = np.zeros((H, 3 * H))
        b_eq = np.zeros(H)

        for t in range(H):
            A_eq[t, 2 * H + t] = 1.0
            A_eq[t, t] = -eta
            A_eq[t, H + t] = inv_eta
            if t == 0:
                b_eq[t] = soc_segur
            else:
                A_eq[t, 2 * H + (t - 1)] = -1.0

        # Marge de seguretat intern per evitar qualsevol infracció numèrica
        marge_soc = 1e-3
        bounds = (
            [(0.0, self.potencia_nominal_kw)] * H
            + [(0.0, self.potencia_nominal_kw)] * H
            + [(marge_soc, self.soc_kwh_max - marge_soc)] * H
        )

        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if res.success:
            return float(res.x[0] - res.x[H])
        return 0.0

    def _aplica_seguretat_fisica(self, consigna: float, soc_kwh: float) -> float:
        """Garanteix estrictament 0 infraccions de potència o de clipping de capacitat."""
        marge = 1e-3
        max_carrega = max(
            0.0,
            min(
                self.potencia_nominal_kw,
                (self.soc_kwh_max - soc_kwh) / self.rendiment - marge,
            ),
        )
        max_descarrega = max(
            0.0,
            min(
                self.potencia_nominal_kw,
                soc_kwh * self.rendiment - marge,
            ),
        )

        consigna_segura = float(max(-max_descarrega, min(max_carrega, consigna)))
        return max(-self.potencia_nominal_kw, min(self.potencia_nominal_kw, consigna_segura))