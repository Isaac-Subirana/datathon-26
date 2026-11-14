"""
dashboard_vall_punta.py - Hores vall i punta segons el mes.
Poseu-lo a starter_kit/ (o a qualsevol carpeta amb ../data/train).
Execució:  streamlit run dashboard_vall_punta.py
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

AQUI = Path(__file__).parent
MESOS = ["Gen", "Feb", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Des"]

st.set_page_config(page_title="Hores vall i punta", layout="wide")
st.title("Hores vall i punta segons el mes")


def trobar_dades():
    for p in [AQUI / "../data/train", AQUI / "data/train", AQUI / "data", AQUI]:
        if (p / "contador.csv").exists():
            return p
    return None


@st.cache_data(show_spinner="Carregant dades...")
def carregar(data_dir: str) -> pd.DataFrame:
    d = Path(data_dir)
    cont = pd.read_csv(d / "contador.csv", parse_dates=["Fecha"]).set_index("Fecha")
    inv = pd.read_csv(d / "inversor.csv", parse_dates=["Fecha"]).set_index("Fecha")
    pvpc = pd.read_csv(d / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co2 = pd.read_csv(d / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")

    load = (-cont["Contador - POTENCIA ACTIVA EXPORTADA (kW)"]).clip(lower=0, upper=5000)
    load_h = load.resample("1h").mean()
    cols = [[x for x in inv.columns if f"INVERSOR {i}" in x.upper()
             and "POTENCIA ACTIVA" in x.upper() and "FASE" not in x.upper()][0]
            for i in (1, 2, 3)]
    pv_h = sum(inv[c].fillna(0) for c in cols).clip(lower=0).resample("1h").mean()

    df = pd.DataFrame({
        "load_kw": load_h,
        "pv_kw": pv_h,
        "preu": pvpc["precio_eur_per_kwh"],
        "co2": co2["co2_kg_per_kwh"],
    })   # sense dropna: així el preu i el CO2 de novembre no es perden encara que falti el consum
    df["net_kw"] = (df["load_kw"] - df["pv_kw"]).clip(lower=0)
    return df


data_dir = trobar_dades()
if data_dir is None:
    st.error("No trobo data/train/contador.csv. Comproveu l'estructura de carpetes.")
    st.stop()

df = carregar(str(data_dir))
df["hora"] = df.index.hour
df["mes"] = df.index.month
df["cap_setmana"] = df.index.dayofweek >= 5

# ---------------------------------------------------------------- controls
st.sidebar.header("Configuració")
mag = st.sidebar.selectbox(
    "Què vols analitzar?",
    ["Preu (EUR/kWh)", "CO2 (kg/kWh)", "Índex combinat (CO2 + preu)", "Consum net del campus (kW)"],
)
dies = st.sidebar.radio("Dies", ["Tots", "Feina (dl-dv)", "Cap de setmana"])
n_hores = st.sidebar.slider("Hores punta / hores vall per dia", 2, 10, 6)

alpha = 0.7
if mag.startswith("Índex"):
    alpha = st.sidebar.slider("Pes del CO2 (la resta és preu)", 0.0, 1.0, 0.7, 0.05)

d = df.copy()
if dies == "Feina (dl-dv)":
    d = d[~d["cap_setmana"]]
elif dies == "Cap de setmana":
    d = d[d["cap_setmana"]]

if mag.startswith("Preu"):
    d["valor"] = d["preu"]
    unitat = "EUR/kWh"
elif mag.startswith("CO2"):
    d["valor"] = d["co2"]
    unitat = "kg/kWh"
elif mag.startswith("Índex"):
    d["valor"] = alpha * d["co2"] / df["co2"].mean() + (1 - alpha) * d["preu"] / df["preu"].mean()
    unitat = "adimensional (1 = mitjana)"
else:
    d["valor"] = d["net_kw"]
    unitat = "kW"

d = d.dropna(subset=["valor"])   # només traiem les hores sense dada de la magnitud triada

# ---------------------------------------------------------------- perfil mes x hora
perfil = d.groupby(["mes", "hora"])["valor"].mean().unstack("hora")   # files = mes, columnes = hora

# classificació: les n_hores més altes de cada mes = punta, les n_hores més baixes = vall
cls = pd.DataFrame("", index=perfil.index, columns=perfil.columns)
resum = []
for m in perfil.index:
    fila = perfil.loc[m]
    ordre = fila.sort_values()
    vall = list(ordre.index[:n_hores])
    punta = list(ordre.index[-n_hores:])
    cls.loc[m, vall] = "vall"
    cls.loc[m, punta] = "punta"
    mv, mp = fila[vall].mean(), fila[punta].mean()
    resum.append({
        "mes": m,
        "Mes": MESOS[m - 1],
        "Mitjana vall": mv,
        "Mitjana punta": mp,
        "Diferència": mp - mv,
        "Ratio punta/vall": mp / mv if mv > 0 else np.nan,
        "Hores vall": sorted(vall),
        "Hores punta": sorted(punta),
    })
resum = pd.DataFrame(resum)

st.caption(f"Magnitud: **{mag}** · unitat: {unitat} · dies: {dies}")

# ---------------------------------------------------------------- 1. mapa de calor
st.subheader("1. Mapa de calor: hora del dia × mes")
heat = perfil.reset_index().melt(id_vars="mes", var_name="hora", value_name="valor")
heat["Mes"] = heat["mes"].map(lambda x: MESOS[x - 1])
chart = (
    alt.Chart(heat)
    .mark_rect()
    .encode(
        x=alt.X("hora:O", title="Hora del dia"),
        y=alt.Y("Mes:O", sort=MESOS, title=None),
        color=alt.Color("valor:Q", scale=alt.Scale(scheme="redyellowgreen", reverse=True),
                        title=unitat),
        tooltip=["Mes", "hora", alt.Tooltip("valor:Q", format=".3f")],
    )
    .properties(height=380)
)
st.altair_chart(chart, use_container_width=True)

# ---------------------------------------------------------------- 2. classificació
st.subheader(f"2. Classificació: {n_hores} hores punta i {n_hores} hores vall per mes")
cl = cls.reset_index().melt(id_vars="mes", var_name="hora", value_name="tipus")
cl["Mes"] = cl["mes"].map(lambda x: MESOS[x - 1])
cl["tipus"] = cl["tipus"].replace("", "normal")
chart2 = (
    alt.Chart(cl)
    .mark_rect(stroke="white")
    .encode(
        x=alt.X("hora:O", title="Hora del dia"),
        y=alt.Y("Mes:O", sort=MESOS, title=None),
        color=alt.Color("tipus:N", title=None,
                        scale=alt.Scale(domain=["vall", "normal", "punta"],
                                        range=["#2e9e5b", "#e6e6e6", "#d64545"])),
        tooltip=["Mes", "hora", "tipus"],
    )
    .properties(height=380)
)
st.altair_chart(chart2, use_container_width=True)

tabla = resum[["Mes", "Hores vall", "Hores punta"]].copy()
tabla["Hores vall"] = tabla["Hores vall"].apply(lambda l: ", ".join(f"{h}h" for h in l))
tabla["Hores punta"] = tabla["Hores punta"].apply(lambda l: ", ".join(f"{h}h" for h in l))
st.dataframe(tabla, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 3. diferència per mes
st.subheader("3. Diferència entre punta i vall per mes")
c1, c2 = st.columns(2)
c1.write(f"Diferència punta − vall ({unitat})")
c1.bar_chart(resum.set_index("Mes")["Diferència"].reindex(MESOS))
c2.write("Ratio punta / vall")
c2.bar_chart(resum.set_index("Mes")["Ratio punta/vall"].reindex(MESOS))

if mag.startswith(("Preu", "CO2", "Índex")):
    st.info(
        "La bateria té un rendiment de cicle del 90%. Perquè carregar a la vall i descarregar "
        "a la punta compensi, el ratio punta/vall ha de ser **superior a 1,11** (1/0,9). "
        "Mireu en quins mesos es compleix amb marge."
    )
    ok = resum[resum["Ratio punta/vall"] > 1 / 0.9]["Mes"].tolist()
    st.write("Mesos on el ratio supera 1,11:", ", ".join(ok) if ok else "cap")

# ---------------------------------------------------------------- 4. perfil d'un mes concret
st.subheader("4. Perfil horari d'un o més mesos")
triats = st.multiselect("Mesos", MESOS, default=[MESOS[0], MESOS[6]])
if triats:
    idx = [MESOS.index(m) + 1 for m in triats]
    sub = perfil.loc[[i for i in idx if i in perfil.index]].T
    sub.columns = [MESOS[i - 1] for i in sub.columns]
    st.line_chart(sub)

with st.expander("Dades del resum"):
    st.dataframe(resum.drop(columns=["mes"]), hide_index=True)
