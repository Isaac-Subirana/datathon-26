"""Com bé indica el nom de l'arxiu, aquest agent ha estat dissenyat amb l'ajuda d'Opencode 
(fent servir l'agent Gemma, proporcionat gràcies a Helmcode); basant-nos en part en la nostra idea original
(que podeu trobar a agent.py -l'altra solució lliurada-), que era comprar potència de la xarxa les hores on
l'energia proveïda era més verda, més barata que un llindar, o en hores vall observades, i lliurar-ne al campus 
en les hores on l'energia de la xarxa era més bruta, més cara que un llindar, o en hores punta observades."""

import numpy as np
from math import sqrt

class BatteryAgent:
    def __init__(self) -> None:
        """
        Inicialització de l'agent.
        S'executa una sola vegada a l'inici del període d'avaluació.
        Permet carregar models predictius o definir llindars d'operació.
        """
        self.potencia_nominal_kw = 500.0
        self.soc_kwh_max = 2000.0
        self.rendiment = sqrt(0.90)
        
        self.historial_soc: list[float] = []
        self.historial_consignes: list[float] = []

    def act(self, obs: dict) -> float:
        """
        Retorna la consigna de potència activa de la bateria basant-se en la previsió de 24 hores.
        
        L'objectiu és minimitzar les emissions de CO2 (que compten un 70% cap a l'score) i el cost (que compta un 30%)
        basant-nos en la desviació del score actual respecte
        a la mitjana de la finestra de previsió.
        """
        preu_actual = obs["preu_actual"]
        co2_actual = obs["co2_actual"]
        preus_properes_24h = obs["preus_properes_24h"]
        co2_properes_24h = obs["co2_properes_24h"]
        soc_kwh = obs["soc_kwh"]
        self.historial_soc.append(soc_kwh)

        # 2. Construcció de la finestra de dades (actual + previsió de 24 hores)
        # Fem servir numpy per a càlculs vectoritzats i eficients
        preus = np.array([preu_actual] + preus_properes_24h)
        co2s = np.array([co2_actual] + co2_properes_24h)

        # 3. Normalització i càlcul de "scores" de desitjabilitat
        # Un score baix indica bon moment per carregar (preu baix, CO2 baix)
        # Un score alt indica bon moment per descarregar (preu alt, CO2 alt)
        
        def normalitza(arr):
            diff = np.max(arr) - np.min(arr)
            return (arr - np.min(arr)) / diff

        norm_preus = normalitza(preus)
        norm_co2s = normalitza(co2s)

        # Score combinat: 70% de pes a la reducció de CO2 i 30% a la reducció de cost
        scores = 0.7 * norm_co2s + 0.3 * norm_preus
        
        s_now = scores[0]
        s_avg = np.mean(scores)
        s_min = np.min(scores)
        s_max = np.max(scores)

        # 4. Decisió de la potència (Heurística de desviació de la mitjana)
        # En lloc de retornar valors fixes (+500, -500, 0), calculem una potència
        # concreta que sigui proporcional a la "qualitat" de l'oportunitat.
        consigna = 0.0
        
        if s_now < s_avg:
            # Oportunitat de càrrega: el score actual és millor (baix) que la mitjana del període
            # La potència de càrrega augmenta proporcionalment a la diferència amb la mitjana.
            denom = s_avg - s_min
            if denom > 1e-9:
                # Si s_now == s_min, la potència serà el màxim (500 kW)
                # Si s_now == s_avg, la potència serà 0 kW
                consigna = 500.0 * (s_avg - s_now) / denom
            else:
                consigna = 0.0
        elif s_now > s_avg:
            # Oportunitat de descàrrega: el score actual és pitjor (alt) que la mitjana
            # La potència de descàrrega augmenta proporcionalment a la diferència amb la mitjana.
            denom = s_max - s_avg
            if denom > 1e-9:
                # Si s_now == s_max, la potència serà el màxim (-500 kW)
                # Si s_now == s_avg, la potència serà 0 kW
                consigna = -500.0 * (s_now - s_avg) / denom
            else:
                consigna = 0.0
        else:
            consigna = 0.0

        # 5. Clamping de seguretat física (Limitar per SOC i Potència màxima)
        # Evitem infraccions tècniques que resten punts de la puntuació oficial.
        
        # Limites de potència per no superar els límits de la bateria [0, 2000 kWh]
        # Segons la dinàmica: SOC_{t+1} = SOC_t + P_t * dt * eta_c (per a P_t >= 0)
        max_p_charge = min(self.potencia_nominal_kw, (self.soc_kwh_max - soc_kwh) / self.rendiment)
        
        # Segons la dinàmica: SOC_{t+1} = SOC_t + (P_t * dt) / eta_d (per a P_t < 0)
        # Per assegurar SOC_{t+1} >= 0, necessitem P_t >= -soc_kwh * eta_d
        max_p_discharge_mag = min(self.potencia_nominal_kw, soc_kwh * self.rendiment)
        
        if consigna > 0:
            consigna = min(consigna, max_p_charge)
        elif consigna < 0:
            consigna = max(consigna, -max_p_discharge_mag)
            
        self.historial_consignes.append(consigna)
        return float(consigna)
