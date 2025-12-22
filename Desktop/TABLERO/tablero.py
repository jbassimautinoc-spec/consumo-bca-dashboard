# -*- coding: utf-8 -*-

import os
from io import BytesIO
import hashlib
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
import streamlit as st

st.set_page_config(
    page_title="Tablero EMPRESA PROPIA",
    page_icon="🚛",
    layout="wide"
)

# -------------------------------
# LOGIN - CORREOS AUTORIZADOS
# -------------------------------
AUTHORIZED_EMAILS = [
    "jbassi@grupobca.com.ar",
    "mcabo@grupobca.com.ar",
    "mmaxit@grupobca.com.ar",
    "mcarmona@grupobca.com.ar",
    "ncabo@grupobca.com.ar",
    "mmanresa@grupobca.com.ar",
    "aescobar@grupobca.com.ar"
]

st.title("🔐 Acceso al Tablero Logístico")

# Estado de login
if "acceso" not in st.session_state:
    st.session_state.acceso = False

# Si todavía no tiene acceso → mostrar login
if not st.session_state.acceso:
    email = st.text_input("Ingrese su correo corporativo")
    login_btn = st.button("Ingresar")

    if login_btn:
        if email.strip().lower() in AUTHORIZED_EMAILS:
            st.success(f"Bienvenido {email}, acceso concedido ✅")
            st.session_state.acceso = True
            st.rerun()
        else:
            st.error("Acceso denegado ❌")
    st.stop()   # ⛔ PARA EL CÓDIGO SI NO TIENE PERMISO

# ======================================================
# CONFIG GENERAL
# ======================================================
st.set_page_config(page_title="Tablero BCA", page_icon="🚛", layout="wide")

FILE_LIQ = "liq_comb.xlsx"
LOGO_PATH = "logo_bca.png"

# Colores corporativos
COLOR_BG = "#f2f6f7"
COLOR_BORDER = "#d9e2e3"
COLOR1 = "#006778"  # principal
COLOR2 = "#009999"  # secundario
COLOR_TEXT = "#1A1A1A"

# Reglas
CLIENTES_EXC = ["QUEBRACHO BLANCO SRL", "QUEBRACHO BLANDO SRL"]
MATS_VALIDOS = ["ARENA", "PIEDRA", "YESO"]
VACIOS = {"", ".", "NAN", "NONE", "0"}

# ======================================================
# ESTILO
# ======================================================
st.markdown(
    f"""
<style>
.bca-banner {{
    background: linear-gradient(90deg, {COLOR1} 0%, {COLOR2} 100%);
    padding: 18px 22px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 16px;
}}
.bca-banner h1 {{
    color: white;
    margin: 0;
    font-size: 28px;
    font-weight: 800;
}}
.bca-banner h3 {{
    color: rgba(255,255,255,0.9);
    margin: 0;
    font-size: 16px;
    font-weight: 500;
}}
.metric-card {{
    padding: 16px;
    border-radius: 12px;
    background-color: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
}}
.metric-title {{
    color: {COLOR_TEXT};
    font-size: 14px;
    margin-bottom: 4px;
}}
.metric-value {{
    font-size: 28px;
    font-weight: 800;
    color: {COLOR1};
}}
hr {{
    border: none;
    border-top: 1px solid {COLOR_BORDER};
    margin: 12px 0 16px;
}}
</style>
""",
    unsafe_allow_html=True
)

# Header con logo
banner_cols = st.columns([1, 6])
with banner_cols[0]:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.write("")
with banner_cols[1]:
    st.markdown(
        """
    <div class="bca-banner">
        <div style="display:flex;flex-direction:column;">
            <h1>Tablero Logístico BCA</h1>
            <h3>Monitoreo de viajes, toneladas y valorización</h3>
        </div>
    </div>
    """,
        unsafe_allow_html=True
    )

st.markdown("<hr />", unsafe_allow_html=True)

# Debug base
try:
    st.info(
        f"DEBUG · Base modificada: "
        f"{datetime.fromtimestamp(os.path.getmtime(FILE_LIQ)).strftime('%d/%m/%Y')}"
    )
except Exception:
    st.info("DEBUG · No se pudo leer fecha de modificación")

# ======================================================
# HELPERS
# ======================================================
def norm_col_name(x: str) -> str:
    return (
        str(x).strip().upper()
        .replace(" ", "").replace("_", "")
        .replace(".", "").replace("/", "")
        .replace("-", "")
    )

