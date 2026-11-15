"""
agent.py
Iteració sobre la plantilla oficial de l'agent de control per al repte de la bateria de UPC Sostenible.
Datathon 2026.

La idea principal del codi és aprofitar les dades d'entrenament proporcionades per trobar, per a cada mes, el preu
mitjà, el co2 mitjà generat per les centrals i les hores vall i hores punta.

Llavors, definim un llindar de preus per carregar/descarregar i un llindar de co2 generat per les centrals "tolerable".

Amb aquestes dades, l'algoritme valora si aquella hora val la pena o no carregar o descarregar la bateria, i evalua com quant
val la pena carregar/descarregar.

"""

class BatteryAgent:
    def __init__(self) -> None:
        """Inicialització de l'agent.
        S'executa una sola vegada a l'inici del període d'avaluació.
        Permet carregar models predictius o definir llindars d'operació.
        """

        from math import sqrt

        # Paràmetres d'operació de la política de referència
        self.preu: list[float] = [  # €/kWh
            0.1464,
            0.1136,
            0.1425,
            0.1229,
            0.1198,
            0.1270,
            0.1599,
            0.1653,
            0.1331,
            0.1454,
            0.1333,
            0.1467
        ]     
        self.co2_xarxa: list[float] = [  # kg CO2/kWh
            0.08763,
            0.05093,
            0.06796,          
            0.06840,
            0.07592,
            0.07476,
            0.09645,
            0.10407,
            0.09517,
            0.11387,
            0.08897,
            0.10278
        ]               

        # Els llindars de preus i co2 són força arbitraris però creiem que poden funcionar.
        self.llindar_preu_carrega: list[float] = [c - min(self.preu) / 2 for c in self.preu]
        self.llindar_preu_descarrega: list[float] = [c + max(self.preu) / 2 for c in self.preu]

        self.llindar_co2_verd_xarxa: list[float] = [c - 0.01 for c in self.co2_xarxa]
        self.llindar_co2_brut_xarxa: list[float] = [c + 0.02 for c in self.co2_xarxa]


        self.hores_vall = [                         # llista de hores vall del preu per cada mes
            list(range(1, 6 + 1)),                           # gener
            list(range(0, 2 + 1)) + list(range(4, 6 + 1)),   # febrer
            list(range(2, 4 + 1)) + list(range(14, 16 + 1)), # març
            [4, 9] + list(range(14, 17 + 1)),                # abril
            [9] + list(range(13, 17 + 1)),                   # maig
            [9] + list(range(13, 17 + 1)),                   # juny
            [9] + list(range(13, 17 + 1)),                   # juliol
            list(range(11, 16 + 1)),                         # agost
            list(range(12, 17 + 1)),                         # setembre
            list(range(3, 4 + 1)) + list(range(14, 17 + 1)), # octubre
            list(range(2, 5 + 1)) + list(range(14, 15 + 1)), # novembre
            list(range(1, 5 + 1)) + [14] # desembre
            ]       

        self.hores_punta = [                         # llista de hores punta del preu per cada mes
            list(range(10, 11 + 1)) + list(range(18, 21 + 1)), # gener
            [10, 13] + list(range(18, 21 + 1)),                # febrer
            list(range(18, 23 + 1)),                           # març
            [8] + list(range(19, 23 + 1)),                     # abril
            [7] + list(range(19, 23 + 1)),                     # maig
            [7] + list(range(19, 23 + 1)),                     # juny
            [7] + list(range(19, 23 + 1)),                     # juliol
            [7] + list(range(19, 23 + 1)),                     # agost
            [8] + list(range(19, 23 + 1)),                     # setembre
            [8, 10] + list(range(18, 21 + 1)),                 # octubre
            [8] + list(range(18, 22 + 1)),                     # novembre
            [10, 11] + list(range(18, 21 + 1))                 # desembre
            ]


        self.potencia_nominal_kw = 500.0        # Potència màxima de l'inversor (kW)
        self.rendiment = round(sqrt(0.9), 10)

    def act(self, obs: dict) -> float:
        """Determina la consigna de potència activa de la bateria per a l'hora actual.

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
        """
        
        from pandas import to_datetime
        
        hora = obs["hour"]
        mes = to_datetime(obs["timestamp"]).month - 1
        preu = obs["preu_actual"]
        co2 = obs["co2_actual"]
        soc = obs["soc_pct"]
        soc_kwh = obs["soc_kwh"]
        soc_kwh_max = 2000
        soc_percentatge = soc * 100
        
        consigna = 0.0
        
        
        # canvia la consigna segons certes condicions
        if co2 < self.llindar_co2_verd_xarxa[mes] or preu < self.llindar_preu_carrega[mes] or hora in self.hores_vall[mes]:
            # si la electricitat consumida és prou verda o el preu és molt barat, carreguem la bateria
            consigna = 500

        elif co2 > self.llindar_co2_brut_xarxa[mes] or preu > self.llindar_preu_descarrega[mes] or hora in self.hores_punta[mes]: 
            # si la electricitat consumida és força contaminant o el preu és molt car descarreguem la bateria
            consigna = -500
        
        # Si la electricitat consumida no és cap de les dues coses, no fem res



        # Clamping de seguretat física per evitar infraccions de retallada (clipping): 
        # [part de la plantilla original, lleugerament modificada per el Gemma de l'Opencode]
        max_carrega = min(self.potencia_nominal_kw, (soc_kwh_max - soc_kwh) / self.rendiment)
        max_descarrega = min(self.potencia_nominal_kw, soc_kwh * self.rendiment)

        if consigna > 0:
            consigna = min(consigna, max_carrega)
        elif consigna < 0:
            consigna = max(consigna, -max_descarrega)
        
        return consigna