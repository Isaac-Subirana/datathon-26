"""
agent.py
Plantilla oficial de l'agent de control per al repte de la bateria de UPC Sostenible.
Datathon 2026.
"""

class BatteryAgent:
    def __init__(self):
        """Inicialització de l'agent.
        S'executa una sola vegada a l'inici del període d'avaluació.
        Permet carregar models predictius o definir llindars d'operació.
        """
        # Paràmetres d'operació de la política de referència
        self.llindar_preu_carrega = [0.08]      # €/kWh
        self.llindar_preu_descarrega = [0.16]   # €/kWh
        self.llindar_co2_xarxa = [0.0]          # kg CO2/kWh
        self.potencia_nominal_kw = 500.0        # Potència màxima de l'inversor (kW)

        self.hores_vall = [                         # llista de hores vall del preu per cada mes
            list(range(1, 6 + 1)), # gener
            list(range(0, 2 + 1)).extend(list(range(4, 6 + 1))), # febrer
            list(range(2, 4 + 1)).extend(list(range(14, 16 + 1))), # març
            [4, 9].extend(list(range(14, 17 + 1))),                # abril
            [9].extend(list(range(13, 17 + 1))),   # maig
            [9].extend(list(range(13, 17 + 1))),   # juny
            [9].extend(list(range(13, 17 + 1))),   # juliol
            list(range(11, 16 + 1)),   # agost
            list(range(12, 17 + 1)), #setembre
            list(range(3, 4 + 1)).extend(list(range(14, 17 + 1))), # octubre
            list(range(2, 5 + 1)).extend(list(range(14, 15 + 1))), # novembre
            list(range(1, 5 + 1)).extend([14]) # desembre
            ]       

        self.hores_punta = [                         # llista de hores punta del preu per cada mes
            list(range(10, 11 + 1)).extend(list(range(18, 21 + 1))), # gener
            [10, 13].extend(list(range(18, 21 + 1))), # febrer
            list(range(18, 23 + 1)), # març
            [8].extend(list(range(19, 23 + 1))),    # abril
            [7].extend(list(range(19, 23 + 1))),   # maig
            [7].extend(list(range(19, 23 + 1))),   # juny
            [7].extend(list(range(19, 23 + 1))),   # juliol
            [7].extend(list(range(19, 23 + 1))),   # agost
            [8].extend(list(range(19, 23 + 1))),   # setembre
            [8, 10].extend(list(range(18, 21 + 1))),   # octubre
            [8].extend(list(range(18, 22 + 1))), # novembre
            list(range(10, 11 + 1)).extend(list(range([18, 21 + 1]))) # desembre
            ]

        self.historial = []

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
        hora = obs["hour"]
        mes = extreu_mes(obs[timestamp]) - 1 # perquè volem l'índex de la llista
        preu = obs["preu_actual"]
        co2 = obs["co2_actual"]
        soc = obs["soc_pct"]
        soc_kwh = obs["soc_kwh"]
        soc_percentatge = soc * 100
        
        consigna = 0.0
        
        
        # canvia la consigna segons certes condicions
        if co2 < self.llindar_co2[mes] or (preu < self.llindar_preu_carrega[mes] and hora in self.hores_vall[mes]):
            

        return assegura_resultat(consigna, soc_kwh, 2000.0, 500.0, -500.0)

    def extreu_mes(timestamp: str) -> int:
        """Donada una timestamp en format YYYY-MM-DD hh:mm:ss, retorna el mes expressat per el timestamp."""
        timestamp_en_llista = timestamp.split("-")
        return int(timestamp_en_llista[1])

    def assegura_resultat(consigna: float, soc_kwh:float, soc_kwh_max: float, pot_màx: float, pot_mín: float) -> float:
        """Donada una possible operació hi opera un safety check, asegurant-se que no es restin punts per violació dels límits o clipping."""
        from math import sqrt

        # Clamping de seguretat física per evitar infraccions de retallada (clipping): [part de l'agent original]
        rendiment = round(sqrt(90), 10)
        max_carrega = min(self.potencia_nominal_kw, (soc_kwh_max - soc_kwh) / rendiment)
        max_descarrega = min(self.potencia_nominal_kw, soc_kwh * rendiment)

        consigna = float(max(-max_descarrega, min(max_carrega, consigna)))

        # Considerarem que el valor de sortida és 'sortida'. 
        # Safety check: ens assegurem que no es restin punts per violació dels límits.
        if consigna > pot_màx:
            return pot_màx
        elif consigna < pot_mín:
            return pot_mín
        else:
            return consigna