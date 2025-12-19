#!/usr/bin/env python3
"""
Painel ADB (backend + frontend embutido)
- FastAPI backend (endpoints: /set_ip, /connect, /status, /key, /reboot, /screenshot, /screen)
- Frontend HTML servido em /
- Streaming /screen: multipart/x-mixed-replace frames (uses `adb exec-out screencap -p`)
Notes:
- Install: pip install fastapi uvicorn python-multipart
- Requires `adb` installed and in PATH.
- If TV blocks screencap, /screen will show black frames (but controls still work).
"""
import os
import shlex
import subprocess
import asyncio
import time
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Painel ADB - TCL Control")

# CORS (local network use)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# default TV IP (can be changed via /set_ip)
TV_IP = os.environ.get("TV_IP", "10.0.110.253")
ADB_DEVICE = f"{TV_IP}:5555"


def _adb_cmd(args: list[str], timeout: int = 15):
    """Run adb command (returns stdout, stderr, returncode)."""
    cmd = ["adb"] + args
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = p.stdout.decode(errors="ignore")
        err = p.stderr.decode(errors="ignore")
        return out, err, p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 124
    except FileNotFoundError:
        return "", "adb-not-found", 127


def adb_shell(cmd: str, timeout: int = 15):
    """Helper to run `adb -s DEVICE shell <cmd>`."""
    args = ["-s", ADB_DEVICE, "shell"] + shlex.split(cmd)
    out, err, code = _adb_cmd(args, timeout=timeout)
    return out, err, code


def adb_simple(args: list[str], timeout: int = 15):
    """Helper to run `adb -s DEVICE <args...>`."""
    out, err, code = _adb_cmd(["-s", ADB_DEVICE] + args, timeout=timeout)
    return out, err, code


# --- Background auto-reconnect thread-like coroutine (non-blocking) ---
async def adb_autoreconnect_loop():
    """Continuously ensure adb connect to the device address."""
    global ADB_DEVICE
    while True:
        try:
            # check devices
            out, err, code = _adb_cmd(["devices"])
            if ADB_DEVICE not in out:
                # try connect
                _out, _err, _c = _adb_cmd(["connect", ADB_DEVICE])
                # small wait
                await asyncio.sleep(2)
        except Exception:
            pass
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    # start background reconnect task
    asyncio.create_task(adb_autoreconnect_loop())


# -------------------------
# Frontend (single-page)
# -------------------------
INDEX_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Painel ADB - TCL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Inter,Arial;margin:0;background:linear-gradient(180deg,#071029,#0e2a4d);color:#fff;padding:18px}
.container{max-width:1000px;margin:0 auto}
.header{display:flex;gap:10px;align-items:center;margin-bottom:14px}
input[type=text]{padding:10px;border-radius:8px;border:0;width:260px}
button{padding:10px 12px;border-radius:8px;border:0;background:#2b9cff;color:#fff;cursor:pointer}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.card{background:rgba(255,255,255,0.06);padding:14px;border-radius:12px;margin-bottom:12px}
.grid{display:grid;grid-template-columns:120px 120px 120px;justify-content:center;gap:8px}
.screen{background:#000;height:360px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#999}
.log{background:rgba(0,0,0,0.25);padding:10px;height:160px;overflow:auto;border-radius:8px}
.small{padding:6px 8px;font-size:13px}
.warn{color:#ffd966;font-size:13px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2 style="margin:0">Painel ADB - TCL</h2>
    <div style="flex:1"></div>
    <input id="ip" type="text" placeholder="IP da TV (ex: 10.0.110.253)" />
    <button onclick="setIp()">Set IP</button>
    <button onclick="connect()">Connect</button>
    <button onclick="status()">Status</button>
  </div>

  <div class="card">
    <div style="display:flex;gap:10px;align-items:center">
      <button onclick="sendKey(3)" class="small">Home</button>
      <button onclick="sendKey(4)" class="small">Back</button>
      <button onclick="sendKey(26)" class="small">Power</button>
      <button onclick="sendKey(24)" class="small">Vol+</button>
      <button onclick="sendKey(25)" class="small">Vol-</button>
      <button onclick="sendKey(178)" class="small">Entradas</button>
      <button onclick="reboot()" style="background:#e44" class="small">Reboot</button>
    </div>
  </div>

  <div class="card">
    <h4 style="margin:0 0 8px 0">Direcionais / OK</h4>
    <div class="grid" style="justify-content:center">
      <div></div>
      <button onclick="sendKey(19)">▲</button>
      <div></div>
      <button onclick="sendKey(21)">◀</button>
      <button onclick="sendKey(66)">OK</button>
      <button onclick="sendKey(22)">▶</button>
      <div></div>
      <button onclick="sendKey(20)">▼</button>
      <div></div>
    </div>
  </div>

  <div class="card">
    <h4 style="margin:0 0 8px 0">Entradas HDMI</h4>
    <div style="display:flex;gap:8px">
      <button onclick="hdmi(1)">HDMI1</button>
      <button onclick="hdmi(2)">HDMI2</button>
      <button onclick="hdmi(3)">HDMI3</button>
    </div>
  </div>

  <div class="card">
    <h4 style="margin:0 0 8px 0">Visualização</h4>
    <div class="warn">Se ficar preta, a TV bloqueia captura. Os botões continuam funcionando.</div>
    <div id="screen" class="screen">Carregando stream... (se disponível)</div>
  </div>

  <div class="card">
    <h4 style="margin:0 0 8px 0">Logs</h4>
    <div id="log" class="log"></div>
  </div>
</div>

<script>
let TV_IP = "{tv_ip}";

function log(msg){
  const l = document.getElementById('log');
  l.innerText = `[${new Date().toLocaleTimeString()}] ${msg}\\n` + l.innerText;
}

function setIp(){
  const ip = document.getElementById('ip').value.trim();
  if(!ip) return alert('Informe IP');
  TV_IP = ip;
  fetch('/set_ip', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ip})})
    .then(r=>r.json()).then(j=>log('IP set: ' + JSON.stringify(j)));
}

function connect(){
  fetch('/connect').then(r=>r.json()).then(j=>log('connect: '+JSON.stringify(j)));
}

function status(){
  fetch('/status').then(r=>r.json()).then(j=>log('status: '+JSON.stringify(j)));
}

function sendKey(key){
  fetch('/key', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key})})
    .then(r=>r.json()).then(j=>log('key '+key+': '+JSON.stringify(j)));
}

