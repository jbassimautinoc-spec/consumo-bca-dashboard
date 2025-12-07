# ==========================
# AUTENTICACIÓN POR EMAIL + CÓDIGO
# ==========================

import streamlit as st

USUARIOS_PERMITIDOS = {
    "ycarriego@grupobca.com.ar": 8521,
    "aescobar@grupobca.com.ar": 9514,
    "oscarsaavedra01@gmail.com": 1322,
    "jptermite@grupobca.com.ar": 3695,
    "mcabo@grupobca.com.ar": 2002,
    "jbassi@grupobca.com.ar": 1304,
    "mmanresa@grupobca.com.ar": 1045,
    "dloillet@grupobca.com.ar": 2287
}

# Inicializar variable de sesión
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# Pantalla de login si NO está autenticado
if not st.session_state["autenticado"]:
    st.header("Acceso al Panel de Consumo BCA")

    email = st.text_input("Ingrese su correo corporativo:")
    codigo = st.text_input("Ingrese su código de acceso:", type="password")

    if st.button("Ingresar"):
        if email in USUARIOS_PERMITIDOS and str(codigo) == str(USUARIOS_PERMITIDOS[email]):
            st.session_state["autenticado"] = True
            st.success("Acceso concedido. Bienvenido.")
            st.rerun()

        else:
            st.error("Correo o código incorrecto.")

    st.stop()  # 🔥 BLOQUEA TODO EL DASHBOARD

import pandas as pd
import numpy as np
import streamlit as st
from io import BytesIO
import re
import altair as alt
import os

# PDF
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, portrait
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

# ==========================
# CONFIGURACIÓN GENERAL
# ==========================

TOLERANCIA_PCT = 0.10

FILE_CONSUMO = "consumo_real.xlsx"
FILE_KM = "distances_26-11 al 03-12.xlsx"   # ajustá el nombre si cambia
FILE_NOMINA = "Nomina_consumo_camion.xlsx"

COLOR_PRINCIPAL = "#006778"   # BCA aprox
COLOR_SECUNDARIO = "#009999"  # BCA aprox


# ==========================
# FUNCIONES AUXILIARES
# ==========================

def es_patente_valida(p):
    """Valida patentes argentinas formato viejo AAA123 o nuevo AA123BB."""
    if pd.isna(p):
        return False
    p = str(p).strip().upper()
    formato_viejo = r'^[A-Z]{3}[0-9]{3}$'         # ABC123
    formato_nuevo = r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$' # AB123CD
    return bool(re.match(formato_viejo, p) or re.match(formato_nuevo, p))


def to_num_col(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )


def clasificar_estado(row):
    km = row["KM_RECORRIDOS"]
    litros = row["LITROS_TOTALES"]
    cons_real = row["CONSUMO_REAL_L_100KM"]
    cons_teor = row["CONSUMO_TEORICO_L_100KM"]
    min_ok = row["MIN_OK"]
    max_ok = row["MAX_OK"]

    if km == 0 and litros == 0:
        return "SIN MOVIMIENTO"
    if km > 0 and litros == 0:
        return "FALTA CARGA"
    if km == 0 and litros > 0:
        return "ERROR DE KM"
    if pd.isna(cons_real) or pd.isna(cons_teor):
        return "SIN DATOS"

    limite_mejor_15 = cons_teor * 0.85
    if cons_real < limite_mejor_15:
        return "DUDOSO"

    if min_ok <= cons_real <= max_ok:
        return "NORMAL"

    if limite_mejor_15 <= cons_real < min_ok:
        return "NORMAL"

    if cons_real > max_ok:
        return "A AUDITAR"

    return "SIN DATOS"


def color_row(row):
    estado = row["ESTADO"]
    if estado == "NORMAL":
        color = "#dcedc8"   # verde suave
    elif estado == "A AUDITAR":
        color = "#ffcdd2"   # rojo suave
    elif estado == "DUDOSO":
        color = "#bbdefb"   # celeste
    else:
        color = "#fff9c4"   # amarillo suave
    return [f"background-color:{color}"] * len(row)


