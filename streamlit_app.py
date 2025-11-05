import os
import time
import json
import re
import random
import streamlit as st
from collections import deque
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
import snap7, os
print("snap7 file:", snap7.__file__)
d = os.path.dirname(snap7.__file__)
print("dir:", d)
# Intentar importar snap7 (opcional)

try:
    import snap7
    print("OK:", snap7)
except Exception:
    import traceback
    traceback.print_exc()

st.set_page_config(page_title="PLC DB4 — Streamlit (rotativo)", layout="wide")
st.title("Lectura continua DB4 — Rotación POR turnos")

# --- Configuración básica en sidebar ---
with st.sidebar.form("config"):
    db_number = st.number_input("DB number", min_value=1, value=4)
    update_interval = st.number_input("Intervalo lectura (s)", min_value=1, value=5)
    max_points = st.number_input("Máx puntos gráfica", min_value=10, value=200)
    save_interval_minutes = st.number_input("Intervalo guardado (min)", min_value=1, value=2)
    csv_base_dir = st.text_input("Carpeta base CSV", value="data")
    operator_name = st.text_input("Operador", value="operador")
    default_shifts = [
        {"name": "Mañana", "start": "06:00"},
        {"name": "Tarde", "start": "14:00"},
        {"name": "Noche", "start": "22:00"}
    ]
    shifts_json = st.text_area("Turnos (JSON)", value=json.dumps(default_shifts, indent=2), height=160)
    simulate = st.checkbox("Modo SIMULACIÓN (no requiere PLC / snap7)", value=not SNAP7_AVAILABLE)
    st.form_submit_button("Aplicar")

SAVE_INTERVAL = int(save_interval_minutes) * 60

# --- TAGS (igual que tu plantilla) ---
TAGS = [
    {"name": "cuenta", "type": "INT", "byte": 0},
    {"name": "itUno", "type": "BOOL", "byte": 2, "bit": 0},
    {"name": "bitdos", "type": "BOOL", "byte": 2, "bit": 1},
    {"name": "startar", "type": "BOOL", "byte": 2, "bit": 2},
    {"name": "stop", "type": "BOOL", "byte": 2, "bit": 3},
    {"name": "reset", "type": "BOOL", "byte": 2, "bit": 4},
    {"name": "start", "type": "BOOL", "byte": 2, "bit": 5},
    {"name": "Presion", "type": "INT", "byte": 4},
    {"name": "nivel", "type": "INT", "byte": 6},
    {"name": "depresion", "type": "INT", "byte": 8},
    {"name": "velMotor1", "type": "INT", "byte": 10},
    {"name": "velMotor2", "type": "INT", "byte": 12},
    {"name": "velMotor3", "type": "INT", "byte": 14},
    {"name": "posActuadorAir", "type": "INT", "byte": 16},
    {"name": "posActfuel", "type": "INT", "byte": 18},
    {"name": "posActH20", "type": "INT", "byte": 20},
]

# calcular tamaño a leer
max_byte = 0
for t in TAGS:
    b = t["byte"]
    size = 1 if t["type"] == "BOOL" else 2
    if b + size > max_byte:
        max_byte = b + size
read_size = max(1, max_byte)

# Estado
if "last_save_ts" not in st.session_state:
    st.session_state.last_save_ts = 0.0
if "running" not in st.session_state:
    st.session_state.running = False
if "client" not in st.session_state and SNAP7_AVAILABLE and not simulate:
    st.session_state.client = snap7.client.Client()

# UI layout
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Iniciar"):
        st.session_state.running = True
    if st.button("Detener"):
        st.session_state.running = False
    st.write("Modo:", "SIMULACIÓN" if simulate else ("snap7 disponible" if SNAP7_AVAILABLE else "snap7 NO disponible"))
    st.write(f"Guardar cada {save_interval_minutes} min en {csv_base_dir}")

with col2:
    chart_placeholder = st.empty()
    table_placeholder = st.empty()
    bools_placeholder = st.empty()
    status_placeholder = st.empty()

numeric_names = [t["name"] for t in TAGS if t["type"] != "BOOL" and t["name"] != "cuenta"]
from collections import deque
history = {name: deque(maxlen=max_points) for name in numeric_names}
timestamps = deque(maxlen=max_points)

# utilidades (idénticas a las tuyas)
def parse_shifts(sh_json):
    try:
        parsed = json.loads(sh_json)
        out = []
        for entry in parsed:
            nm = entry.get("name")
            ststr = entry.get("start")
            if not nm or not ststr:
                raise ValueError("Cada turno necesita 'name' y 'start'")
            hh, mm = map(int, ststr.split(":"))
            out.append({"name": nm, "start": dt_time(hh, mm)})
        out.sort(key=lambda x: (x["start"].hour, x["start"].minute))
        return out
    except Exception:
        return [
            {"name": "Mañana", "start": dt_time(6, 0)},
            {"name": "Tarde", "start": dt_time(14, 0)},
            {"name": "Noche", "start": dt_time(22, 0)},
        ]

def get_current_shift(now_dt, shifts):
    today = now_dt.date()
    t_times = [s["start"] for s in shifts]
    starts = [datetime.combine(today, tt) for tt in t_times]
    starts_next = starts + [starts[0] + timedelta(days=1)]
    for i in range(len(starts)):
        if starts[i] <= now_dt < starts_next[i + 1]:
            return shifts[i]["name"], starts[i]
    last_index = len(starts) - 1
    return shifts[last_index]["name"], starts[last_index]

def sanitize_filename_component(s):
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    if not s:
        s = "unknown"
    return s