def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    colmap = {norm_col_name(c): c for c in df.columns}
    for cand in candidates:
        key = norm_col_name(cand)
        if key in colmap:
            return colmap[key]
    return None

def safe_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str)
    return out

def es_vacio_series(s: pd.Series) -> pd.Series:
    return (
        s.isna() |
        s.astype(str).str.strip().str.upper().isin(list(VACIOS))
    )

# ======================================================
# CARGA BASE
# ======================================================
@st.cache_data(show_spinner=False)
def cargar_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path)

try:
    df_raw = cargar_excel(FILE_LIQ)
except Exception as e:
    st.error(f"No se pudo cargar {FILE_LIQ}: {e}")
    st.stop()

# ======================================================
# MAPEO A NOMBRES CANÓNICOS (para soportar variaciones)
# ======================================================
COL_SALIDA   = pick_col(df_raw, ["Salida"])
COL_CLIENTE  = pick_col(df_raw, ["Cliente"])
COL_MAT      = pick_col(df_raw, ["Carga/Material", "CargaMaterial", "Carga_Material"])
COL_FLETERO  = pick_col(df_raw, ["Fletero", "Transporte/Fletero", "Transporte / Fletero"])
COL_REMITO   = pick_col(df_raw, ["Remito", "Remitos"])
COL_CUMPLIDO = pick_col(df_raw, ["Cumplido"])
COL_RENDIDO  = pick_col(df_raw, ["Rendido"])
COL_TN       = pick_col(df_raw, ["TnFactu", "TNFACTU", "TNFACTURADA", "Cant Facturar", "Neto Salida"])
COL_VAL      = pick_col(df_raw, ["Total Val. Clientes", "Tarifa Cliente", "TotalValClientes"])

COL_UN          = pick_col(df_raw, ["U.Negocio", "UNegocio", "U_Negocio"])
COL_COMP_COMPRA = pick_col(df_raw, ["Comp.Compra", "CompCompra", "Comp_Compra", "Comp Compra"])
COL_COMP_VENTA  = pick_col(df_raw, ["CompVenta", "Comp.Venta", "Comp_Venta", "Comp Venta"])
COL_ORDSERV     = pick_col(df_raw, ["OrdServicio", "OrdenServicio", "Ord_Servicio", "OS"])

required = {
    "Salida": COL_SALIDA,
    "Cliente": COL_CLIENTE,
    "Carga/Material": COL_MAT,
    "Fletero": COL_FLETERO,
    "Remito": COL_REMITO,
    "Cumplido": COL_CUMPLIDO,
    "Rendido": COL_RENDIDO,
    "TnFactu": COL_TN,
    "Total Val. Clientes": COL_VAL,
}
missing = [k for k, v in required.items() if v is None]
if missing:
    st.error("Faltan columnas requeridas en liq_comb.xlsx: " + ", ".join(missing))
    st.stop()

df = df_raw.copy()

df = df.rename(columns={
    COL_SALIDA: "Salida",
    COL_CLIENTE: "Cliente",
    COL_MAT: "Carga/Material",
    COL_FLETERO: "Fletero",
    COL_REMITO: "Remito",
    COL_CUMPLIDO: "Cumplido",
    COL_RENDIDO: "Rendido",
    COL_TN: "TnFactu",
    COL_VAL: "Total Val. Clientes",
})

# Opcionales
if COL_UN:
    df = df.rename(columns={COL_UN: "U.Negocio"})
else:
    df["U.Negocio"] = ""

if COL_COMP_COMPRA:
    df = df.rename(columns={COL_COMP_COMPRA: "Comp.Compra"})
else:
    df["Comp.Compra"] = ""

if COL_COMP_VENTA:
    df = df.rename(columns={COL_COMP_VENTA: "CompVenta"})
else:
    df["CompVenta"] = ""

if COL_ORDSERV:
    df = df.rename(columns={COL_ORDSERV: "OrdServicio"})
else:
    df["OrdServicio"] = ""

# ======================================================
# NORMALIZACIÓN
# ======================================================
df["Salida"] = pd.to_datetime(df["Salida"], errors="coerce", dayfirst=True)
df["Fecha_norm"] = df["Salida"].dt.date

TEXT_COLS = ["Carga/Material", "Cliente", "U.Negocio", "Fletero", "Remito", "Cumplido", "Comp.Compra", "CompVenta", "OrdServicio"]
for col in TEXT_COLS:
    df[col] = df[col].fillna("").astype(str).str.upper().str.strip().replace({"NAN": "", "NONE": ""})

