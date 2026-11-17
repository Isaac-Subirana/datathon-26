"""Com bé indica el nom de l'arxiu, aquest agent ha estat dissenyat amb l'ajuda d'Opencode
(fent servir l'agent Gemma, cortesia de Helmcode); basant-nos en part en la nostra idea original
(que podeu trobar a agent.py -l'altra solució lliurada-), que era comprar potència de la xarxa les hores on
l'energia proveïda era més verda, més barata que un llindar, o en hores vall observades prèviament, i lliurar-ne al campus
en les hores on l'energia de la xarxa era més bruta, més cara que un llindar, o en hores punta observades.

La idea principal del codi és retornar un valor dinàmic entre -500 i 500 en funció de la puntuació de desitjibilitat,
que evaluem segons la mitjana de les dades previstes durant les següents 24 hores, comptant el pes del 70% del CO2 i
el pes del 30% del factor econòmic.
"""

import numpy as np
from math import sqrt

class BatteryAgent:
    def __init__(self) -> None:
        """
        Inicialització de l'agent.
        S'executa una sola vegada a l'inici del període d'avaluació.
        """
        self.potencia_nominal_kw = 500.0
        self.soc_kwh_max = 2000.0
        self.rendiment = sqrt(0.90)

    def act(self, obs: dict) -> float:
        """
       Determina la consigna de potència activa de la bateria per a l'hora actual.

        Paràmetres:
        -----------
        obs : diccionari amb les variables d'estat disponibles a l'hora actual:
            - "timestamp": pd.Timestamp amb la data i hora d'avaluació.
            - "hour": int de 0 a 23 (hora del dia).
            - "day_of_week": int de 0 (dilluns) a 6 (diumenge).
            - "soc_kwh": float amb l'energia emmagatzemada actual (0.0 a 2.000.0 kWh).
            - "soc_pct": float amb l'estat de càrrega relatiu [0.0, 1.0].
            - "preu_actual": float amb el preu del PVPC d'aquesta hora (€/kWh).
            - "co2_actual": float amb la intensitat de CO2 peninsular (kg CO2/kWh).
            - "preus_properes_24h": llista de preus horaris de les properes 24 hores (€/kWh).
            - "co2_properes_24h": llista de factors d'emissió de CO2 de les properes 24 hores (kg/kWh).
            - "noves_dades_5min": dades mesurades pels sensors en la darrera hora transcorreguda.

        Retorna:
        --------
        float : Consigna de potència activa en kW:
            > 0  -> Càrrega d'energia des de la xarxa interna (fins a +500.0 kW).
            < 0  -> Descàrrega d'energia cap al campus (fins a -500.0 kW).
            = 0  -> Bateria en mode d'espera (0.0 kW).

        L'objectiu és minimitzar les emissions de CO2 (que compten un 70% cap a l'score) i el cost (que compta un 30%)
        basant-nos en la desviació de la puntuació actual respecte a la mitjana de la finestra de previsió.
        """

        preu_actual = obs["preu_actual"]
        co2_actual = obs["co2_actual"]
        preus_properes_24h = obs["preus_properes_24h"]
        co2_properes_24h = obs["co2_properes_24h"]
        soc_kwh = obs["soc_kwh"]

        # Creem la finestra de dades (actual + previsió de 24 hores)
        preus = np.array([preu_actual] + preus_properes_24h)
        co2s = np.array([co2_actual] + co2_properes_24h)

        # Normalitzem i calculem la puntuació de desitjabilitat
        # Una puntuació baixa indica un bon moment per carregar (energia verda/preu baix)
        # Una puntuació alta indica un bon moment per descarregar (energia bruta/preu alt)

        def normalitza(arr):
            diff = np.max(arr) - np.min(arr)
            return (arr - np.min(arr)) / diff

        norm_preus = normalitza(preus)
        norm_co2s = normalitza(co2s)

        # La puntuació s'avalua donant un 70% de pes a la reducció de CO2 i un 30% a la reducció de cost
        scores = 0.7 * norm_co2s + 0.3 * norm_preus

        score_now = scores[0]
        score_avg = np.mean(scores)
        score_min = np.min(scores)
        score_max = np.max(scores)

        # En lloc de retornar una consigna estàtica, la multipliquem per la puntuació 
        # perquè s'adapti millor a la demanda futura
        consigna = 0.0

        if score_now < score_avg: # Si la puntuació actual és millor que la mitjana:
            denom = score_avg - score_min
            if denom > 1e-9:
                # Quan score_now == score_min, la potència serà el màxim (500 kW)
                # Quan score_now == score_avg, la potència serà 0 kW
                consigna = 500.0 * (score_avg - score_now) / denom
            else:
                consigna = 0.0
        elif score_now > score_avg: # Si la puntuació actual és pitjor que la mitjana:
            denom = score_max - score_avg
            if denom > 1e-9:
                # Quan score_now == score_max, la potència serà el màxim de descàrrega (-500 kW)
                # Quan score_now == score_avg, la potència serà 0 kW
                consigna = -500.0 * (score_now - score_avg) / denom
            else:
                consigna = 0.0
        else:
            consigna = 0.0

        # Ens assegurem que no cometem infraccions tècniques que restin punts.

        # Clamping de seguretat física per evitar infraccions de retallada (clipping): 
        # [part de la plantilla original, lleugerament modificada per el Gemma de l'Opencode]
        max_carrega = min(self.potencia_nominal_kw, (self.soc_kwh_max - soc_kwh) / self.rendiment)
        max_descarrega = min(self.potencia_nominal_kw, soc_kwh * self.rendiment)

        if consigna > 0:
            consigna = min(consigna, max_carrega)
        elif consigna < 0:
            consigna = max(consigna, -max_descarrega)
        
        return consigna
