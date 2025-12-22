#!/usr/bin/env python3
import os
import subprocess
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# =====================
# CONFIG
# =====================
TV_IP = os.environ.get("TV_IP", "10.0.110.253")
ADB_DEVICE = f"{TV_IP}:5555"
SCRCPY_WEB_URL = "http://10.0.100.73:8000/"

# =====================
# APP
# =====================
app = FastAPI(title="Painel Android TV")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# ADB HELPER
# =====================
def adb(cmd, timeout=8):
    try:
        p = subprocess.run(
            ["adb"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "stdout": p.stdout.decode(errors="ignore"),
            "stderr": p.stderr.decode(errors="ignore"),
            "code": p.returncode,
        }
    except Exception as e:
        return {"error": str(e)}

# =====================
# AUTO RECONNECT
# =====================
async def adb_autoconnect():
    global ADB_DEVICE
    while True:
        out = adb(["devices"])["stdout"]
        if ADB_DEVICE not in out:
            adb(["connect", ADB_DEVICE])
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup():
    asyncio.create_task(adb_autoconnect())

# =====================
# FRONTEND
# =====================
HTML = f"""
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Painel Android TV</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
body {{
  font-family: Arial;
  background: linear-gradient(180deg,#06162e,#0b2c52);
  color:#fff;
  padding:20px;
}}

.container {{ max-width:1100px; margin:auto; }}

.card {{
  background: rgba(255,255,255,0.06);
  padding:14px;
  border-radius:12px;
  margin-bottom:14px;
}}

button {{
  padding:10px 14px;
  border-radius:8px;
  border:0;
  background:#2b9cff;
  color:#fff;
  cursor:pointer;
}}

button.danger {{ background:#e74c3c; }}

.controls {{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}}

.grid {{
  display:grid;
  grid-template-columns:80px 80px 80px;
  gap:6px;
  justify-content:center;
}}

.log {{
  background:rgba(0,0,0,.4);
  height:150px;
  overflow:auto;
  padding:10px;
  border-radius:8px;
  font-size:13px;
}}

.warn {{
  font-size:12px;
  color:#ffd966;
  margin-top:6px;
}}

input {{
  padding:8px;
  border-radius:6px;
  border:0;
}}

/* ===== SCRCPY PANEL ===== */
.scrcpy-panel {{
  width: fit-content;
}}

.scrcpy-resizable {{
  resize: both;
  overflow: hidden;

  width: 520px;
  height: 292px; /* 16:9 */
  min-width: 320px;
  min-height: 180px;

  background:#000;
  border-radius:12px;
  border:1px solid rgba(255,255,255,.1);

  display:flex;
  align-items:center;
  justify-content:center;
}}

.scrcpy-frame {{
  width:1280px;
  height:720px;
  border:0;
  transform-origin:center center;
  pointer-events:none; /* controle só pelos botões */
}}
</style>
</head>

<body>
<div class="container">

<h2>Painel ADB – Android TV</h2>

<div class="card controls">
  <input id="ip" placeholder="IP da TV" />
  <button onclick="setIp()">Set IP</button>
  <button onclick="connect()">Connect</button>
  <button onclick="status()">Status</button>
</div>

<div class="card controls">
  <button onclick="key(3)">Home</button>
  <button onclick="key(4)">Back</button>
  <button onclick="key(26)">Power</button>
  <button onclick="key(24)">Vol +</button>
  <button onclick="key(25)">Vol -</button>
  <button onclick="key(178)">Input</button>
  <button class="danger" onclick="reboot()">Reboot</button>
</div>

<div class="card">
<h4>Direcionais</h4>
<div class="grid">
  <div></div><button onclick="key(19)">▲</button><div></div>
  <button onclick="key(21)">◀</button>
  <button onclick="key(66)">OK</button>
  <button onclick="key(22)">▶</button>
  <div></div><button onclick="key(20)">▼</button><div></div>
</div>
</div>

<div class="card">
<h4>Feedback visual (scrcpy-web)</h4>

<div class="scrcpy-panel">
  <div class="scrcpy-resizable" id="scrcpyContainer">
    <iframe
      id="scrcpyFrame"
      class="scrcpy-frame"
      src="{SCRCPY_WEB_URL}"
      allow="autoplay">
    </iframe>
  </div>

  <div class="warn">
    Vídeo via scrcpy-web • Redimensionável • Controle somente pelos botões
  </div>
</div>
</div>

<div class="card">
<h4>Logs</h4>
<div id="log" class="log"></div>
</div>

</div>

<script>
function log(m) {{
  const l = document.getElementById('log');
  l.innerText = `[${{new Date().toLocaleTimeString()}}] ${{m}}\\n` + l.innerText;
}}

function setIp() {{
  fetch('/set_ip', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{ip:document.getElementById('ip').value}})
  }}).then(r=>r.json()).then(j=>log(JSON.stringify(j)));
}}

function connect() {{
  fetch('/connect').then(r=>r.json()).then(j=>log(JSON.stringify(j)));
}}

function status() {{
  fetch('/status').then(r=>r.json()).then(j=>log(j.devices));
}}

function key(k) {{
  fetch('/key', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{key:k}})
  }});
}}

function reboot() {{
  fetch('/reboot', {{method:'POST'}});
}}

/* ===== SCRCPY SCALE ===== */
const container = document.getElementById('scrcpyContainer');
const iframe = document.getElementById('scrcpyFrame');

const BASE_W = 1280;
const BASE_H = 720;

function resizeScrcpy() {{
  const sx = container.clientWidth / BASE_W;
  const sy = container.clientHeight / BASE_H;
  const scale = Math.min(sx, sy);
  iframe.style.transform = `scale(${{scale}})`;
}}

new ResizeObserver(resizeScrcpy).observe(container);
resizeScrcpy();
</script>

</body>
</html>
"""

# =====================
# ROUTES
# =====================
@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML)

@app.post("/set_ip")
async def set_ip(req: Request):
    global TV_IP, ADB_DEVICE
    body = await req.json()
    TV_IP = body["ip"]
    ADB_DEVICE = f"{TV_IP}:5555"
    return {"device": ADB_DEVICE}

@app.get("/connect")
def connect():
    return adb(["connect", ADB_DEVICE])

@app.get("/status")
def status():
    return JSONResponse({"devices": adb(["devices"])["stdout"]})

@app.post("/key")
async def key(req: Request):
    k = (await req.json()).get("key")
    return adb(["-s", ADB_DEVICE, "shell", "input", "keyevent", str(k)])

@app.post("/reboot")
def reboot():
    return adb(["-s", ADB_DEVICE, "reboot"])

# =====================
# RUN
# =====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)