# numéricos
df["TnFactu"] = df["TnFactu"].astype(str).str.replace(",", ".", regex=False)
df["TnFactu"] = pd.to_numeric(df["TnFactu"], errors="coerce").fillna(0)

df["Total Val. Clientes"] = df["Total Val. Clientes"].astype(str).str.replace(",", ".", regex=False)
df["Total Val. Clientes"] = pd.to_numeric(df["Total Val. Clientes"], errors="coerce").fillna(0)

df["rendido_num"] = pd.to_numeric(df.get("Rendido", 0), errors="coerce").fillna(0).astype(int)

# derivados
df["Remito"] = df["Remito"].fillna("").astype(str).str.upper().str.strip()
df["remito_vacio_bool"] = df["Remito"].isin(VACIOS)

ord_num = (
    df["OrdServicio"].astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
df["OrdServicio_num"] = pd.to_numeric(ord_num, errors="coerce").fillna(0)

# ======================================================
# FILTROS (GLOBAL)
# ======================================================
st.sidebar.header("Filtros")

if "filters_initialized" not in st.session_state:
    st.session_state.fi_user = df["Fecha_norm"].min()
    st.session_state.ff_user = df["Fecha_norm"].max()
    # inicializar selecciones por primera vez
    st.session_state["f_cli"] = []
    st.session_state["f_mat"] = []
    st.session_state["f_un"]  = []
    st.session_state["_prev_date_range"] = (st.session_state.fi_user, st.session_state.ff_user)
    st.session_state.filters_initialized = True

fi_user = st.sidebar.date_input("Desde", value=st.session_state.fi_user, key="fi_user")
ff_user = st.sidebar.date_input("Hasta", value=st.session_state.ff_user, key="ff_user")

if fi_user > ff_user:
    st.sidebar.error("⚠ Rango de fechas inválido")
    st.stop()

# rango cambió: actualizar ancla pero NO borrar selecciones
prev_range = st.session_state.get("_prev_date_range")
curr_range = (fi_user, ff_user)
if prev_range != curr_range:
    st.session_state["_prev_date_range"] = curr_range

# aplicar fecha
df_fecha = df[
    df["Fecha_norm"].notna() &
    (df["Fecha_norm"] >= fi_user) &
    (df["Fecha_norm"] <= ff_user)
].copy()

clientes_opt = sorted([x for x in df_fecha["Cliente"].unique() if str(x).upper() not in ["NAN", "NONE", ""]])
mats_opt     = sorted([x for x in df_fecha["Carga/Material"].unique() if str(x).upper() not in ["NAN", "NONE", ""]])
un_opt       = sorted([x for x in df_fecha["U.Negocio"].unique() if str(x).upper() not in ["NAN", "NONE", ""]])

# --- FIX DEFINITIVO: sincronizar defaults con opciones ---
def sync_default(key: str, options: list) -> list:
    # Cuando opciones está vacío, default debe ser []
    if not options:
        st.session_state[key] = []
        return []
    sel = st.session_state.get(key, [])
    # mantener solo valores existentes en options
    sel = [x for x in sel if x in options]
    # si quedó vacío, usar todos por defecto
    if not sel:
        sel = options
    st.session_state[key] = sel
    return sel

default_cli = sync_default("f_cli", clientes_opt)
default_mat = sync_default("f_mat", mats_opt)
default_un  = sync_default("f_un",  un_opt)

f_cli = st.sidebar.multiselect("Cliente", options=clientes_opt, default=default_cli, key="f_cli")
f_mat = st.sidebar.multiselect("Material", options=mats_opt, default=default_mat, key="f_mat")
f_un  = st.sidebar.multiselect("U. Negocio", options=un_opt, default=default_un, key="f_un")

# Si el usuario borra todo manualmente, aseguramos "todos"
f_cli_eff = f_cli if f_cli else clientes_opt
f_mat_eff = f_mat if f_mat else mats_opt
f_un_eff  = f_un  if f_un  else un_opt

# ===========================
# DATAFRAME FILTRADO FINAL (ÚNICA FUENTE)
# ===========================
df_filtrado = df_fecha[
    (df_fecha["Cliente"].isin(f_cli_eff)) &
    (df_fecha["Carga/Material"].isin(f_mat_eff)) &
    (df_fecha["U.Negocio"].isin(f_un_eff))
].copy()

# ANCLA REACTIVA – NO BORRAR
_ = (fi_user, ff_user, tuple(f_cli_eff), tuple(f_mat_eff), tuple(f_un_eff))

# Recalcular derivados sobre df_filtrado
df_filtrado["Remito"] = df_filtrado["Remito"].fillna("").astype(str).str.upper().str.strip()
df_filtrado["remito_vacio_bool"] = df_filtrado["Remito"].isin(VACIOS)
df_filtrado["rendido_num"] = pd.to_numeric(df_filtrado.get("Rendido", 0), errors="coerce").fillna(0).astype(int)
df_filtrado["Cumplido_norm"] = df_filtrado.get("Cumplido", "").fillna("").astype(str).str.upper().str.strip()

ord_num_f = (
    df_filtrado.get("OrdServicio", "")
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
df_filtrado["OrdServicio_num"] = pd.to_numeric(ord_num_f, errors="coerce").fillna(0)

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.caption(f"📊 Registros encontrados: {len(df_filtrado):,}")

# ======================================================
# TABS
# ======================================================
tab1, tab2, tab3, tab4 = st.tabs(["📊 KPIs", "📦 Materiales", "🚚 Fleteros", "🔍 Auditoría"])

# ======================================================
# TAB 1 – KPIs + GRÁFICA
# ======================================================
with tab1:
    st.header("📊 KPIs generales")

    df_kpi = df_filtrado[~df_filtrado["Cliente"].isin(["QUEBRACHO BLANCO SRL"])].copy()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="metric-card"><div class="metric-title">Viajes</div>'
            f'<div class="metric-value">{len(df_kpi):,}</div></div>',
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            '<div class="metric-card"><div class="metric-title">Toneladas</div>'
            f'<div class="metric-value">{df_kpi["TnFactu"].sum():,.0f}</div></div>',
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            '<div class="metric-card"><div class="metric-title">Valorización</div>'
            f'<div class="metric-value">$ {df_kpi["Total Val. Clientes"].sum():,.0f}</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<hr />", unsafe_allow_html=True)

    st.subheader("📈 Evolución diaria – Arena vs Piedra (Viajes)")
    df_g = df_filtrado[df_filtrado["Carga/Material"].isin(["ARENA", "PIEDRA"])].copy()

    if not df_g.empty:
        chart_df = (
            df_g.groupby(["Fecha_norm", "Carga/Material"])
            .size()
            .reset_index(name="Viajes")
        )
        chart = alt.Chart(chart_df).mark_line(point=True).encode(
            x=alt.X("Fecha_norm:T", title="Fecha"),
            y=alt.Y("Viajes:Q", title="Viajes"),
            color=alt.Color("Carga/Material:N", title="Material")
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No hay datos de arena/piedra en este rango.")

# ======================================================
# TAB 2 – MATERIALES
# ======================================================
with tab2:
    st.header("📦 Materiales (Arena / Piedra / Yeso)")

    df_m = df_filtrado[df_filtrado["Carga/Material"].isin(MATS_VALIDOS)].copy()

    for m in MATS_VALIDOS:
        d = df_m[df_m["Carga/Material"] == m].copy()
        if d.empty:
            continue

        st.subheader(m)
        c1, c2, c3 = st.columns(3)
        c1.metric("Viajes", f"{len(d):,}")
        c2.metric("Toneladas", f"{d['TnFactu'].sum():,.0f}")
        c3.metric("Valorización", f"$ {d['Total Val. Clientes'].sum():,.0f}")

        tabla = (
            d.groupby("Cliente", dropna=False)
             .agg(
                viajes=("Cliente", "size"),
                toneladas=("TnFactu", "sum"),
                valorizacion=("Total Val. Clientes", "sum")
             )
             .sort_values("toneladas", ascending=False)
             .reset_index()
        )
        st.dataframe(safe_df_for_display(tabla), use_container_width=True)
        st.markdown("<hr />", unsafe_allow_html=True)

# ======================================================
# TAB 3 – FLETEROS
# ======================================================
with tab3:
    st.header("🚚 Ranking Fleteros (Toneladas)")

    rk = (
        df_filtrado.groupby("Fletero", dropna=False)["TnFactu"]
        .sum()
        .reset_index()
        .sort_values("TnFactu", ascending=False)
    )
    st.dataframe(safe_df_for_display(rk), use_container_width=True)

# ======================================================
# TAB 4 – AUDITORÍA
# ======================================================
with tab4:
    st.header("🔍 Auditoría")

    df_aud_base = df_filtrado.copy()
    df_no_quebracho = df_aud_base[~df_aud_base["Cliente"].isin(["QUEBRACHO BLANCO SRL"])].copy()

    # A) Sin remito (solo materiales válidos)
    df_a = df_no_quebracho[
        df_no_quebracho["remito_vacio_bool"] &
        df_no_quebracho["Carga/Material"].isin(MATS_VALIDOS)
    ].copy()

    # B) No rendidos
    df_b = df_no_quebracho[df_no_quebracho["rendido_num"] == 0].copy()

    # C) No cumplidos
    df_c = df_no_quebracho[df_no_quebracho["Cumplido_norm"].isin(["", "NO", "0", "FALSE", "N"])].copy()

    # D) Toneladas inválidas (0, 33, 33.33)
    df_d = df_no_quebracho[df_no_quebracho["TnFactu"].isin([0, 33, 33.33])].copy()

    # E) Sin líquido producto (Comp.Compra vacío)
    df_liq_1 = df_no_quebracho[
        es_vacio_series(df_no_quebracho["Comp.Compra"]) &
        (~df_no_quebracho["Cliente"].isin(CLIENTES_EXC)) &
        (~df_no_quebracho["Fletero"].isin(["EMPRESA PROPIA"]))
    ].copy()

    # F) Facturas sin asociar (CompVenta vacío)
    df_liq_2 = df_no_quebracho[
        es_vacio_series(df_no_quebracho["CompVenta"]) &
        (~df_no_quebracho["Cliente"].isin(CLIENTES_EXC))
    ].copy()

    # G) OS pendiente
    df_liq_3 = df_no_quebracho[
        (df_no_quebracho["OrdServicio_num"].notna()) &
        (df_no_quebracho["OrdServicio_num"] != 0) &
        (es_vacio_series(df_no_quebracho["Comp.Compra"])) &
        (~df_no_quebracho["Fletero"].isin(["EMPRESA PROPIA"]))
    ].copy()

    # Métricas
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("S/ remito", len(df_a))
    c2.metric("No rendidos", len(df_b))
    c3.metric("No cumplidos", len(df_c))
    c4.metric("Toneladas inválidas", len(df_d))
    c5.metric("Sin líquido producto", len(df_liq_1))
    c6.metric("Factura sin asociar", len(df_liq_2))
    c7.metric("OS pendiente", len(df_liq_3))

    st.markdown("<hr />", unsafe_allow_html=True)

    # Secciones + export individual
    secciones = [
        ("A) Viajes sin remito", df_a, "sin_remito.xlsx"),
        ("B) Viajes no rendidos", df_b, "no_rendidos.xlsx"),
        ("C) Viajes no cumplidos", df_c, "no_cumplidos.xlsx"),
        ("D) Toneladas inválidas", df_d, "toneladas_invalidas.xlsx"),
        ("E) Sin líquido producto", df_liq_1, "liq_sin_liquido_producto.xlsx"),
        ("F) Factura sin asociar", df_liq_2, "liq_factura_sin_asociar.xlsx"),
        ("G) OS pendiente", df_liq_3, "liq_os_pendiente.xlsx"),
    ]

    for titulo, df_x, nombre in secciones:
        st.subheader(titulo)
        st.metric("Total", 0 if df_x is None else len(df_x))
        if df_x is not None and not df_x.empty:
            st.dataframe(safe_df_for_display(df_x), use_container_width=True)
            buf = BytesIO()
            df_x.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                "⬇ Exportar",
                buf,
                nombre,
                key=f"dl_{hashlib.md5(nombre.encode()).hexdigest()}"
            )
        else:
            st.info("Sin registros con los filtros actuales.")
        st.markdown("<hr />", unsafe_allow_html=True)

    # Exportación completa
    st.subheader("📦 Exportación completa de Auditoría")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_a.to_excel(writer, sheet_name="A_Sin_remito", index=False)
        df_b.to_excel(writer, sheet_name="B_No_rendidos", index=False)
        df_c.to_excel(writer, sheet_name="C_No_cumplidos", index=False)
        df_d.to_excel(writer, sheet_name="D_Tn_invalidas", index=False)
        df_liq_1.to_excel(writer, sheet_name="E_Sin_liquido", index=False)
        df_liq_2.to_excel(writer, sheet_name="F_Fact_sin_asoc", index=False)
        df_liq_3.to_excel(writer, sheet_name="G_OS_pendiente", index=False)

    output.seek(0)
    st.download_button("📥 Exportar Auditoría completa (Excel)", output, "auditoria_completa.xlsx")

st.caption("Tablero Logístico BCA – Base única (liq_comb.xlsx)")
