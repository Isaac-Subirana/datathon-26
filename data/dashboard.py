"""
dashboard.py - Gràfics de Streamlit per al Repte UPC Sostenible.
Poseu-lo a la carpeta starter_kit/ (al costat d'agent.py i environment.py).
Execució:  streamlit run dashboard.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

st.set_page_config(page_title="Repte UPC Sostenible", layout="wide")
st.title("Repte UPC Sostenible - Dashboard")

# ---------------------------------------------------------------- dades
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

    cols = []
    for i in (1, 2, 3):
        c = [x for x in inv.columns
             if f"INVERSOR {i}" in x.upper() and "POTENCIA ACTIVA" in x.upper()
             and "FASE" not in x.upper()][0]
        cols.append(c)
    pv = sum(inv[c].fillna(0) for c in cols).clip(lower=0)
    pv_h = pv.resample("1h").mean()

    df = pd.DataFrame({
        "load_kw": load_h,
        "pv_kw": pv_h,
        "precio_eur_per_kwh": pvpc["precio_eur_per_kwh"],
        "co2_kg_per_kwh": co2["co2_kg_per_kwh"],
    }).dropna()
    return df


data_dir = trobar_dades()
if data_dir is None:
    st.error("No trobo data/train/contador.csv. Moveu les dades a ../data/train o a data/train.")
    st.stop()

df = carregar(str(data_dir))
df["net_kw"] = df["load_kw"] - df["pv_kw"]
df["hora"] = df.index.hour
df["dia_setmana"] = df.index.dayofweek
df["mes"] = df.index.month

# ---------------------------------------------------------------- barra lateral
st.sidebar.header("Filtre de dates")
dmin, dmax = df.index.min().date(), df.index.max().date()
rang = st.sidebar.date_input("Interval", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(rang, tuple) and len(rang) == 2:
    sel = df.loc[str(rang[0]):str(rang[1])]
else:
    sel = df
st.sidebar.write(f"{len(sel)} hores seleccionades")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Resum", "Preu i CO2", "Consum i solar", "Agent"]
)

# ---------------------------------------------------------------- resum
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consum mitjà (kW)", f"{sel['load_kw'].mean():.0f}")
    c2.metric("Solar mitjana (kW)", f"{sel['pv_kw'].mean():.0f}")
    c3.metric("Preu mitjà (EUR/kWh)", f"{sel['precio_eur_per_kwh'].mean():.3f}")
    c4.metric("CO2 mitjà (kg/kWh)", f"{sel['co2_kg_per_kwh'].mean():.3f}")
    st.subheader("Sèries horàries")
    st.line_chart(sel[["load_kw", "pv_kw"]])
    st.line_chart(sel[["precio_eur_per_kwh"]])
    st.line_chart(sel[["co2_kg_per_kwh"]])

# ---------------------------------------------------------------- preu i CO2
with tab2:
    st.subheader("Perfil mitjà per hora del dia")
    perfil = sel.groupby("hora")[["precio_eur_per_kwh", "co2_kg_per_kwh"]].mean()
    a, b = st.columns(2)
    a.write("Preu (EUR/kWh)")
    a.bar_chart(perfil["precio_eur_per_kwh"])
    b.write("CO2 (kg/kWh)")
    b.bar_chart(perfil["co2_kg_per_kwh"])

    st.subheader("Mapa de calor: hora x mes")
    mag = st.radio("Magnitud", ["precio_eur_per_kwh", "co2_kg_per_kwh"], horizontal=True)
    piv = sel.pivot_table(index="hora", columns="mes", values=mag, aggfunc="mean")
    try:
        st.dataframe(piv.style.background_gradient(cmap="RdYlGn_r", axis=None).format("{:.3f}"))
    except Exception:
        st.dataframe(piv)

    st.subheader("Correlació preu vs CO2")
    st.write(f"Correlació: **{sel['precio_eur_per_kwh'].corr(sel['co2_kg_per_kwh']):.2f}**")
    st.scatter_chart(sel.sample(min(2000, len(sel)), random_state=0),
                     x="precio_eur_per_kwh", y="co2_kg_per_kwh")

# ---------------------------------------------------------------- consum i solar
with tab3:
    st.subheader("Perfil mitjà per hora")
    st.line_chart(sel.groupby("hora")[["load_kw", "pv_kw", "net_kw"]].mean())
    st.subheader("Consum segons dia de la setmana (0 = dilluns)")
    st.bar_chart(sel.groupby("dia_setmana")["load_kw"].mean())
    st.subheader("Mitjanes per mes")
    st.bar_chart(sel.groupby("mes")[["load_kw", "pv_kw"]].mean())
    st.subheader("Hores amb solar > consum (sobrant)")
    st.write(f"{(sel['net_kw'] < 0).mean() * 100:.1f}% de les hores")

# ---------------------------------------------------------------- agent
with tab4:
    st.subheader("Simulació de l'agent (agent.py)")
    try:
        import importlib
        import agent as agent_mod
        import environment as env_mod
        importlib.reload(agent_mod)
        importlib.reload(env_mod)
    except Exception as e:
        st.error(f"No puc importar agent.py / environment.py: {e}")
        st.stop()

    mode = st.radio("Avaluar sobre", ["Interval seleccionat", "Setmana concreta", "Tot l'any"],
                    horizontal=True)
    if mode == "Setmana concreta":
        setmanes = sorted({(i.isocalendar().year, i.isocalendar().week) for i in df.index})
        w = st.selectbox("Setmana ISO", setmanes, index=0)
        dades = df[[(i.isocalendar().year, i.isocalendar().week) == w for i in df.index]]
    elif mode == "Tot l'any":
        dades = df
    else:
        dades = sel

    if st.button("Executar simulació") and len(dades) > 1:
        base = dades[["load_kw", "pv_kw", "precio_eur_per_kwh", "co2_kg_per_kwh"]]
        env = env_mod.CampusBatteryEnv(base)
        ag = agent_mod.BatteryAgent()
        obs = env.reset()
        done = False
        while not done:
            obs, done = env.step(ag.act(obs))
        res = env.evaluate_results()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Score", res["score"])
        m2.metric("CO2 estalviat %", res["co2_estalviat_pct"])
        m3.metric("Cost estalviat %", res["cost_estalviat_pct"])
        m4.metric("Infraccions", res["infraccions"])

        out = pd.DataFrame({
            "SOC (kWh)": env.soc_series,
            "Acció (kW)": env.actions[:len(env.soc_series)],
            "Xarxa amb bateria (kW)": env.grid,
            "Xarxa sense bateria (kW)": np.maximum(base["load_kw"].values - base["pv_kw"].values, 0),
            "Preu": base["precio_eur_per_kwh"].values,
            "CO2": base["co2_kg_per_kwh"].values,
        }, index=base.index[:len(env.soc_series)])

        st.write("Estat de càrrega de la bateria")
        st.line_chart(out["SOC (kWh)"])
        st.write("Acció de l'agent (positiu = carrega, negatiu = descarrega)")
        st.bar_chart(out["Acció (kW)"])
        st.write("Xarxa amb bateria vs sense bateria")
        st.line_chart(out[["Xarxa amb bateria (kW)", "Xarxa sense bateria (kW)"]])
        st.write("Preu i CO2")
        st.line_chart(out[["Preu", "CO2"]])
        with st.expander("Totes les mètriques"):
            st.json(res)