def kpi_card(label, value, color_bg, color_text="#ffffff"):
    return f"""
    <div style="background-color:{color_bg};
                padding:16px;
                border-radius:12px;
                text-align:center;
                box-shadow:0 2px 6px rgba(0,0,0,0.15);">
        <div style="font-size:14px;color:{color_text};margin-bottom:4px;">
            {label}
        </div>
        <div style="font-size:24px;font-weight:bold;color:{color_text};">
            {value}
        </div>
    </div>
    """


def recomendaciones_automaticas(normal, auditar, dudoso, sin_datos, total):
    """Genera recomendaciones según la situación general."""
    if total == 0:
        return [
            "No hay datos disponibles en el período analizado. Verificar los archivos de entrada."
        ]

    recs = []

    pct_normal = normal / total * 100 if total > 0 else 0
    pct_auditar = auditar / total * 100 if total > 0 else 0
    pct_dudoso = dudoso / total * 100 if total > 0 else 0
    pct_sin_datos = sin_datos / total * 100 if total > 0 else 0

    if pct_auditar > 20:
        recs.append(
            "Alto porcentaje de unidades en estado A AUDITAR. "
            "Se recomienda priorizar la revisión de estas unidades, verificando consumo, rutas y condiciones de operación."
        )

    if pct_dudoso > 10:
        recs.append(
            "Existe un número relevante de unidades en estado DUDOSO, con consumos inusualmente bajos. "
            "Se sugiere revisar la carga de kilómetros, integridad de datos de odómetro y registros GPS."
        )

    if pct_normal >= 70:
        recs.append(
            "La mayoría de las unidades se encuentra en estado NORMAL. "
            "Se recomienda mantener los procedimientos actuales de operación y monitoreo."
        )

    if pct_sin_datos > 0:
        recs.append(
            "Hay unidades en estado SIN DATOS. "
            "Conviene revisar los registros de consumo y kilometraje para completar la información."
        )

    if not recs:
        recs.append(
            "La situación general es intermedia. "
            "Se recomienda monitorear semanalmente y revisar puntualmente las unidades con desvíos."
        )

    return recs


# ==========================
# 1) CARGA DE ARCHIVOS
# ==========================

df_cons = pd.read_excel(FILE_CONSUMO)
df_km = pd.read_excel(FILE_KM)
df_nom = pd.read_excel(FILE_NOMINA)

# Renombrar la columna correcta
if "LITROS UNIDADES" in df_cons.columns:
    df_cons = df_cons.rename(columns={"LITROS UNIDADES": "LITROS"})


# ==========================
# 2) NORMALIZAR NOMBRES
# ==========================

df_cons = df_cons.rename(columns={
    "IDENTIFICACIONTARJETA": "PATENTE",
    "LITROS UNIDADES": "LITROS"
})
df_km = df_km.rename(columns={
    "Placa/Patente": "PATENTE",
    "Distancia [km]": "KM_RECORRIDOS"
})

df_nom.columns = [c.upper() for c in df_nom.columns]
if "PATENTE" not in df_nom.columns:
    for c in df_nom.columns:
        if "PAT" in c.upper():
            df_nom = df_nom.rename(columns={c: "PATENTE"})
            break

possible_names = [c for c in df_nom.columns if "LIT" in c.upper() and "100" in c]
if not possible_names:
    possible_names = [c for c in df_nom.columns if "LIT" in c.upper()]
consumo_col = possible_names[0]
df_nom = df_nom.rename(columns={consumo_col: "LITROS_100KM"})

# ==========================
# 3) LIMPIEZA Y VALIDACIÓN
# ==========================

df_cons["LITROS"] = to_num_col(df_cons["LITROS"])
df_km["KM_RECORRIDOS"] = to_num_col(df_km["KM_RECORRIDOS"])
df_nom["LITROS_100KM"] = to_num_col(df_nom["LITROS_100KM"])

df_cons["PATENTE"] = df_cons["PATENTE"].astype(str).str.upper().str.strip()
df_km["PATENTE"] = df_km["PATENTE"].astype(str).str.upper().str.strip()
df_nom["PATENTE"] = df_nom["PATENTE"].astype(str).str.upper().str.strip()

df_cons_invalidas = df_cons[~df_cons["PATENTE"].apply(es_patente_valida)]
df_km_invalidas   = df_km[~df_km["PATENTE"].apply(es_patente_valida)]
df_nom_invalidas  = df_nom[~df_nom["PATENTE"].apply(es_patente_valida)]

