# Carrega la Bateria! — Datathon UPC Sostenible

## Descripció del projecte

Aquest projecte s'ha desenvolupat en el marc de la **Datathon UPC Sostenible**, dins del repte *Carrega la Bateria!*.

L'objectiu és desenvolupar una estratègia intel·ligent de gestió d'una bateria d'emmagatzematge energètic del campus universitari, decidint quan carregar-la i quan descarregar-la per optimitzar el consum elèctric.

La nostra solució busca aconseguir un equilibri entre dos objectius principals:

- **Reduir el cost econòmic** de l'electricitat consumida.
- **Reduir les emissions de CO₂** associades al consum energètic.

## El repte

Disposem de dades horàries del campus, com ara:

- Consum elèctric (`load_kw`).
- Producció d'energia solar fotovoltaica (`pv_kw`).
- Preu de l'electricitat (`precio_eur_per_kwh`).
- Intensitat de les emissions de CO₂ (`co2_kg_per_kwh`).

També disposem de les especificacions tècniques de la bateria, que determinen la seva capacitat, potència màxima, eficiència i límits de càrrega.

A partir d'aquestes dades, hem de prendre decisions horàries sobre la càrrega i descàrrega de la bateria, respectant sempre les seves limitacions físiques.

## La nostra solució

Hem desenvolupat dos agents que decideixen com gestionar la bateria a cada pas de la simulació.

Els agents reben informació sobre l'estat actual del sistema i les previsions disponibles, i retornen la potència de càrrega o descàrrega que s'hauria de dur a terme a la bateria.

Les nostres dues estratègies tenen en compte els següents factors:

- El preu actual de l'electricitat.
- Les previsions de preus de les properes hores.
- La petjada de carboni de l'electricitat consumida.
- Les previsions de petjades de carboni de l'electricitat consumida en les properes hores.
- L'estat de càrrega de la bateria (SOC).
- Les hores vall i punta mitjanes observades als mesos anteriors donats a la carpeta `data/train`, així com els preus i petjades de CO2 mitjanes. Podreu visualitzar dashboards gràfics que mostren les dades donades a `data/dashboard.py`, `starter_kit/co2_grafic.py` i `starter_kit/dashboard*.py`, creats mitjançant Streamlit.

L'objectiu és trobar una estratègia que permeti aprofitar millor l'energia disponible i reduir l'impacte econòmic i ambiental.

Podreu trobar les nostres dues solucions a `src/agent.py` i `src/agent-opencode.py`.