def make_shift_filename(base_dir, operator, shift_name, shift_start_dt):
    date_str = shift_start_dt.strftime("%Y%m%d")
    op = sanitize_filename_component(operator)
    sh = sanitize_filename_component(shift_name)
    fname = f"turno_{date_str}_{sh}_{op}.csv"
    return os.path.join(base_dir, fname)

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"No se puede crear carpeta {path}: {e}")

def append_to_csv(filename, row_dict):
    try:
        file_exists = os.path.exists(filename)
        df = pd.DataFrame([row_dict])
        df.to_csv(filename, mode='a', header=not file_exists, index=False, encoding='utf-8')
        return True, None
    except Exception as e:
        return False, str(e)

def simulate_row():
    row = {}
    for t in TAGS:
        if t["type"] == "BOOL":
            row[t["name"]] = random.choice([True, False])
        elif t["type"] == "INT":
            row[t["name"]] = random.randint(0, 200)
        else:
            row[t["name"]] = None
    return row

def parse_tags(data):
    if simulate or not SNAP7_AVAILABLE:
        return simulate_row()
    row = {}
    for t in TAGS:
        name = t["name"]
        if t["type"] == "BOOL":
            row[name] = bool(get_bool(data, t["byte"], t.get("bit", 0)))
        elif t["type"] == "INT":
            row[name] = int(get_int(data, t["byte"]))
        else:
            row[name] = None
    return row

def read_db_bytes(client, db_num, start, size):
    if simulate or not SNAP7_AVAILABLE:
        # no-op for simulation
        return None
    try:
        if not client.get_connected():
            client.connect("192.168.0.10", 0, 1)
        return client.db_read(int(db_num), int(start), int(size))
    except Exception:
        try:
            client.disconnect()
        except:
            pass
        client.connect("192.168.0.10", 0, 1)
        return client.db_read(int(db_num), int(start), int(size))

def render_bool_list(row, placeholder):
    bool_tags = [t for t in TAGS if t["type"] == "BOOL"]
    lines = []
    for t in bool_tags:
        name = t["name"]
        val = bool(row.get(name, False))
        emoji = "🟢" if val else "🛑"
        lines.append(f"{emoji}  {name}")
    md = "\n\n".join(lines)
    placeholder.markdown("### Señales BOOL\n" + md)

def run_loop():
    status_placeholder.info("Arrancando lectura...")
    client = st.session_state.get("client")
    shifts = parse_shifts(shifts_json)
    try:
        ensure_dir(csv_base_dir)
    except RuntimeError as e:
        status_placeholder.error(str(e))
        st.session_state.running = False
        return

    # lectura inicial para UI
    try:
        data_init = read_db_bytes(client, db_number, 0, read_size)
        row_init = parse_tags(data_init)
        render_bool_list(row_init, bools_placeholder)
        display_row = {k: v for k, v in row_init.items() if k != "cuenta"}
        table_placeholder.table(pd.DataFrame([display_row], index=[pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")]))
    except Exception:
        bools_placeholder.markdown("<div style='color:#666'>No se pudo leer aún los BOOLs.</div>", unsafe_allow_html=True)

    while st.session_state.running:
        now = datetime.now()
        ts = pd.Timestamp.now()
        try:
            data = read_db_bytes(client, db_number, 0, read_size)
        except Exception as e:
            status_placeholder.error(f"Error lectura: {e}")
            time.sleep(1)
            continue

        row = parse_tags(data)
        render_bool_list(row, bools_placeholder)

        for name in numeric_names:
            history[name].append(row.get(name))
        timestamps.append(ts)

        display_row = {k: v for k, v in row.items() if k != "cuenta"}
        table_placeholder.table(pd.DataFrame([display_row], index=[ts.strftime("%Y-%m-%d %H:%M:%S")]))

        df = pd.DataFrame({name: list(history[name]) for name in numeric_names})
        df.index = list(timestamps)
        chart_placeholder.line_chart(df)

        shift_name, shift_start_dt = get_current_shift(now, shifts)
        csv_filename = make_shift_filename(csv_base_dir, operator_name, shift_name, shift_start_dt)

        now_ts = time.time()
        if (now_ts - st.session_state.last_save_ts) >= SAVE_INTERVAL:
            save_row = {"timestamp": ts.strftime("%Y-%m-%d %H:%M:%S")}
            for t in TAGS:
                if t["name"] == "cuenta":
                    continue
                save_row[t["name"]] = row.get(t["name"])
            save_row["turno"] = shift_name
            save_row["operador"] = operator_name

            try:
                ensure_dir(os.path.dirname(csv_filename) or ".")
            except RuntimeError as e:
                status_placeholder.error(str(e))
                time.sleep(1)
                continue

            success, err = append_to_csv(csv_filename, save_row)
            if success:
                status_placeholder.info(f"Guardado en {csv_filename} @ {save_row['timestamp']}")
                st.session_state.last_save_ts = now_ts
            else:
                status_placeholder.error(f"Error guardando CSV: {err}")

        status_placeholder.info(f"Última lectura: {ts.strftime('%Y-%m-%d %H:%M:%S')}  (turno: {shift_name})")
        sleep_remaining = update_interval
        while sleep_remaining > 0 and st.session_state.running:
            time.sleep(min(0.2, sleep_remaining))
            sleep_remaining -= 0.2

if st.session_state.running:
    run_loop()
else:
    bools_placeholder.markdown("<div style='color:#666'>Pulsa Iniciar para comenzar</div>", unsafe_allow_html=True)
    status_placeholder.info("Pulsa 'Iniciar' para comenzar la lectura.")