df_cons = df_cons[df_cons["PATENTE"].apply(es_patente_valida)]
df_km   = df_km[df_km["PATENTE"].apply(es_patente_valida)]
df_nom  = df_nom[df_nom["PATENTE"].apply(es_patente_valida)]

# ==========================
# 4) AGRUPACIÓN
# ==========================

df_litros_total = df_cons.groupby("PATENTE", as_index=False)["LITROS"].sum().rename(columns={"LITROS": "LITROS_TOTALES"})
df_km_total = df_km.groupby("PATENTE", as_index=False)["KM_RECORRIDOS"].sum()

# ==========================
# 5) UNIFICACIÓN
# ==========================

cols_nom = ["PATENTE", "LITROS_100KM"]
if "MODELO" in df_nom.columns:
    cols_nom.append("MODELO")

df_final = pd.merge(df_km_total, df_litros_total, on="PATENTE", how="outer")
df_final = pd.merge(df_final, df_nom[cols_nom], on="PATENTE", how="left")

df_final["KM_RECORRIDOS"] = df_final["KM_RECORRIDOS"].fillna(0)
df_final["LITROS_TOTALES"] = df_final["LITROS_TOTALES"].fillna(0)

# ==========================
# 6) CÁLCULOS
# ==========================

df_final["CONSUMO_REAL_L_100KM"] = np.where(
    df_final["KM_RECORRIDOS"] > 0,
    (df_final["LITROS_TOTALES"] / df_final["KM_RECORRIDOS"]) * 100,
    np.nan
)

df_final["CONSUMO_TEORICO_L_100KM"] = df_final["LITROS_100KM"]
df_final["LITROS_TEOREICOS_ESPERADOS"] = df_final["KM_RECORRIDOS"] * df_final["CONSUMO_TEORICO_L_100KM"] / 100

df_final["DESVIO_LITROS"] = df_final["LITROS_TOTALES"] - df_final["LITROS_TEOREICOS_ESPERADOS"]
df_final["DESVIO_PCT"] = np.where(
    df_final["LITROS_TEOREICOS_ESPERADOS"] > 0,
    df_final["DESVIO_LITROS"] / df_final["LITROS_TEOREICOS_ESPERADOS"],
    np.nan
)

df_final["MIN_OK"] = df_final["CONSUMO_TEORICO_L_100KM"] * (1 - TOLERANCIA_PCT)
df_final["MAX_OK"] = df_final["CONSUMO_TEORICO_L_100KM"] * (1 + TOLERANCIA_PCT)

# ==========================
# 7) ESTADOS
# ==========================

df_final["ESTADO"] = df_final.apply(clasificar_estado, axis=1)

df_final["COLOR"] = df_final["ESTADO"].map({
    "NORMAL": "🟢",
    "A AUDITAR": "🔴",
    "DUDOSO": "🔵",
    "SIN MOVIMIENTO": "⚪",
    "FALTA CARGA": "🟣",
    "ERROR DE KM": "⚠️",
    "SIN DATOS": "🟡"
})

salida = df_final[[
    "PATENTE",
    "MODELO",
    "KM_RECORRIDOS",
    "LITROS_TOTALES",
    "CONSUMO_REAL_L_100KM",
    "CONSUMO_TEORICO_L_100KM",
    "LITROS_TEOREICOS_ESPERADOS",
    "DESVIO_LITROS",
    "DESVIO_PCT",
    "ESTADO",
    "COLOR"
]].sort_values(["MODELO", "PATENTE"])

# ==========================
# 8) STREAMLIT – LAYOUT
# ==========================

st.set_page_config(page_title="Control inteligente de consumo", layout="wide")



# Encabezado corporativo
header_col1, header_col2 = st.columns([1, 4])
with header_col1:
    posibles_logos = [
        "logo_bca.png", "logo_bca.jpeg", "logo_bca.jpg",
        "logo.png", "logo.jpg", "logo.jpeg"
    ]
    logo_encontrado = None
    for l in posibles_logos:
        if os.path.exists(l):
            logo_encontrado = l
            break
    if logo_encontrado:
        st.image(logo_encontrado, width=110)
