# Optimització de la Bateria del Campus — Datathon FME, UPC Sostenible

## Descripció del projecte

Aquest projecte, proposat per [UPC Sostenible](https://sostenible.upc.edu), s'ha desenvolupat en el marc de la **Datathon FME 2026**,UPC Sostenible**, dins del repte _Optimització de la Bateria del Campus_.

L'objectiu és desenvolupar una estratègia intel·ligent de gestió d'una bateria d'emmagatzematge energètic del campus universitari, decidint quan carregar-la i quan descarregar-la per optimitzar el CO<sub>2</sub> necessari per a produir l'electricitat, alhora que s'optimitza el cost econòmic.

## El repte

Hem disposat de dades horàries del campus i la xarxa elèctrica de l'any anterior, que trobareu a `data/train`:

- Consum elèctric (`contador.csv`).
- Producció d'energia solar fotovoltaica (`inversor.csv`).
- Preu de l'electricitat (`precio_pvpc.csv`).
- Emissions de CO₂ (`co2_red.csv`).

També disposem de les especificacions tècniques de la bateria, que determinen la seva capacitat, potència màxima, eficiència i límits de càrrega.

A partir d'aquestes dades, hem de prendre decisions horàries sobre la càrrega i descàrrega de la bateria, respectant sempre les seves limitacions físiques.

## La nostra solució

Hem desenvolupat dos agents que decideixen com gestionar la bateria a cada pas de la simulació.

Els agents reben informació sobre l'estat actual del sistema i les previsions disponibles, i retornen la potència de càrrega o descàrrega que s'hauria de dur a terme a la bateria per optimitzar-ne l'ús.

Les nostres dues estratègies tenen en compte els següents factors:

- El preu actual de l'electricitat.
- Les previsions de preus de les properes 24 hores.
- La petjada de carboni de l'electricitat consumida.
- Les previsions de petjada de carboni de l'electricitat consumida en les properes 24 hores.
- L'estat de càrrega de la bateria (SOC).
- Les hores vall i punta mitjanes observades als mesos anteriors donats a la carpeta `data/train`, així com els preus i petjades de CO<sub>2</sub> mitjanes. Podreu visualitzar dashboards gràfics que mostren les dades donades a `data/dashboard.py`, `starter_kit/co2_grafic.py` i `starter_kit/dashboard*.py`, creats mitjançant Streamlit.

L'objectiu és trobar una estratègia que permeti aprofitar millor l'energia disponible i reduir l'impacte econòmic i ambiental.

Podreu trobar les nostres dues solucions a `src/agent.py` i `src/agent-opencode.py`.
