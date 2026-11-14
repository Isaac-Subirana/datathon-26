"""
agent.py
Agent de control optimitzat (MPC 24h) per maximitzar l'estalvi de CO2
amb co-optimització econòmica. Datathon 2026 - UPC Sostenible.
"""

from math import sqrt
import numpy as np

try:
    from scipy.optimize import linprog
    SCIPY_DISPONIBLE = True
except ImportError:
    SCIPY_DISPONIBLE = False


class BatteryAgent:
    def __init__(self) -> None:
        """Inicialització de l'agent."""
        self.potencia_nominal_kw: float = 500.0
        self.soc_kwh_max: float = 2000.0
        self.rendiment_anada_tornada: float = 0.90
        self.rendiment: float = round(sqrt(self.rendiment_anada_tornada), 10)

        # Pes relatiu del preu (€/kWh) respecte al CO2 (kg CO2/kWh).
        # Valors baixos (0.05 - 0.15) prioritzen clarament el CO2 i usen el preu
        # per desempatar hores amb intensitat de carboni similar.
        self.pes_preu: float = 0.12

    def act(self, obs: dict) -> float:
        """Determina la consigna de potència activa (kW) per a l'hora actual."""
        soc_kwh = float(obs["soc_kwh"])
        co2_actual = float(obs["co2_actual"])
        preu_actual = float(obs["preu_actual"])

        co2_futur = [float(x) for x in obs.get("co2_properes_24h", [])]
        preu_futur = [float(x) for x in obs.get("preus_properes_24h", [])]

        # Construïm l'horitzó complet (hora actual + fins a 24 hores futures)
        h_futur = min(len(co2_futur), len(preu_futur))
        co2_seq = np.array([co2_actual] + co2_futur[:h_futur], dtype=float)
        preu_seq = np.array([preu_actual] + preu_futur[:h_futur], dtype=float)

        if SCIPY_DISPONIBLE and len(co2_seq) > 1:
            consigna = self._optimitza_mpc(soc_kwh, co2_seq, preu_seq)
        else:
            consigna = self._heuristica_dinamica(soc_kwh, co2_seq, preu_seq)

        return self._aplica_seguretat_fisica(consigna, soc_kwh)

    def _optimitza_mpc(
        self, soc_inicial: float, co2_seq: np.ndarray, preu_seq: np.ndarray
    ) -> float:
        """Resol el despatx òptim de les properes H hores mitjançant Programació Lineal."""
        H = len(co2_seq)
        eta = self.rendiment
        inv_eta = 1.0 / eta

        # Funció de cost combinada (prioritat CO2 + desempat econòmic)
        cost_horari = co2_seq + self.pes_preu * preu_seq

        # Variables de decisió (3*H):
        # [0 .. H-1]     -> p_carrega[t] >= 0
        # [H .. 2H-1]    -> p_descarrega[t] >= 0
        # [2H .. 3H-1]   -> soc[t] al final de l'hora t
        eps = 1e-6  # Evita càrrega i descàrrega simultànies
        c = np.zeros(3 * H)
        c[:H] = cost_horari + eps
        c[H : 2 * H] = -cost_horari + eps

        # Valor terminal de l'energia emmagatzemada al final de l'horitzó
        # per evitar buidar la bateria en hores poc favorables
        valor_terminal = float(np.percentile(cost_horari, 55)) * eta
        c[3 * H - 1] = -valor_terminal

        # Restriccions d'igualtat de balanç energètic:
        # soc[t] - soc[t-1] - eta * p_carrega[t] + (1/eta) * p_descarrega[t] = 0
        A_eq = np.zeros((H, 3 * H))
        b_eq = np.zeros(H)

        for t in range(H):
            A_eq[t, 2 * H + t] = 1.0
            A_eq[t, t] = -eta
            A_eq[t, H + t] = inv_eta
            if t == 0:
                b_eq[t] = soc_inicial
            else:
                A_eq[t, 2 * H + (t - 1)] = -1.0

        # Límits físics de potència i capacitat
        bounds = (
            [(0.0, self.potencia_nominal_kw)] * H
            + [(0.0, self.potencia_nominal_kw)] * H
            + [(0.0, self.soc_kwh_max)] * H
        )

        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if res.success:
            p_c0 = float(res.x[0])
            p_d0 = float(res.x[H])
            return p_c0 - p_d0

        return self._heuristica_dinamica(soc_inicial, co2_seq, preu_seq)

    def _heuristica_dinamica(
        self, soc_inicial: float, co2_seq: np.ndarray, preu_seq: np.ndarray
    ) -> float:
        """Alternativa sense dependències basada en quantils a 24h i rendiment."""
        cost_horari = co2_seq + self.pes_preu * preu_seq
        c_actual = cost_horari[0]

        llindar_carrega = float(np.percentile(cost_horari, 25))
        llindar_descarrega = float(np.percentile(cost_horari, 75))

        # Només operem si el marge supera les pèrdues del 10% d'anada i tornada
        if c_actual <= llindar_carrega and (llindar_descarrega > c_actual / self.rendiment_anada_tornada):
            return self.potencia_nominal_kw
        elif c_actual >= llindar_descarrega and (c_actual > llindar_carrega / self.rendiment_anada_tornada):
            return -self.potencia_nominal_kw

        return 0.0

    def _aplica_seguretat_fisica(self, consigna: float, soc_kwh: float) -> float:
        """Clamping estricte per garantir zero penalitzacions per clipping."""
        marge = 1e-4  # Petit marge de seguretat numèrica
        max_carrega = max(
            0.0,
            min(self.potencia_nominal_kw, (self.soc_kwh_max - soc_kwh) / self.rendiment - marge),
        )
        max_descarrega = max(
            0.0,
            min(self.potencia_nominal_kw, soc_kwh * self.rendiment - marge),
        )

        consigna_segura = float(max(-max_descarrega, min(max_carrega, consigna)))
        return max(-self.potencia_nominal_kw, min(self.potencia_nominal_kw, consigna_segura))