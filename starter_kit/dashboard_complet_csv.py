"""
dashboard_csv.py - Explorador amb una pestanya per cada CSV.
Poseu-lo a starter_kit/ (o a qualsevol carpeta amb ../data/train).
Execució:  streamlit run dashboard_csv.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

AQUI = Path(__file__).parent

FITXERS = {
    "Comptador": "contador.csv",
    "Inversors": "inversor.csv",
    "Meteo": "meteo.csv",
    "Entrades/Sortides": "entradas_salidas.csv",
    "Preu PVPC": "precio_pvpc.csv",
    "CO2 xarxa": "co2_red.csv",
}
DESCRIPCIO = {
    "Comptador": "Comptador fiscal del campus (5 min). Potència exportada negativa = importació de la xarxa.",
    "Inversors": "Telemetria dels 3 inversors fotovoltaics (5 min).",
    "Meteo": "Estació meteorològica: irradiància, temperatures, vent (5 min).",
    "Entrades/Sortides": "Senyals digitals marxa/aturada de càrregues auxiliars.",
    "Preu PVPC": "Preu del mercat regulat (horari, EUR/kWh).",
    "CO2 xarxa": "Factor d'emissió del mix elèctric (horari, kg CO2/kWh).",
}
OPCIONS_REMOSTREIG = {
    "Original": None,
    "1 hora": "1h",
    "1 dia": "1D",
    "1 setmana": "1W",
    "1 mes": "MS",
}

st.set_page_config(page_title="Explorador de CSV", layout="wide")
st.title("Explorador de dades - un CSV per pestanya")


def trobar_dades():
    for p in [AQUI / "../data/train", AQUI / "data/train", AQUI / "data", AQUI]:
        if (p / "contador.csv").exists() or (p / "precio_pvpc.csv").exists():
            return p
    return None


@st.cache_data(show_spinner="Carregant fitxer...")
def carregar(ruta: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["Fecha"])
    return df.set_index("Fecha").sort_index()


data_dir = trobar_dades()
if data_dir is None:
    st.error("No trobo la carpeta data/train. Poseu els CSV a ../data/train o a data/train.")
    st.stop()

# ---------------------------------------------------------------- barra lateral
st.sidebar.header("Filtres globals")
st.sidebar.caption(f"Carpeta de dades: {Path(data_dir).resolve()}")
remostreig = st.sidebar.selectbox("Agrupar el gràfic per", list(OPCIONS_REMOSTREIG), index=1)
funcio = st.sidebar.selectbox("Funció d'agrupació", ["mean", "max", "min", "sum"])

tabs = st.tabs(list(FITXERS))

for tab, (nom, fitxer) in zip(tabs, FITXERS.items()):
    with tab:
        ruta = Path(data_dir) / fitxer
        st.subheader(nom)
        st.caption(f"`{fitxer}` - {DESCRIPCIO[nom]}")

        if not ruta.exists():
            st.warning(f"No trobo {fitxer} a {data_dir}.")
            continue

        df = carregar(str(ruta))
        num = df.select_dtypes("number")

        # ---- info bàsica
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Files", f"{len(df):,}".replace(",", "."))
        c2.metric("Columnes", df.shape[1])
        c3.metric("Inici", str(df.index.min())[:16])
        c4.metric("Final", str(df.index.max())[:16])

        if len(df) > 2:
            pas = df.index.to_series().diff().mode().iloc[0]
            st.write(f"Freqüència habitual: **{pas}**")

        # ---- interval de dates
        dmin, dmax = df.index.min().date(), df.index.max().date()
        rang = st.date_input("Interval de dates", (dmin, dmax),
                             min_value=dmin, max_value=dmax, key=f"rang_{nom}")
        sub = df.loc[str(rang[0]):str(rang[1])] if isinstance(rang, tuple) and len(rang) == 2 else df

        # ---- gràfic
        if num.shape[1] == 0:
            st.info("Aquest fitxer no té columnes numèriques per dibuixar.")
        else:
            per_defecte = [c for c in num.columns if "POTENCIA ACTIVA" in c.upper()
                           and "FASE" not in c.upper() and "(kW)" in c][:3]
            if not per_defecte:
                per_defecte = list(num.columns[:2])
            cols = st.multiselect("Columnes a dibuixar", list(num.columns),
                                  default=per_defecte, key=f"cols_{nom}")
            if cols:
                dades = sub[cols]
                regla = OPCIONS_REMOSTREIG[remostreig]
                if regla:
                    dades = getattr(dades.resample(regla), funcio)()
                elif len(dades) > 20000:
                    st.caption("Gràfic submostrejat (1 de cada n punts) per anar més ràpid.")
                    dades = dades.iloc[:: len(dades) // 20000 + 1]
                st.line_chart(dades)

        # ---- estadístiques
        st.markdown("**Estadístiques**")
        if num.shape[1]:
            st.dataframe(sub[num.columns].describe().T, use_container_width=True)

        # ---- valors que falten
        st.markdown("**Valors que falten (%) per columna**")
        falten = (sub.isna().mean() * 100).round(2).sort_values(ascending=False)
        falten = falten[falten > 0]
        if falten.empty:
            st.success("No hi ha valors buits.")
        else:
            st.dataframe(falten.rename("% buits"), use_container_width=True)

        # ---- perfil mitjà per hora del dia
        if num.shape[1] and "cols" in locals() and cols:
            st.markdown("**Perfil mitjà per hora del dia** (columnes triades)")
            st.line_chart(sub[cols].groupby(sub.index.hour).mean())

        # ---- taula
        with st.expander("Veure les primeres files"):
            st.dataframe(sub.head(200))
        with st.expander("Llista de columnes"):
            st.write(list(df.columns))
