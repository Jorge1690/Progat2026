import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import io
import uuid
import sqlite3
import os
import unicodedata

# --- 0. PRE-CONFIGURACIÓN ---
DB_FILE = 'agenda_v21.sqlite'

def get_db_connection_pre(): 
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def get_page_title_from_param():
    try:
        query_params = st.query_params
        edit_id = query_params.get("edit_id", None)
        if edit_id and os.path.exists(DB_FILE):
            conn = get_db_connection_pre()
            c = conn.cursor()
            c.execute("SELECT se_linea, n_pt FROM agenda WHERE id_unico = ?", (edit_id,))
            res = c.fetchone()
            conn.close()
            if res: return f"{res[0]} _{res[1]}"
    except: pass
    return "PROGAT 2026"

st.set_page_config(page_title=get_page_title_from_param(), layout="wide", page_icon="⚡")

# --- 1. BASE DE DATOS ---
def get_db_connection(): return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agenda (
        id_unico TEXT PRIMARY KEY, n_pt TEXT, area_zonal TEXT, area TEXT, tipo TEXT, 
        fecha_inicio TEXT, hora_inicio TEXT, fecha_termino TEXT, hora_termino TEXT, 
        se_linea TEXT, componente TEXT, descripcion TEXT, recurso_op TEXT, 
        programador TEXT, aviso_cen TEXT, sodi TEXT, observacion TEXT, 
        requiere_estudio INTEGER, to1 INTEGER, to2 INTEGER, e1 TEXT, e2 TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, color TEXT)''')
    
    # Crear usuarios por defecto si no existen
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', 'admin123', 'Administrador', '#e74c3c'))
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('visita', 'visita', 'Visita', '#95a5a6'))
    conn.commit()
    conn.close()

# --- GESTIÓN USUARIOS ---
def check_login(u, p):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
    res = c.fetchone(); conn.close()
    return res[0] if res else None

def get_user_color(username):
    if not username: return "#333333"
    username = str(username).strip()
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT color FROM users WHERE username=?", (username,))
    res = c.fetchone(); conn.close()
    return res[0] if res else "#333333"

def get_all_users():
    conn = get_db_connection(); df = pd.read_sql("SELECT * FROM users", conn); conn.close()
    return df

def create_or_update_user(u, p, r, c_hex):
    try:
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO users (username, password, role, color) VALUES (?, ?, ?, ?)", (u, p, r, c_hex))
        conn.commit(); conn.close()
        return True
    except: return False

def delete_user(u):
    conn = get_db_connection(); conn.execute("DELETE FROM users WHERE username=?", (u,)); conn.commit(); conn.close()

# --- LÓGICA AGENDA OPTIMIZADA ---

def update_cell_db(uid, col_name, key):
    try:
        new_value = st.session_state[key]
        idx = st.session_state.data.index[st.session_state.data["ID_UNICO"] == uid]
        if not idx.empty:
            real_idx = idx[0]
            val_for_df = new_value
            if col_name in ["TO1", "TO2"]:
                try: val_for_df = int(new_value)
                except: val_for_df = 0
            elif col_name in ["Hora Inicio", "Hora termino"]:
                val_for_df = str_to_time(new_value)
            
            st.session_state.data.at[real_idx, col_name] = val_for_df

            db_col_map = {
                "N° PT": "n_pt", "Área Zonal - Tercero": "area_zonal", "Área": "area", "Tipo": "tipo", 
                "Fecha inicio": "fecha_inicio", "Hora Inicio": "hora_inicio", "Fecha termino": "fecha_termino", 
                "Hora termino": "hora_termino", "SE o Linea": "se_linea", "Componente": "componente", 
                "Descripción": "descripcion", "Recurso de operación": "recurso_op", "Programador": "programador", 
                "Aviso CEN": "aviso_cen", "SODI": "sodi", "Observación": "observacion", 
                "Requiere Estudio": "requiere_estudio", "TO1": "to1", "TO2": "to2", "E1": "e1", "E2": "e2"
            }
            if col_name in db_col_map:
                db_col = db_col_map[col_name]
                val_for_sql = str(new_value)
                if col_name in ["Hora Inicio", "Hora termino"]:
                     val_for_sql = str_to_time(new_value).strftime("%H:%M:%S")
                conn = get_db_connection()
                conn.execute(f"UPDATE agenda SET {db_col} = ? WHERE id_unico = ?", (val_for_sql, uid))
                conn.commit()
                conn.close()
    except Exception: pass

def save_agenda_to_db_full(df):
    conn = get_db_connection()
    df_save = df.copy()
    df_save = df_save.loc[:, ~df_save.columns.duplicated()]
    df_save['Fecha inicio'] = df_save['Fecha inicio'].astype(str)
    df_save['Fecha termino'] = df_save['Fecha termino'].astype(str)
    df_save['N° PT'] = df_save['N° PT'].astype(str)
    def t_str(t): return t.strftime("%H:%M:%S") if isinstance(t, time) else "00:00:00"
    df_save['Hora Inicio'] = df_save['Hora Inicio'].apply(t_str)
    df_save['Hora termino'] = df_save['Hora termino'].apply(t_str)
    
    col_map = {
        "ID_UNICO": "id_unico", "N° PT": "n_pt", "Área Zonal - Tercero": "area_zonal", "Área": "area", "Tipo": "tipo", 
        "Fecha inicio": "fecha_inicio", "Hora Inicio": "hora_inicio", "Fecha termino": "fecha_termino", 
        "Hora termino": "hora_termino", "SE o Linea": "se_linea", "Componente": "componente", 
        "Descripción": "descripcion", "Recurso de operación": "recurso_op", "Programador": "programador", 
        "Aviso CEN": "aviso_cen", "SODI": "sodi", "Observación": "observacion", 
        "Requiere Estudio": "requiere_estudio", "TO1": "to1", "TO2": "to2", "E1": "e1", "E2": "e2"
    }
    for k in col_map.keys():
        if k not in df_save.columns: df_save[k] = 0 if k in ["TO1","TO2","Requiere Estudio"] else ""
    
    df_save = df_save[list(col_map.keys())] 
    df_save.rename(columns=col_map, inplace=True)
    try: df_save.to_sql('agenda', conn, if_exists='replace', index=False)
    except Exception: pass
    finally: conn.close()

def load_agenda_from_db():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    conn = get_db_connection()
    try: df = pd.read_sql('SELECT * FROM agenda', conn)
    except: return pd.DataFrame()
    conn.close()
    if df.empty: return df
    
    col_map_inv = {
        "id_unico": "ID_UNICO", "n_pt": "N° PT", "area_zonal": "Área Zonal - Tercero", "area": "Área", "tipo": "Tipo", 
        "fecha_inicio": "Fecha inicio", "hora_inicio": "Hora Inicio", "fecha_termino": "Fecha termino", 
        "hora_termino": "Hora termino", "se_linea": "SE o Linea", "componente": "Componente", 
        "descripcion": "Descripción", "recurso_op": "Recurso de operación", "programador": "Programador", 
        "aviso_cen": "Aviso CEN", "sodi": "SODI", "observacion": "Observación", 
        "requiere_estudio": "Requiere Estudio", "to1": "TO1", "to2": "TO2", "e1": "E1", "e2": "E2"
    }
    df.rename(columns=col_map_inv, inplace=True)
    df["Fecha inicio"] = pd.to_datetime(df["Fecha inicio"], errors='coerce').fillna(datetime.now().date()).dt.date
    df["Fecha termino"] = pd.to_datetime(df["Fecha termino"], errors='coerce').fillna(datetime.now().date()).dt.date
    df["Hora Inicio"] = df["Hora Inicio"].apply(str_to_time)
    df["Hora termino"] = df["Hora termino"].apply(str_to_time)
    df["Requiere Estudio"] = df["Requiere Estudio"].apply(lambda x: True if x in [1,'1',True,'True'] else False)
    
    cols_txt = ["N° PT","Programador","Descripción","Aviso CEN","SODI","Área Zonal - Tercero","Área","Tipo","SE o Linea","Componente","Recurso de operación","Observación","E1","E2"]
    for c in cols_txt: 
        if c in df.columns: df[c] = df[c].fillna("").astype(str).replace(["nan","None"], "")
    return df

def reset_db():
    if os.path.exists(DB_FILE): 
        try: os.remove(DB_FILE)
        except: pass
    st.query_params.clear() 
    st.session_state.clear()
    st.rerun()

# --- UTILS ---
def normalize_str(s): return unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode("utf-8").lower().strip()
def fecha_larga(dt): 
    try:
        DIAS={0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
        MESES={1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month]} de {dt.year}"
    except: return str(dt)

def str_to_time(val):
    if isinstance(val, time): return val
    if isinstance(val, datetime): return val.time()
    val = str(val).strip()
    if not val or val == "nan": return time(0,0)
    try: 
        if ":" in val: return datetime.strptime(val, "%H:%M:%S" if len(val.split(":"))==3 else "%H:%M").time()
    except: pass
    return time(0,0)
def safe_strftime(val): return val.strftime("%H:%M") if isinstance(val, time) else "00:00"
def sanitize_filename(text): return str(text).replace("/", "-").replace("\\", "-").replace(":", "")

def format_type(val):
    val_lower = str(val).lower().strip()
    if "conexión" in val_lower or "conexion" in val_lower: return "Dat", "bg-dat"
    if "intervención" in val_lower or "intervencion" in val_lower: return "Interv", "bg-int"
    return val[:10], "bg-oth"

def clean_excel(df):
    rename_map = {"fecha fin":"Fecha termino","hora fin":"Hora termino","fecha inicio":"Fecha inicio","hora inicio":"Hora Inicio","n° pt":"N° PT","pt":"N° PT","área zonal / tercero":"Área Zonal - Tercero","se o línea":"SE o Linea","componente":"Componente","descripción":"Descripción","tipo":"Tipo","área":"Área"}
    df.columns = df.columns.str.strip()
    new_cols = {}
    for col in df.columns:
        norm = normalize_str(col)
        for k,v in rename_map.items(): 
            if norm==normalize_str(k): new_cols[col]=v; break
    df.rename(columns=new_cols, inplace=True)
    if "Fecha inicio" not in df.columns: return pd.DataFrame()
    df["Fecha inicio"] = pd.to_datetime(df["Fecha inicio"], errors='coerce').dt.date
    df["Fecha termino"] = pd.to_datetime(df["Fecha termino"], errors='coerce').dt.date
    for c in ["Hora Inicio","Hora termino"]: df[c] = df[c].apply(str_to_time) if c in df.columns else time(0,0)
    if "N° PT" in df.columns: df["N° PT"] = df["N° PT"].astype(str).replace(["nan","0.0"], "")
    else: df["N° PT"] = ""
    for c in ["Programador","Aviso CEN","SODI","E1","E2","Observación","Área","Tipo","SE o Linea","Componente","Descripción","Área Zonal - Tercero","Recurso de operación"]:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].astype(str).replace(["nan","None","NaT"], "")
    for c in ["TO1","TO2"]:
        if c not in df.columns: df[c] = 0
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df["Requiere Estudio"] = False
    df["ID_UNICO"] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df

def calcular_gantt(row):
    try:
        f = row.get('Fecha inicio')
        if not isinstance(f, (datetime, pd.Timestamp, type(datetime.now().date()))): f = datetime.now().date()
        start = datetime.combine(f, row['Hora Inicio']); end = datetime.combine(f, row['Hora termino'])
        if row['Hora Inicio'] == time(0,0) and row['Hora termino'] == time(0,0): return {"err":False,"l_t1":0,"w_t1":0,"l_wk":0,"w_wk":0,"l_t2":0,"w_t2":0}
        if end < start: return {"err":True}
        to1_s = start - timedelta(hours=int(row['TO1'])); to2_e = end + timedelta(hours=int(row['TO2']))
        def pct(dt): return ((dt.hour * 60 + dt.minute) / 1440.0) * 100
        return {"err":False,"l_t1":max(0, pct(to1_s)),"w_t1":pct(start)-pct(to1_s),"l_wk":max(0, pct(start)),"w_wk":pct(end)-pct(start),"l_t2":max(0, pct(end)),"w_t2":pct(to2_e)-pct(end)}
    except: return {"err":True}

def generar_excel(row):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        campos = ["N° PT","Área Zonal - Tercero","Área","Tipo","Fecha inicio","Hora Inicio","Fecha termino","Hora termino","SE o Linea","Componente","Descripción","Recurso de operación","Programador","Aviso CEN","SODI","Observación","Requiere Estudio"]
        d = {k: row.get(k, "") for k in campos}
        pd.DataFrame(list(d.items()), columns=["Campo","Valor"]).to_excel(writer, sheet_name='Carátula', index=False)
        writer.book.add_worksheet('GM').write('A1', f"GM PT {row['N° PT']}")
    return output.getvalue()

def get_timeline_html():
    html = '<div class="timeline-header">'
    for h in range(24): html += f'<div class="time-label">{h}</div>'
    html += '</div>'
    return html

# --- APP START ---
init_db()
query_params = st.query_params
session_user = query_params.get("session", None)
edit_mode_id = query_params.get("edit_id", None)

if 'logged_in' not in st.session_state:
    if session_user:
        role = check_login(session_user, "dummy")
        users = get_all_users()
        if session_user in users['username'].values:
            u_data = users[users['username']==session_user].iloc[0]
            st.session_state.logged_in = True
            st.session_state.user_role = u_data['role']
            st.session_state.user_name = session_user
        else: st.session_state.logged_in = False
    else: st.session_state.logged_in = False

def login(u, p):
    role = check_login(u, p)
    if role:
        st.session_state.logged_in = True
        st.session_state.user_role = role
        st.session_state.user_name = u
        st.query_params["session"] = u
        st.rerun()
    else: st.error("Incorrecto")

def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.query_params.clear()
    st.rerun()

# 1. LOGIN
if not st.session_state.logged_in:
    c_left, c_center, c_right = st.columns([1, 1, 1], gap="large")
    with c_center:
        st.markdown("<br><h1 style='text-align:center'>⚡ PROGAT 2026</h1>", unsafe_allow_html=True)
        with st.container(border=True):
            with st.form("login"):
                u = st.text_input("Usuario")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("Ingresar", type="primary", use_container_width=True): login(u, p)

# 2. APP LOGUEADA
else:
    # --- MODO EDICIÓN ---
    if edit_mode_id:
        data_full = load_agenda_from_db()
        mask = data_full["ID_UNICO"] == edit_mode_id
        if mask.any():
            row = data_full[mask].iloc[0]
            ssee_pt_title = f"{row['SE o Linea']} _{row['N° PT']}"
            
            st.markdown(f'<div class="edit-header" style="font-size:24px; font-weight:bold; color:#2c3e50; border-bottom:3px solid #3498db; margin-bottom:20px; padding-bottom:10px;">✏️ {ssee_pt_title}</div>', unsafe_allow_html=True)
            
            # Solo editores ven los botones de acción en modo edición
            is_editor = st.session_state.user_role in ["Administrador", "Programador"]
            
            if is_editor:
                c_top1, c_top2, c_top3 = st.columns([6, 2, 2])
                c_top1.info("💡 Modo Edición Detallada.")
                fn = f"{sanitize_filename(row['SE o Linea'])}_{sanitize_filename(row['Componente'])}_{sanitize_filename(row['N° PT'])}_{row['Fecha inicio']}.xlsx"
                c_top2.download_button("📥 Descargar Excel", generar_excel(row), fn, type="primary", use_container_width=True)
                if c_top3.button("❌ Cerrar Edición", use_container_width=True):
                    st.query_params["edit_id"] = ""
                    st.rerun()
            else:
                st.info("🔒 Modo Lectura")
                if st.button("❌ Volver", use_container_width=True):
                    st.query_params["edit_id"] = ""
                    st.rerun()

            with st.form("full_edit_form"):
                st.subheader("Datos Generales")
                c1, c2, c3 = st.columns(3)
                
                # Deshabilitar inputs si es visita
                dis = not is_editor
                
                n_pt = c1.text_input("N° PT", row["N° PT"], disabled=dis)
                n_az = c2.text_input("Área Zonal", row["Área Zonal - Tercero"], disabled=dis)
                n_ar = c3.text_input("Área", row["Área"], disabled=dis)
                
                c4, c5 = st.columns(2)
                n_ti = c4.text_input("Tipo", row["Tipo"], disabled=dis)
                n_re = c5.text_input("Recurso", row["Recurso de operación"], disabled=dis)
                
                st.divider()
                st.subheader("Ubicación y Equipo")
                c6, c7 = st.columns(2)
                n_se = c6.text_input("SE o Línea", row["SE o Linea"], disabled=dis)
                n_co = c7.text_input("Componente", row["Componente"], disabled=dis)
                n_de = st.text_area("Descripción", row["Descripción"], disabled=dis)
                
                st.divider()
                st.subheader("Programación")
                c8, c9, c10, c11 = st.columns(4)
                safe_date_ini = row["Fecha inicio"] if pd.notnull(row["Fecha inicio"]) else datetime.now().date()
                safe_date_fin = row["Fecha termino"] if pd.notnull(row["Fecha termino"]) else datetime.now().date()
                n_fi = c8.date_input("Fecha Inicio", safe_date_ini, disabled=dis)
                n_hi = c9.time_input("Hora Inicio", row["Hora Inicio"], disabled=dis)
                n_ff = c10.date_input("Fecha Fin", safe_date_fin, disabled=dis)
                n_hf = c11.time_input("Hora Fin", row["Hora termino"], disabled=dis)
                
                c12, c13, c14, c15 = st.columns(4)
                n_pr = c12.text_input("Programador", row["Programador"], disabled=dis)
                n_ce = c13.text_input("Aviso CEN", row["Aviso CEN"], disabled=dis)
                n_so = c14.text_input("SODI", row["SODI"], disabled=dis)
                n_rq = c15.checkbox("Requiere Estudio", row["Requiere Estudio"], disabled=dis)
                
                st.divider()
                st.subheader("Operaciones")
                c16, c17, c18, c19 = st.columns(4)
                n_t1 = c16.number_input("TO1", value=int(row["TO1"]), min_value=0, disabled=dis)
                n_e1 = c17.text_input("E1", row["E1"], disabled=dis)
                n_t2 = c18.number_input("TO2", value=int(row["TO2"]), min_value=0, disabled=dis)
                n_e2 = c19.text_input("E2", row["E2"], disabled=dis)
                n_ob = st.text_area("Observación", row["Observación"], disabled=dis)
                
                if is_editor:
                    if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
                        cols_update = {
                            "N° PT":n_pt, "Área Zonal - Tercero":n_az, "Área":n_ar, "Tipo":n_ti,
                            "Recurso de operación":n_re, "SE o Linea":n_se, "Componente":n_co, "Descripción":n_de,
                            "Fecha inicio":n_fi, "Hora Inicio":n_hi, "Fecha termino":n_ff, "Hora termino":n_hf,
                            "Programador":n_pr, "Aviso CEN":n_ce, "SODI":n_so, "Requiere Estudio":n_rq,
                            "TO1":n_t1, "E1":n_e1, "TO2":n_t2, "E2":n_e2, "Observación":n_ob
                        }
                        for k,v in cols_update.items(): data_full.at[data_full.index[mask][0], k] = v
                        save_agenda_to_db_full(data_full)
                        st.success("Guardado exitosamente")
                        st.session_state.data = data_full
                else:
                    st.form_submit_button("Guardar Cambios", disabled=True, use_container_width=True)
        else: st.error("PT no encontrado.")

    # --- VISTA AGENDA ---
    else:
        st.markdown("""
            <style>
            div[data-testid="stTextInput"] { height: 22px; min-height: 22px; margin-bottom: 0px !important; }
            div[data-testid="stTextInput"] > div {
                border: 1px solid transparent !important;
                background-color: transparent !important;
                box-shadow: none !important;
                border-radius: 2px !important;
                min-height: 22px !important;
                height: 22px !important;
            }
            div[data-testid="stTextInput"] input { 
                padding: 0 1px !important; font-size: 11px; font-weight: 500; 
                min-height: 22px !important; height: 22px !important; line-height: 22px !important;
                text-align: center; color: #2c3e50; 
            }
            div[data-testid="stTextInput"] > div:hover,
            div[data-testid="stTextInput"] > div:focus-within {
                border: 1px solid #ccc !important;
                background-color: white !important;
            }
            div[data-testid="stTextInput"] input:disabled { 
                background-color: transparent !important; 
                color: #444; opacity: 1; border: none !important;
            }
            [data-testid="column"] { padding: 0 1px !important; }
            div[data-testid="stHorizontalBlock"] { gap: 0.1rem !important; margin-bottom: 1px !important; border-bottom: 1px solid #f0f0f0; }
            div[data-testid="element-container"] { margin-bottom: 0px !important; }
            
            .gantt-wrapper { 
                width: 100%; height: 22px; background: #ecf0f1; 
                border: 1px solid #bdc3c7; position: relative; overflow: hidden;
                z-index: 0;
            }
            .timeline-header { display: flex; width: 100%; border-bottom: 1px solid #ccc; height: 14px; margin-bottom: 2px; }
            .time-label { width: 4.166666%; font-size: 8px; color: #999; text-align: left; border-left: 1px solid #eee; line-height: 14px; font-weight: 700; padding-left: 1px; }
            
            /* GANTT BARS: ABSOLUTE DIVS CON ESTILOS INLINE */
            
            .desc-tooltip { 
                background-color: transparent; border: 1px solid transparent; 
                height: 22px; padding: 0 2px; font-size: 10px; color: #555; 
                white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; 
                line-height: 20px; cursor: help; box-shadow: none !important; 
                max-width: 100%; display: block;
            }
            .desc-tooltip:hover { border: 1px solid #ccc; background-color: #fff; }
            
            .type-badge { font-weight: 700; font-size: 9px; padding: 0 2px; border-radius: 2px; color: #fff; display:flex; align-items:center; justify-content:center; height: 22px; width: 100%; box-shadow: none !important; }
            .col-header { font-size: 10px; font-weight: 800; color: #7f8c8d; text-align: center; text-transform: uppercase; border-bottom: 2px solid #ddd; margin-bottom: 2px; white-space: nowrap; height: 18px; line-height: 18px; }
            .bg-dat { background-color: #e74c3c; } .bg-int { background-color: #3498db; } .bg-oth { background-color: #95a5a6; } 
            .date-separator { background-color: #2c3e50; color: #fff; padding: 4px 10px; border-radius: 2px; font-weight: 700; margin: 15px 0 5px 0; font-size: 13px; box-shadow: none !important; }
            div[data-testid="column"] button { padding: 0px !important; min-height: 22px !important; height: 22px !important; font-size: 11px !important; border: none; background: transparent; color: #7f8c8d; box-shadow: none !important; }
            div[data-testid="column"] button:hover { color: #3498db; background-color: #f0f8ff; border-radius: 2px; }
            </style>
        """, unsafe_allow_html=True)

        if 'data' not in st.session_state or st.session_state.data.empty:
            st.session_state.data = load_agenda_from_db()
        
        role = st.session_state.user_role
        is_admin = role == "Administrador"
        is_editor = role in ["Administrador", "Programador"]
        
        with st.container(border=True):
            c_head1, c_head2, c_head3 = st.columns([1, 1, 2], gap="medium")
            with c_head1:
                st.write(f"👤 **{st.session_state.user_name}** ({role})")
                if st.button("Cerrar Sesión", key="logout_top", use_container_width=True): logout()
            with c_head2:
                today = datetime.now().date(); default_max = today + timedelta(days=7)
                if not st.session_state.data.empty:
                     max_data = st.session_state.data["Fecha inicio"].max()
                     if pd.isna(max_data) or max_data < today: max_data = default_max
                else: max_data = default_max
                date_filter = st.date_input("Filtro Fechas", value=(today, max_data), label_visibility="collapsed")
            with c_head3:
                c_tools = st.columns(3)
                if is_editor:
                    with c_tools[0].expander("📂 Carga Excel"):
                        up = st.file_uploader("Subir .xlsx", type=["xlsx"], key="up_top")
                        if up:
                            try:
                                ndf = pd.read_excel(up, dtype=str); ndf = clean_excel(ndf)
                                if not ndf.empty:
                                    curr = st.session_state.data
                                    keys_ex = set(zip(curr["N° PT"].astype(str), curr["Fecha inicio"])) if not curr.empty else set()
                                    to_add = []
                                    for _, row in ndf.iterrows():
                                        if pd.isna(row["Fecha inicio"]): continue
                                        if (str(row["N° PT"]), row["Fecha inicio"]) not in keys_ex: to_add.append(row)
                                    if to_add:
                                        df_new = pd.DataFrame(to_add)
                                        st.session_state.data = pd.concat([curr, df_new], ignore_index=True) if not curr.empty else df_new
                                        save_agenda_to_db_full(st.session_state.data); st.success(f"✅ {len(to_add)}"); st.rerun()
                            except Exception as e: st.error(f"Err: {e}")
                    with c_tools[1]:
                        if st.button("➕ Nuevo PT", use_container_width=True):
                            nr = {c: "" for c in st.session_state.data.columns} if not st.session_state.data.empty else {}
                            nr.update({"N° PT":"NUEVO","ID_UNICO":str(uuid.uuid4()),"Fecha inicio":datetime.now().date(),"Hora Inicio":time(8,0),"Hora termino":time(12,0)})
                            st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([nr])], ignore_index=True) if not st.session_state.data.empty else pd.DataFrame([nr])
                            save_agenda_to_db_full(st.session_state.data); st.rerun()
                if is_admin:
                    with c_tools[2].expander("⚙️ Admin - Gestión Usuarios"):
                        if st.button("Borrar DB (Reset Total)"): reset_db()
                        st.markdown("---")
                        st.write("**Lista de Usuarios:**")
                        users_df = get_all_users()
                        if not users_df.empty:
                            for _, u_row in users_df.iterrows():
                                c_u1, c_u2, c_u3, c_u4 = st.columns([2, 2, 2, 1])
                                c_u1.write(f"👤 {u_row['username']}")
                                c_u2.write(f"🔑 {u_row['role']}")
                                c_u3.color_picker("C", u_row['color'], disabled=True, label_visibility="collapsed", key=f"c_read_{u_row['username']}")
                                if c_u4.button("🗑️", key=f"del_{u_row['username']}"):
                                    delete_user(u_row['username'])
                                    st.rerun()
                        st.markdown("---")
                        st.write("**Crear o Editar Usuario:**")
                        with st.form("quick_user"):
                            c_f1, c_f2 = st.columns(2)
                            nu = c_f1.text_input("Usuario (Si existe, se actualiza)")
                            np = c_f2.text_input("Contraseña", type="password")
                            c_f3, c_f4 = st.columns(2)
                            nr = c_f3.selectbox("Rol", ["Programador", "Administrador", "Visita"])
                            nc = c_f4.color_picker("Color Distintivo", "#3498db")
                            if st.form_submit_button("Guardar / Actualizar"): 
                                if nu and np:
                                    create_or_update_user(nu, np, nr, nc)
                                    st.success(f"Usuario {nu} procesado.")
                                    st.rerun()
                                else: st.warning("Datos incompletos.")

        if not st.session_state.data.empty:
            df_v = st.session_state.data.copy()
            if isinstance(date_filter, tuple):
                if len(date_filter)==2: df_v = df_v[(df_v["Fecha inicio"]>=date_filter[0])&(df_v["Fecha inicio"]<=date_filter[1])]
                elif len(date_filter)==1: df_v = df_v[df_v["Fecha inicio"]>=date_filter[0]]
            
            df_v = df_v.sort_values(["Fecha inicio", "Hora Inicio"])
            
            for f in df_v["Fecha inicio"].unique():
                st.markdown(f"<div class='date-separator'>{fecha_larga(f)}</div>", unsafe_allow_html=True)
                cols = st.columns([0.65, 0.30, 0.05], gap="small") 
                
                with cols[0]:
                    sc = st.columns([1.1, 0.5, 0.6, 0.6, 1.0, 1.1, 0.6, 0.8, 0.8, 0.5, 0.6, 0.5, 0.6], gap="small") 
                    headers = ["PT/SE", "Área", "Tipo", "Prog", "Desc", "CEN", "SODI", "Ini", "Fin", "TO1", "E1", "TO2", "E2"]
                    for i, h in enumerate(headers): sc[i].markdown(f"<div class='col-header'>{h}</div>", unsafe_allow_html=True)
                
                with cols[1]: st.markdown(get_timeline_html(), unsafe_allow_html=True)
                with cols[2]: st.markdown("<div class='col-header'>Acc</div>", unsafe_allow_html=True)
                
                for _, row in df_v[df_v["Fecha inicio"]==f].iterrows():
                    uid = row["ID_UNICO"]
                    if uid not in st.session_state.data["ID_UNICO"].values: continue
                    idx = st.session_state.data.index[st.session_state.data["ID_UNICO"]==uid][0]
                    
                    mc = st.columns([0.65, 0.30, 0.05], gap="small")
                    with mc[0]:
                        cc = st.columns([1.1, 0.5, 0.6, 0.6, 1.0, 1.1, 0.6, 0.8, 0.8, 0.5, 0.6, 0.5, 0.6], gap="small")
                        
                        prog_name = row.get('Programador', '')
                        user_color = get_user_color(prog_name)
                        html_pt = f"""<div style='text-align:center; line-height:1.1'><span style='color:{user_color}; font-weight:bold; font-size:12px'>{row['N° PT']}</span><br><span style='color:#7f8c8d; font-size:11px; font-weight:700;'>{row.get('SE o Linea','')}</span></div>"""
                        cc[0].markdown(html_pt, unsafe_allow_html=True)
                        
                        cc[1].text_input("Ar", row.get("Área",""), key=f"ar_{uid}", label_visibility="collapsed", disabled=True)
                        short_type, type_class = format_type(row.get("Tipo",""))
                        cc[2].markdown(f"<span class='type-badge {type_class}'>{short_type}</span>", unsafe_allow_html=True)
                        
                        dis = not is_editor # Bloqueado si NO es editor (Visita)
                        
                        cc[3].text_input("P", row.get("Programador",""), key=f"Programador_{uid}", on_change=update_cell_db, args=(uid, "Programador", f"Programador_{uid}"), disabled=dis, label_visibility="collapsed")
                        
                        desc_text = str(row.get("Descripción","")).replace('"', '&quot;')
                        html_desc = f"""<div class="desc-tooltip" title="{desc_text}">{desc_text}</div>"""
                        cc[4].markdown(html_desc, unsafe_allow_html=True)
                        
                        cc[5].text_input("C", row.get("Aviso CEN",""), key=f"Aviso CEN_{uid}", on_change=update_cell_db, args=(uid, "Aviso CEN", f"Aviso CEN_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[6].text_input("S", row.get("SODI",""), key=f"SODI_{uid}", on_change=update_cell_db, args=(uid, "SODI", f"SODI_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[7].text_input("I", safe_strftime(row["Hora Inicio"]), key=f"Hora Inicio_{uid}", on_change=update_cell_db, args=(uid, "Hora Inicio", f"Hora Inicio_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[8].text_input("F", safe_strftime(row["Hora termino"]), key=f"Hora termino_{uid}", on_change=update_cell_db, args=(uid, "Hora termino", f"Hora termino_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[9].text_input("T1", str(row.get("TO1",0)), key=f"TO1_{uid}", on_change=update_cell_db, args=(uid, "TO1", f"TO1_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[10].text_input("E1", row.get("E1",""), key=f"E1_{uid}", on_change=update_cell_db, args=(uid, "E1", f"E1_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[11].text_input("T2", str(row.get("TO2",0)), key=f"TO2_{uid}", on_change=update_cell_db, args=(uid, "TO2", f"TO2_{uid}"), disabled=dis, label_visibility="collapsed")
                        cc[12].text_input("E2", row.get("E2",""), key=f"E2_{uid}", on_change=update_cell_db, args=(uid, "E2", f"E2_{uid}"), disabled=dis, label_visibility="collapsed")

                    with mc[1]:
                        c_g = calcular_gantt(row)
                        if c_g["err"]: st.markdown("<div class='gantt-wrapper' style='border:1px solid red'></div>", unsafe_allow_html=True)
                        else:
                            # AQUI LA MAGIA: Divs absolutos simples, con estilos inline que NO fallan
                            html_gantt = f"""<div class="gantt-wrapper">
                                <div style="position:absolute; background-color:#28a745; left:{c_g['l_t1']}%; width:{c_g['w_t1']}%; height:14px; top:4px; border-radius:2px; z-index:10; display:flex; align-items:center; justify-content:center; color:white; font-size:9px; font-weight:bold; overflow:hidden;">{row.get('E1','')}</div>
                                <div style="position:absolute; background-color:#fd7e14; left:{c_g['l_wk']}%; width:{c_g['w_wk']}%; height:14px; top:4px; border-radius:2px; z-index:5;"></div>
                                <div style="position:absolute; background-color:#28a745; left:{c_g['l_t2']}%; width:{c_g['w_t2']}%; height:14px; top:4px; border-radius:2px; z-index:10; display:flex; align-items:center; justify-content:center; color:white; font-size:9px; font-weight:bold; overflow:hidden;">{row.get('E2','')}</div>
                            </div>"""
                            st.markdown(html_gantt, unsafe_allow_html=True)

                    with mc[2]:
                        if is_editor:
                            c_acc = st.columns([1,1,1], gap="small")
                            with c_acc[0]: st.link_button("✏️", f"/?session={st.session_state.user_name}&edit_id={uid}", help="Editar")
                            with c_acc[1]: 
                                if st.button("📋", key=f"cp_{uid}", help="Duplicar"):
                                    cp = st.session_state.data.loc[idx].copy()
                                    cp["ID_UNICO"] = str(uuid.uuid4())
                                    cp["N° PT"] = f"{row['N° PT']} (Copia)"
                                    st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([cp])], ignore_index=True)
                                    save_agenda_to_db_full(st.session_state.data); st.rerun()
                            with c_acc[2]:
                                if st.button("🗑️", key=f"rm_{uid}"):
                                    st.session_state.data = st.session_state.data.drop(idx).reset_index(drop=True)
                                    save_agenda_to_db_full(st.session_state.data); st.rerun()
        else: st.info("👋 Agenda vacía para el rango seleccionado.")