with header_col2:
    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg,{COLOR_PRINCIPAL},{COLOR_SECUNDARIO});
                    padding:16px 24px;
                    border-radius:16px;
                    color:white;">
            <div style="font-size:22px;font-weight:bold;">
                Control inteligente de consumo – Grupo BCA
            </div>
            <div style="font-size:13px;opacity:0.9;">
                Monitoreo de consumo real vs teórico por unidad y modelo
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Espaciado visual debajo del encabezado
st.markdown(
    """
    <div style="height:35px;"></div>
    """,
    unsafe_allow_html=True
)


# ==========================
# 9) FILTROS
# ==========================

st.sidebar.header("Filtros")

modelos = salida["MODELO"].dropna().unique().tolist()
modelos.sort()
modelo_sel = st.sidebar.selectbox("Modelo", ["TODOS"] + modelos)

estados_disponibles = salida["ESTADO"].dropna().unique().tolist()
estado_sel = st.sidebar.multiselect("Estado", estados_disponibles, default=estados_disponibles)

columna_orden = st.sidebar.selectbox("Ordenar por", salida.columns.tolist())
asc = st.sidebar.checkbox("Orden ascendente", True)

salida_filtrada = salida.copy()
if modelo_sel != "TODOS":
    salida_filtrada = salida_filtrada[salida_filtrada["MODELO"] == modelo_sel]

salida_filtrada = salida_filtrada[salida_filtrada["ESTADO"].isin(estado_sel)]
salida_filtrada = salida_filtrada.sort_values(by=columna_orden, ascending=asc)

# ==========================
# 10) KPIs
# ==========================

total = len(salida_filtrada)
normal = (salida_filtrada["ESTADO"] == "NORMAL").sum()
auditar = (salida_filtrada["ESTADO"] == "A AUDITAR").sum()
dudoso = (salida_filtrada["ESTADO"] == "DUDOSO").sum()
sin_datos = (salida_filtrada["ESTADO"] == "SIN DATOS").sum()

pct_normal = (normal / total * 100) if total > 0 else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(kpi_card("Normal", normal, COLOR_PRINCIPAL), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_card("A Auditar", auditar, "#c62828"), unsafe_allow_html=True)
with k3:
    st.markdown(kpi_card("Dudoso", dudoso, "#1565c0"), unsafe_allow_html=True)
with k4:
    st.markdown(kpi_card("% Normal", f"{pct_normal:.1f}%", COLOR_SECUNDARIO), unsafe_allow_html=True)

# ==========================
# 11) GRÁFICO — DISTRIBUCIÓN DE ESTADOS (DASHBOARD)
# ==========================

st.subheader("Distribución de estados")

resumen_est = None
if not salida_filtrada.empty:
    resumen_est = (
        salida_filtrada["ESTADO"]
        .value_counts()
        .rename_axis("Estado")
        .reset_index(name="Cantidad")
    )

    bar_color = "#009999"

    chart_barras = (
        alt.Chart(resumen_est)
        .mark_bar(color=bar_color)
        .encode(
            x=alt.X(
                "Estado:N",
                sort=None,
                title="Estado",
                axis=alt.Axis(
                    labelAngle=0,
                    labelFontSize=14,
                    titleFontSize=14
                )
            ),
            y=alt.Y("Cantidad:Q", title="Cantidad"),
            tooltip=["Estado", "Cantidad"]
        )
    )

    labels = (
        alt.Chart(resumen_est)
        .mark_text(
            align="center",
            baseline="bottom",
            dy=-2,
            fontSize=14,
            color=bar_color
        )
        .encode(
            x="Estado:N",
            y="Cantidad:Q",
            text="Cantidad:Q"
        )
    )

    st.altair_chart(chart_barras + labels, use_container_width=True)

# ======================================================
# TABLA DETALLADA
# ======================================================
st.subheader("Detalle por unidad")

# 🔧 Eliminamos la columna COLOR que genera conflicto en tablas HTML/React
if "COLOR" in salida_filtrada.columns:
    salida_filtrada = salida_filtrada.drop(columns=["COLOR"])

