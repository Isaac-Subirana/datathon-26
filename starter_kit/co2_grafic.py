from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Anàlisi d'Emissions CO₂", layout="wide")


@st.cache_data
def carregar_dades():
  ruta_csv = Path(__file__).parent / "co2_red.csv"
  df = pd.read_csv(ruta_csv)
  df["Fecha"] = pd.to_datetime(df["Fecha"])
  # Convertim la proporció (0-1) a percentatge (0-100%)
  df["porcentaje_con_emisiones"] = df["porcentaje_con_emisiones"] * 100
  return df.sort_values("Fecha")


df = carregar_dades()

st.title("Evolució de les Emissions de CO₂ i Generació Elèctrica")

# Barra lateral amb filtres
st.sidebar.header("Filtres i visualització")

data_min = df["Fecha"].min().date()
data_max = df["Fecha"].max().date()

rang_dates = st.sidebar.date_input(
    "Rang de dates",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
)

agregacio = st.sidebar.selectbox(
    "Agrupació temporal",
    options=[
        "Horària (dades originals)",
        "Diària (mitjana)",
        "Setmanal (mitjana)",
        "Mensual (mitjana)",
    ],
    index=1,  # Per defecte mostra la mitjana diària per fer-ho més llegible
)

# Filtrar el DataFrame segons les dates seleccionades
if isinstance(rang_dates, tuple) and len(rang_dates) == 2:
  inici, fi = rang_dates
  df_filtrat = df[
      (df["Fecha"].dt.date >= inici) & (df["Fecha"].dt.date <= fi)
  ].copy()
else:
  df_filtrat = df.copy()

# Aplicar l'agrupació temporal escollida
if agregacio == "Diària (mitjana)":
  df_plot = df_filtrat.groupby(df_filtrat["Fecha"].dt.date).mean(
      numeric_only=True
  )
elif agregacio == "Setmanal (mitjana)":
  df_plot = df_filtrat.groupby(
      df_filtrat["Fecha"].dt.to_period("W").dt.to_timestamp()
  ).mean(numeric_only=True)
elif agregacio == "Mensual (mitjana)":
  df_plot = df_filtrat.groupby(
      df_filtrat["Fecha"].dt.to_period("M").dt.to_timestamp()
  ).mean(numeric_only=True)
else:
  df_plot = df_filtrat.set_index("Fecha")

# Indicadors resum (KPIs)
col1, col2, col3 = st.columns(3)
col1.metric(
    "Mitjana CO₂ (kg/kWh)", f"{df_filtrat['co2_kg_per_kwh'].mean():.4f}"
)
col2.metric(
    "% Generació amb emissions",
    f"{df_filtrat['porcentaje_con_emisiones'].mean():.1f} %",
)
col3.metric(
    "Generació sense emissions (mitjana)",
    f"{df_filtrat['gen_sin_emisiones_mw'].mean():,.0f} MW",
)

# Gràfic 1: Intensitat de CO2
st.subheader("Intensitat d'emissions (kg CO₂ / kWh)")
st.line_chart(df_plot[["co2_kg_per_kwh"]])

# Gràfic 2: Comparativa de generació elèctrica
st.subheader("Generació elèctrica: sense emissions vs. amb emissions (MW)")
df_generacio = df_plot.rename(
    columns={
        "gen_sin_emisiones_mw": "Sense emissions (MW)",
        "gen_con_emisiones_mw": "Amb emissions (MW)",
    }
)
st.area_chart(df_generacio[["Sense emissions (MW)", "Amb emissions (MW)"]])

# Gràfic 3: Percentatge amb emissions
st.subheader("Percentatge de generació amb emissions (%)")
st.line_chart(df_plot[["porcentaje_con_emisiones"]])

# Taula desplegable amb les dades
with st.expander("Veure taula de dades"):
  st.dataframe(df_filtrat, use_container_width=True)