function reboot(){
  fetch('/reboot', {method:'POST'}).then(r=>r.json()).then(j=>log('reboot: '+JSON.stringify(j)));
}

function hdmi(n){
  if(n===1) sendKey(243);
  else if(n===2) sendKey(244);
  else if(n===3) sendKey(245);
}

// try to show screen via <img src="/screen"> if available
(function try_stream(){
  const screen = document.getElementById('screen');
  // create image element that points to /screen (multipart stream)
  const img = document.createElement('img');
  img.style.maxHeight = '360px';
  img.style.maxWidth = '100%';
  img.onerror = ()=> { screen.innerText = 'Stream não disponível / tela preta'; };
  img.onload = ()=> { screen.innerHTML = ''; screen.appendChild(img); };
  img.src = '/screen?_=' + Date.now();
})();
</script>
</body>
</html>
""".replace("{tv_ip}", TV_IP)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)


# -------------------------
# API endpoints
# -------------------------
@app.post("/set_ip")
async def set_ip(req: Request):
    """Set the TV IP for future adb calls."""
    global TV_IP, ADB_DEVICE
    body = await req.json()
    ip = body.get("ip")
    if not ip:
        raise HTTPException(status_code=400, detail="ip required")
    TV_IP = ip
    ADB_DEVICE = f"{TV_IP}:5555"
    return {"tv_ip": TV_IP, "adb_device": ADB_DEVICE}


@app.get("/connect")
def connect():
    """Try to connect adb to the configured TV ip."""
    out, err, code = _adb_cmd(["connect", ADB_DEVICE])
    return {"out": out.strip(), "err": err.strip(), "code": code}


@app.get("/status")
def status():
    """Return adb devices list and current TV address."""
    out, err, code = _adb_cmd(["devices"])
    return {"adb_devices": out, "adb_err": err, "adb_device": ADB_DEVICE}


@app.post("/key")
async def key_event(req: Request):
    """Send a single keyevent integer (body: { key: 3 })"""
    body = await req.json()
    key = body.get("key")
    try:
        key_int = int(key)
    except Exception:
        raise HTTPException(400, "key must be an integer")
    out, err, code = _adb_cmd(["-s", ADB_DEVICE, "shell", "input", "keyevent", str(key_int)])
    return {"out": out, "err": err, "code": code}


@app.post("/reboot")
def reboot():
    out, err, code = _adb_cmd(["-s", ADB_DEVICE, "reboot"])
    return {"out": out, "err": err, "code": code}


@app.get("/screenshot")
def screenshot():
    """Take a screenshot via adb exec-out screencap -p and return it as a file."""
    fname = "tv_screenshot.png"
    # run and write locally
    try:
        with open(fname, "wb") as f:
            p = subprocess.Popen(["adb", "-s", ADB_DEVICE, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data, err = p.communicate(timeout=10)
            f.write(data)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "screencap timeout")
    except Exception as e:
        raise HTTPException(500, str(e))
    return FileResponse(fname, media_type="image/png", filename=fname)


# streaming generator
async def screencap_generator():
    boundary = "--frame"
    while True:
        # run blocking screencap in thread
        def grab():
            try:
                p = subprocess.run(["adb", "-s", ADB_DEVICE, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
                return p.stdout, p.stderr
            except Exception as e:
                return b"", str(e).encode()

        data, err = await asyncio.to_thread(grab)
        if not data:
            # sleep briefly and continue (yields nothing)
            await asyncio.sleep(0.4)
            continue

        header = (f"{boundary}\r\nContent-Type: image/png\r\nContent-Length: {len(data)}\r\n\r\n").encode()
        yield header + data + b"\r\n"
        await asyncio.sleep(0.18)


@app.get("/screen")
def screen():
    """Stream multipart png frames (MJPEG-like but PNG frames)."""
    return StreamingResponse(screencap_generator(), media_type='multipart/x-mixed-replace; boundary=--frame')


# Run uvicorn externally (recommended). If run directly, start uvicorn server.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("painel_adb:app", host="0.0.0.0", port=8000, reload=True)