# 🟩 USAMOS st.dataframe EN VEZ DE HTML — sin errores removeChild
styled_df = salida_filtrada.style.apply(color_row, axis=1).format({
    "KM_RECORRIDOS": "{:.2f}",
    "LITROS_TOTALES": "{:.2f}",
    "CONSUMO_REAL_L_100KM": "{:.2f}",
    "CONSUMO_TEORICO_L_100KM": "{:.2f}",
    "LITROS_TEOREICOS_ESPERADOS": "{:.2f}",
    "DESVIO_LITROS": "{:.2f}",
    "DESVIO_PCT": "{:.1%}"
})

st.dataframe(styled_df, use_container_width=True)

# ==========================
# 13) EXPORTACIÓN EXCEL / CSV
# ==========================

st.subheader("📥 Exportar datos")

buffer_excel = BytesIO()
salida_filtrada.to_excel(buffer_excel, index=False, engine="openpyxl")
buffer_excel.seek(0)
st.download_button("📘 Descargar Excel", data=buffer_excel, file_name="control_consumo.xlsx")

csv_data = salida_filtrada.to_csv(index=False, sep=";", decimal=",").encode("utf-8")
st.download_button("📄 Descargar CSV", data=csv_data, file_name="control_consumo.csv")

# ==========================
# 14) EXPORTACIÓN A PDF PREMIUM
# ==========================

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.pagesizes import letter, landscape, portrait
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib.units import cm


# Mapa de colores por estado para el PDF (cuadritos sólidos)
COLOR_ESTADO_HEX = {
    "NORMAL": "#4CAF50",        # verde
    "A AUDITAR": "#F44336",     # rojo
    "DUDOSO": "#1E88E5",        # azul
    "FALTA CARGA": "#8E24AA",   # violeta
    "ERROR DE KM": "#FB8C00",   # naranja
    "SIN MOVIMIENTO": "#9E9E9E",# gris
    "SIN DATOS": "#FFEB3B"      # amarillo
}


def cuadrado_color(color_hex, size=8):
    """Devuelve un pequeño cuadrito de color para usar en la tabla del PDF."""
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, fillColor=colors.HexColor(color_hex), strokeWidth=0))
    return d


def generar_pdf_premium(df, normal, auditar, dudoso, sin_datos, pct_normal, resumen_est):
    buffer = BytesIO()

    total = len(df)
    num_cols = len(df.columns)

    # Orientación automática según ancho (cantidad de columnas)
    pagesize = landscape(letter) if num_cols > 8 else portrait(letter)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=35,
        rightMargin=35,
        topMargin=40,
        bottomMargin=35
    )

    estilos = getSampleStyleSheet()
    story = []

    # ==========================
    # HOJA 1 – PORTADA + KPI + GRÁFICO
    # ==========================

    # Logo
    if "logo_encontrado" in globals() and logo_encontrado:
        img = Image(logo_encontrado, width=4*cm, height=4*cm)
        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, 10))

    # Título principal
    story.append(Paragraph("<b>Control inteligente de consumo – Grupo BCA</b>", estilos["Title"]))
    story.append(Spacer(1, 8))

    # Subtítulo / objetivo
    story.append(Paragraph(
        "Reporte técnico generado a partir de los datos filtrados en el tablero semanal.",
        estilos["Normal"]
    ))
    story.append(Spacer(1, 6))

    # Breve introducción
    story.append(Paragraph(
        "Este informe resume el desempeño de consumo real versus consumo teórico por unidad y modelo, "
        "permitiendo identificar desvíos operativos, oportunidades de mejora y posibles inconsistencias de datos.",
        estilos["Normal"]
    ))
    story.append(Spacer(1, 18))

    # KPIs principales
    story.append(Paragraph("<b>Indicadores principales</b>", estilos["Heading2"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"• Unidades en estado NORMAL: {normal}", estilos["Normal"]))
    story.append(Paragraph(f"• Unidades en estado A AUDITAR: {auditar}", estilos["Normal"]))
    story.append(Paragraph(f"• Unidades en estado DUDOSO: {dudoso}", estilos["Normal"]))
    story.append(Paragraph(f"• Unidades SIN DATOS: {sin_datos}", estilos["Normal"]))
    story.append(Paragraph(f"• Porcentaje de unidades NORMAL: {pct_normal:.1f}%", estilos["Normal"]))
    story.append(Spacer(1, 16))

    # Gráfico de estados en ancho completo (eje X horizontal)
    if resumen_est is not None and not resumen_est.empty:
        res = resumen_est.copy()
        data_vals = res["Cantidad"].tolist()
        categorias = res["Estado"].tolist()

        story.append(Paragraph("<b>Distribución de estados</b>", estilos["Heading2"]))
        story.append(Spacer(1, 6))
        
        # --- Gráfico corregido para que quede en la misma hoja que el título ---
        # --- Gráfico corregido para que no explote el tamaño ---
        drawing_width = doc.width
        drawing_height = 180   # altura fija y segura

        drawing = Drawing(drawing_width, drawing_height)

        bc = VerticalBarChart()
        bc.x = 40
        bc.y = 30
        bc.width = drawing_width - 80     # margen seguro
        bc.height = 120                   # altura real controlada

        bc.data = [data_vals]
        bc.categoryAxis.categoryNames = categorias
        bc.categoryAxis.labels.angle = 0
        bc.categoryAxis.labels.dy = -8
        bc.categoryAxis.labels.fontSize = 8

        bc.valueAxis.valueMin = 0
        bc.bars[0].fillColor = colors.HexColor("#009999")

        # Etiquetas
        bc.barLabelFormat = "%d"
        bc.barLabels.fontSize = 8
        bc.barLabels.dy = -3

        # AGREGAR DENTRO DEL DRAWING
        drawing.add(bc)

        story.append(drawing)
        story.append(Spacer(1, 12))

    # Mini resumen de estados (texto)
    if resumen_est is not None and not resumen_est.empty:
        story.append(Paragraph("<b>Resumen por estado</b>", estilos["Heading3"]))
        story.append(Spacer(1, 4))
        for _, r in resumen_est.iterrows():
            story.append(Paragraph(
                f"• {r['Estado']}: {r['Cantidad']} unidades",
                estilos["Normal"]
            ))

    # Salto de página para que la hoja 2 empiece con el Top 5
    story.append(PageBreak())

    # ==========================
    # HOJA 2 – TOP 5 + RECOMENDACIONES + TABLA
    # ==========================

    story.append(Paragraph("<b>Informe técnico – detalle de unidades</b>", estilos["Heading2"]))
    story.append(Spacer(1, 10))

    # Orden base por MODELO y PATENTE
    df_sorted = df.sort_values(["MODELO", "PATENTE"], na_position="last").copy()

    # --- TOP 5 unidades críticas (mayor desvío positivo en A AUDITAR)
    story.append(Paragraph("<b>Top 5 unidades con mayor desvío positivo (A AUDITAR)</b>", estilos["Heading3"]))
    story.append(Spacer(1, 6))

    df_crit = df_sorted[df_sorted["ESTADO"] == "A AUDITAR"].sort_values("DESVIO_LITROS", ascending=False)
    top5 = df_crit.head(5)

    if top5.empty:
        story.append(Paragraph(
            "No se detectaron unidades en estado A AUDITAR dentro del conjunto filtrado.",
            estilos["Normal"]
        ))
    else:
        for i, r in enumerate(top5.itertuples(), start=1):
            patente = getattr(r, "PATENTE", "")
            modelo = getattr(r, "MODELO", "")
            desvio_l = getattr(r, "DESVIO_LITROS", 0.0)
            cons_real = getattr(r, "CONSUMO_REAL_L_100KM", float("nan"))
            cons_teo = getattr(r, "CONSUMO_TEORICO_L_100KM", float("nan"))

            texto = (
                f"{i}. {patente} ({modelo}) – Desvío: {desvio_l:.1f} litros "
                f"(Real: {cons_real:.1f} L/100km | Teórico: {cons_teo:.1f} L/100km)"
            )
            story.append(Paragraph(texto, estilos["Normal"]))

    story.append(Spacer(1, 14))

    # --- Recomendaciones automáticas
    story.append(Paragraph("<b>Recomendaciones automáticas</b>", estilos["Heading3"]))
    story.append(Spacer(1, 6))

    recs = recomendaciones_automaticas(normal, auditar, dudoso, sin_datos, total)
    for r in recs:
        story.append(Paragraph("• " + r, estilos["Normal"]))

    story.append(Spacer(1, 18))

    # --- Tabla detallada ordenada por MODELO
    story.append(Paragraph("<b>Detalle de unidades (tabla filtrada)</b>", estilos["Heading3"]))
    story.append(Spacer(1, 6))

    df_pdf = df_sorted.copy()

    # Redondeo numérico y formateo limpio
    def fmt_val(col, val):
        if pd.isna(val):
            return "-"
        if col in ["KM_RECORRIDOS", "LITROS_TOTALES",
                   "CONSUMO_REAL_L_100KM", "CONSUMO_TEORICO_L_100KM",
                   "LITROS_TEOREICOS_ESPERADOS", "DESVIO_LITROS"]:
            return f"{val:.2f}"
        if col == "DESVIO_PCT":
            return f"{val*100:.1f}%"  # porcentaje
        return str(val)

    # Construcción de datos para la tabla
    columnas = [
        "PATENTE", "MODELO", "KM_RECORRIDOS", "LITROS_TOTALES",
        "CONSUMO_REAL_L_100KM", "CONSUMO_TEORICO_L_100KM",
        "LITROS_TEOREICOS_ESPERADOS", "DESVIO_LITROS", "DESVIO_PCT",
        "ESTADO", "COLOR"
    ]
    columnas = [c for c in columnas if c in df_pdf.columns]

    tabla_data = []
    tabla_data.append(columnas)

    for _, row in df_pdf.iterrows():
        fila = []
        for col in columnas:
            if col == "COLOR":
                est = row.get("ESTADO", "SIN DATOS")
                hex_col = COLOR_ESTADO_HEX.get(est, "#BDBDBD")
                fila.append(cuadrado_color(hex_col))
            else:
                fila.append(fmt_val(col, row[col]))
        tabla_data.append(fila)

    col_count = len(columnas)
    col_width = doc.width / col_count if col_count > 0 else doc.width

    tabla = Table(tabla_data, repeatRows=1, colWidths=[col_width] * col_count)

    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#006778")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    story.append(tabla)
    story.append(Spacer(1, 18))

    # ==========================
    # ANÁLISIS EJECUTIVO TÉCNICO (HOJA FINAL)
    # ==========================

    story.append(PageBreak())
    story.append(Paragraph("<b>Análisis ejecutivo técnico del consumo</b>", estilos["Heading2"]))
    story.append(Spacer(1, 10))

    if total > 0:
        pct_auditar = auditar / total * 100 if total > 0 else 0
        pct_dudoso = dudoso / total * 100 if total > 0 else 0
        pct_sin_datos = sin_datos / total * 100 if total > 0 else 0

        # Modelos más incidentes en A AUDITAR y DUDOSO
        modelo_mayor_incidente = "sin modelo predominante"
        modelo_dudoso_principal = "sin modelo predominante"

        if "MODELO" in df.columns:
            df_aud = df[df["ESTADO"] == "A AUDITAR"]
            if not df_aud.empty:
                modelo_mayor_incidente = df_aud["MODELO"].value_counts().idxmax()

            df_dud = df[df["ESTADO"] == "DUDOSO"]
            if not df_dud.empty:
                modelo_dudoso_principal = df_dud["MODELO"].value_counts().idxmax()

        # Consumos medios por grupo
        def promedio_seguro(sub, col):
            sub = sub[col].dropna()
            return float(sub.mean()) if not sub.empty else float("nan")

        df_norm = df[df["ESTADO"] == "NORMAL"]
        df_aud = df[df["ESTADO"] == "A AUDITAR"]

        prom_real_norm = promedio_seguro(df_norm, "CONSUMO_REAL_L_100KM")
        prom_teo_norm = promedio_seguro(df_norm, "CONSUMO_TEORICO_L_100KM")

        prom_real_aud = promedio_seguro(df_aud, "CONSUMO_REAL_L_100KM")
        prom_teo_aud = promedio_seguro(df_aud, "CONSUMO_TEORICO_L_100KM")

        texto1 = (
            f"El conjunto analizado muestra un {pct_normal:.1f}% de unidades en estado NORMAL, "
            f"mientras que un {pct_auditar:.1f}% se encuentra en estado A AUDITAR y un "
            f"{pct_dudoso:.1f}% en estado DUDOSO. "
            "Esta distribución refleja una flota con un núcleo estable de desempeño, "
            "pero con un volumen relevante de unidades que exceden el consumo esperado."
        )

        texto2 = (
            f"En el grupo NORMAL, el consumo medio se ubica en torno a "
            f"{prom_real_norm:.1f} L/100km frente a un teórico de {prom_teo_norm:.1f} L/100km, "
            "lo que indica un comportamiento alineado a los parámetros de referencia. "
            f"En contraste, las unidades en estado A AUDITAR presentan un consumo medio de "
            f"{prom_real_aud:.1f} L/100km versus {prom_teo_aud:.1f} L/100km teóricos, "
            "configurando un desvío sistemático que justifica investigación operativa."
        )

        texto3 = (
            f"Los desvíos se concentran principalmente en el modelo {modelo_mayor_incidente} "
            "dentro del grupo A AUDITAR, lo que sugiere revisar calibración, condiciones de carga, "
            "topografía recorrida y hábitos de conducción asociados. "
            f"En paralelo, el estado DUDOSO, con un {pct_dudoso:.1f}% de unidades, se focaliza en el modelo "
            f"{modelo_dudoso_principal}, indicando posible subregistro de kilómetros o datos incompletos de GPS."
        )

        if pct_sin_datos > 0:
            texto4 = (
                f"El {pct_sin_datos:.1f}% de unidades en estado SIN DATOS reduce la capacidad analítica del modelo. "
                "A medida que se incorporen más días de operación con registros completos de kilómetros y combustible, "
                "los indicadores tenderán a estabilizarse y permitirán una evaluación más fina de la eficiencia "
                "por ruta, modelo y patrón de uso."
            )
        else:
            texto4 = (
                "Actualmente no se registran unidades en estado SIN DATOS, lo que refuerza la calidad de la base de "
                "información. A medida que se incorporen más días de operación, será posible afinar todavía más la "
                "evaluación de eficiencia por ruta, modelo y patrón de uso."
            )

        story.append(Paragraph(texto1, estilos["Normal"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(texto2, estilos["Normal"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(texto3, estilos["Normal"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(texto4, estilos["Normal"]))
        story.append(Spacer(1, 12))
    else:
        story.append(Paragraph(
            "No se generó análisis técnico debido a la ausencia de datos en el conjunto filtrado.",
            estilos["Normal"]
        ))
        story.append(Spacer(1, 12))

    # Footer
    story.append(Paragraph(
        "Sistema de Control Inteligente de Consumo – Grupo BCA",
        estilos["Normal"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# Botón de descarga en Streamlit
pdf_buffer = generar_pdf_premium(
    salida_filtrada,
    normal,
    auditar,
    dudoso,
    sin_datos,
    pct_normal,
    resumen_est
)

st.download_button(
    label="📄 Descargar tablero en PDF",
    data=pdf_buffer,
    file_name="control_consumo_bca.pdf",
    mime="application/pdf"
)


# ==========================
# 15) RESUMEN DE ESTADOS (DASHBOARD)
# ==========================

st.subheader("Resumen de estados")

resumen = (
    salida_filtrada["ESTADO"]
    .value_counts()
    .rename_axis("Estado")
    .reset_index(name="Cantidad")
)

orden = ["A AUDITAR", "DUDOSO", "NORMAL",
         "FALTA CARGA", "ERROR DE KM", "SIN MOVIMIENTO", "SIN DATOS"]
resumen["orden"] = resumen["Estado"].apply(lambda x: orden.index(x) if x in orden else 999)
resumen = resumen.sort_values("orden")

colores_estado = {
    "A AUDITAR": "🔴",
    "DUDOSO": "🔵",
    "NORMAL": "🟢",
    "FALTA CARGA": "🟣",
    "ERROR DE KM": "⚠️",
    "SIN MOVIMIENTO": "⚪",
    "SIN DATOS": "🟡"
}

for _, row in resumen.iterrows():
    st.markdown(f"### {colores_estado[row['Estado']]} {row['Estado']}: {row['Cantidad']}")

# ==========================
# 16) FOOTER DASHBOARD
# ==========================

st.write("---")
st.caption("Sistema de Control Inteligente de Consumo – Grupo BCA · Versión PDF Premium 2.0")