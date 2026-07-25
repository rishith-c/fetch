#!/usr/bin/env python3
"""
FETCH GUI — web control panel served by the Pi. Open it from any phone or
laptop on the same WiFi; drive the robot with touch or the keyboard.

    python3 gui.py                 # normal: talks to the Uno over USB
    python3 gui.py --fake          # no hardware, for testing the UI
    python3 gui.py --port 8080     # change the web port (default 8080)

Then browse to   http://<pi-ip>:8080   (the script prints the URL).

Stdlib only apart from pyserial (which drive.py already needs) — no Flask,
no npm, nothing to install on the Pi beyond python3-serial.

SAFETY: releasing a button sends stop, and the Uno's own 500 ms watchdog
halts the motors if this process dies or the WiFi drops mid-press.
"""
import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from drive import Robot
except ImportError:
    Robot = None

try:
    from fetch_auto import Vision
except Exception as _e:            # camera libs missing etc - GUI still runs
    Vision = None
    print(f"[gui] vision unavailable: {_e}")


class FakeRobot:
    """Stand-in so the UI can be developed and tested with no robot attached."""
    port = "FAKE"

    def __init__(self):
        self.sensors = {k: 0 for k in ("f", "lf", "rf", "lr", "rr")}
        self._vel = (0, 0, 0)

    def drive(self, vx, vy=0, w=0):
        self._vel = (vx, vy, w)
        print(f"[fake] drive vx={vx} vy={vy} w={w}")

    def stop(self):
        self._vel = (0, 0, 0)
        print("[fake] stop")

    def motor(self, i, spd):
        print(f"[fake] motor {i} spd={spd}")

    def guard(self, on):
        print(f"[fake] guard {on}")

    def tilt(self, deg):
        print(f"[fake] tilt {deg}")

    def crab_circle(self, seconds=12.0):
        print("[fake] crab circle")

    def close(self):
        pass


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>FETCH control</title>
<style>
  :root{
    --bg:#0e0f13; --panel:#181a21; --line:#282b36; --ink:#eef0f6; --dim:#8b90a0;
    --acc:#f2c321; --go:#3ddc84; --stop:#ff5252; --blue:#5aa9ff;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.4 -apple-system,system-ui,sans-serif;
       padding:14px;max-width:520px;margin:0 auto;user-select:none}
  header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
  h1{font-size:19px;margin:0;letter-spacing:.02em}
  h1 span{color:var(--acc)}
  #link{font:11px ui-monospace,monospace;color:var(--dim)}
  #link.bad{color:var(--stop)}
  .pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  button{
    background:var(--panel);color:var(--ink);border:1px solid var(--line);
    border-radius:14px;padding:0;height:74px;font-size:24px;font-weight:600;
    display:flex;align-items:center;justify-content:center;flex-direction:column;
    gap:2px;cursor:pointer;transition:transform .06s,background .12s;touch-action:none;
  }
  button small{font-size:10px;font-weight:500;color:var(--dim);letter-spacing:.08em}
  button:active,button.on{background:var(--blue);color:#08121f;transform:scale(.96)}
  button:active small,button.on small{color:#08121f;opacity:.75}
  #stop{grid-column:span 3;height:64px;background:var(--stop);color:#fff;
        border-color:var(--stop);font-size:18px;letter-spacing:.12em}
  #stop small{color:#fff;opacity:.8}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
  .row button{height:56px;font-size:15px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
        padding:12px 14px;margin-top:12px}
  .card h2{font-size:11px;letter-spacing:.14em;color:var(--dim);margin:0 0 10px;
           text-transform:uppercase;font-weight:600}
  input[type=range]{width:100%;accent-color:var(--acc)}
  .val{float:right;font:12px ui-monospace,monospace;color:var(--acc)}
  .sensors{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;text-align:center}
  .sensors div{background:#11131a;border:1px solid var(--line);border-radius:8px;
               padding:8px 2px 6px;transition:border-color .15s}
  .sensors b{display:block;font:17px ui-monospace,monospace;line-height:1.1;
             color:var(--go);transition:color .15s}
  .sensors b small{font-size:9px;opacity:.5}
  .sensors span{font-size:9px;color:var(--dim);letter-spacing:.06em}
  .bar{height:4px;border-radius:2px;background:#22252e;margin:5px 3px 0;overflow:hidden}
  .bar i{display:block;height:100%;width:0;background:var(--go);transition:width .2s,background .15s}
  .warn b,.warn i{color:var(--acc);background:var(--acc)}
  .stopz b,.stopz i{color:var(--stop);background:var(--stop)}
  .stopz{border-color:var(--stop)!important}
  .guardrow{display:grid;grid-template-columns:1fr auto;align-items:center;gap:10px;margin-top:10px}
  #guardbtn{height:38px;font-size:11px;letter-spacing:.08em;padding:0 14px}
  #guardbtn.armed{background:var(--go);color:#07200f;border-color:var(--go)}
  footer{margin-top:14px;font-size:11.5px;color:var(--dim);text-align:center}
</style>

<header>
  <h1>FETCH <span>control</span></h1>
  <div id="link">connecting…</div>
</header>

<div class="card" id="camcard" style="padding:10px">
  <h2>Camera <span class="val" id="camstat">…</span></h2>
  <img id="cam" style="width:100%;border-radius:9px;display:block;background:#0a0b0e"
       alt="camera">
</div>

<div class="pad">
  <button data-vx="60"  data-vy="-60">↖<small>DIAG</small></button>
  <button data-vx="100" data-vy="0">▲<small>FWD</small></button>
  <button data-vx="60"  data-vy="60">↗<small>DIAG</small></button>

  <button data-vx="0" data-vy="-100">◀<small>STRAFE L</small></button>
  <button id="crab">◍<small>CRAB</small></button>
  <button data-vx="0" data-vy="100">▶<small>STRAFE R</small></button>

  <button data-vx="-60" data-vy="-60">↙<small>DIAG</small></button>
  <button data-vx="-100" data-vy="0">▼<small>BACK</small></button>
  <button data-vx="-60" data-vy="60">↘<small>DIAG</small></button>

  <button id="stop">■ STOP<small>SPACE</small></button>
</div>

<div class="row">
  <button data-w="-100">⟲<small>SPIN L</small></button>
  <button data-w="100">⟳<small>SPIN R</small></button>
</div>

<div class="card">
  <h2>Speed <span class="val" id="spdv">60%</span></h2>
  <input type="range" id="spd" min="20" max="100" step="5" value="60">
</div>

<div class="card">
  <h2>Camera tilt <span class="val" id="tiltv">90°</span></h2>
  <input type="range" id="tilt" min="0" max="180" step="5" value="90">
</div>

<div class="card">
  <h2>Calibrate — one motor at a time</h2>
  <p style="margin:0 0 10px;font-size:12.5px;color:var(--dim)">
    Hold <b>FWD +</b> then <b>REV −</b> on the same row. The wheel must
    turn <b>opposite ways</b>. If it turns the same way both times, that
    motor's DIRECTION pin is dead.</p>
  <div id="cal"></div>
  <div id="calout" style="font:11px ui-monospace,monospace;color:var(--acc);
       margin-top:8px;white-space:pre-wrap"></div>
</div>

<div class="card">
  <h2>Ultrasonic (cm · 0 = clear)</h2>
  <div class="sensors">
    <div id="c_lf"><b id="s_lf">—</b><span>L-FRT</span><div class="bar"><i id="b_lf"></i></div></div>
    <div id="c_f"><b id="s_f">—</b><span>FRONT</span><div class="bar"><i id="b_f"></i></div></div>
    <div id="c_rf"><b id="s_rf">—</b><span>R-FRT</span><div class="bar"><i id="b_rf"></i></div></div>
    <div id="c_lr"><b id="s_lr">—</b><span>L-REAR</span><div class="bar"><i id="b_lr"></i></div></div>
    <div id="c_rr"><b id="s_rr">—</b><span>R-REAR</span><div class="bar"><i id="b_rr"></i></div></div>
  </div>
  <div class="guardrow">
    <small style="color:var(--dim);font-size:11.5px">Obstacle avoidance blocks
      forward motion under 25&nbsp;cm</small>
    <button id="guardbtn" class="armed">ARMED</button>
  </div>
</div>

<footer>hold to drive · release to stop · WASD + QE also work</footer>

<script>
const $ = s => document.querySelector(s);
let speed = 60, held = null;

async function post(path, body){
  try{
    const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                                body: JSON.stringify(body||{})});
    $('#link').classList.remove('bad');
    return r.json();
  }catch(e){ $('#link').classList.add('bad'); $('#link').textContent = 'link lost'; }
}
const scale = v => Math.round(v * speed / 100);
const post_drive = (vx,vy,w) => post('/drive', {vx:scale(vx), vy:scale(vy), w:scale(w)});

// hold = repeat at 5 Hz. If this page dies or WiFi drops, the server's
// deadman sees the gap and stops the robot.
let repeat = null, cur = null;
function drive(vx,vy,w){
  cur = [vx,vy,w];
  post_drive(vx,vy,w);
  if(!repeat) repeat = setInterval(()=>{ if(cur) post_drive(...cur); }, 200);
}
function stop(){
  cur = null;
  if(repeat){ clearInterval(repeat); repeat = null; }
  post('/stop');
}

// --- touch / mouse: hold to drive, release to stop ---
document.querySelectorAll('.pad button, .row button').forEach(b=>{
  if(b.id === 'stop' || b.id === 'crab') return;
  const go = e => { e.preventDefault(); b.classList.add('on');
    drive(+(b.dataset.vx||0), +(b.dataset.vy||0), +(b.dataset.w||0)); };
  const end = e => { e.preventDefault(); b.classList.remove('on'); stop(); };
  b.addEventListener('pointerdown', go);
  b.addEventListener('pointerup', end);
  b.addEventListener('pointerleave', end);
  b.addEventListener('pointercancel', end);
});
function eStop(){
  // kill every local driver of motion, then tell the robot twice
  cur = null;
  if(repeat){ clearInterval(repeat); repeat = null; }
  held = null;
  document.querySelectorAll('button.on').forEach(b=>b.classList.remove('on'));
  post('/stop'); setTimeout(()=>post('/stop'), 120);
}
$('#stop').onclick = eStop;
$('#crab').onclick = () => post('/crab');

// --- sliders ---
$('#spd').oninput = e => { speed = +e.target.value; $('#spdv').textContent = speed + '%'; };
$('#tilt').oninput = e => { $('#tiltv').textContent = e.target.value + '°';
                            post('/tilt', {deg:+e.target.value}); };

// --- keyboard ---
const KEYS = {w:[100,0,0], s:[-100,0,0], a:[0,-100,0], d:[0,100,0],
              q:[0,0,-100], e:[0,0,100],
              arrowup:[100,0,0], arrowdown:[-100,0,0],
              arrowleft:[0,-100,0], arrowright:[0,100,0]};
addEventListener('keydown', ev=>{
  const k = ev.key.toLowerCase();
  if(k === ' ' || k === 'escape'){ ev.preventDefault(); eStop(); return; }
  if(KEYS[k] && held !== k){ ev.preventDefault(); held = k; drive(...KEYS[k]); }
});
addEventListener('keyup', ev=>{
  const k = ev.key.toLowerCase();
  if(KEYS[k] && held === k){ held = null; stop(); }
});
addEventListener('blur', ()=>{ held = null; stop(); });   // safety: tab away = stop

// --- calibration: drive each socket alone, record which way it rolls ---
const SOCKETS = [
  {i:0, name:'FL top-L'},  {i:1, name:'FR top-R'},
  {i:2, name:'RL bot-L'},  {i:3, name:'RR bot-R'},
];
const answers = {};
const calBox = $('#cal');
SOCKETS.forEach(s=>{
  const row = document.createElement('div');
  row.style.cssText = 'display:grid;grid-template-columns:66px 1fr 62px 62px;gap:6px;'+
                      'align-items:center;margin-bottom:7px';
  row.innerHTML = `<span style="font-size:12px;color:var(--dim)">${s.name}</span>
    <span></span>
    <button class="spin" data-s="45"  style="height:42px;font-size:11px">FWD +</button>
    <button class="spin" data-s="-45" style="height:42px;font-size:11px">REV −</button>`;
  [...row.querySelectorAll('.spin')].forEach(btn=>{
    const go  = e => { e.preventDefault(); btn.classList.add('on');
                       post('/motor', {i:s.i, spd:+btn.dataset.s}); };
    const end = e => { e.preventDefault(); btn.classList.remove('on');
                       post('/motor', {i:s.i, spd:0}); };
    btn.addEventListener('pointerdown', go);
    btn.addEventListener('pointerup', end);
    btn.addEventListener('pointerleave', end);
    btn.addEventListener('pointercancel', end);
  });
  calBox.appendChild(row);
});
$('#calsave').onclick = async ()=>{
  if(Object.keys(answers).length < 4){
    $('#calout').textContent = 'Answer all four sockets first.'; return; }
  const r = await post('/cal', {answers});
  $('#calout').textContent = 'saved: ' + JSON.stringify(answers) +
                             '\nTell Claude — it will flash the fix.';
};

// --- camera feed ---
(function(){
  const img = $('#cam'), stat = $('#camstat');
  fetch('/state').then(r=>r.json()).then(j=>{
    if(j.cam){ img.src = '/camera.mjpg'; stat.textContent = 'live'; }
    else { stat.textContent = 'not detected'; $('#camcard').style.opacity = .5; }
  }).catch(()=>{ stat.textContent = 'offline'; });
  img.onerror = ()=>{ stat.textContent = 'stream error'; };
})();

// --- obstacle-avoidance toggle ---
let armed = true;
$('#guardbtn').onclick = ()=>{
  armed = !armed;
  $('#guardbtn').classList.toggle('armed', armed);
  $('#guardbtn').textContent = armed ? 'ARMED' : 'OFF';
  post('/guard', {on: armed});
};

// --- live sensor poll: 4 Hz, bar + colour bands ---
const RANGE = 120;                       // cm mapped to a full bar
setInterval(async ()=>{
  try{
    const r = await fetch('/state'); const j = await r.json();
    for(const k of ['f','lf','rf','lr','rr']){
      const v = j.sensors[k];
      const val = $('#s_'+k), bar = $('#b_'+k), cell = $('#c_'+k);
      // 0 means no echo inside range, which is 'clear', not 'touching'
      val.innerHTML = v > 0 ? v + '<small>cm</small>' : '—';
      bar.style.width = (v > 0 ? Math.min(100, v / RANGE * 100) : 100) + '%';
      cell.className = (v > 0 && v < 25) ? 'stopz'
                     : (v > 0 && v < 50) ? 'warn' : '';
    }
    $('#link').textContent = j.port;
    $('#link').classList.remove('bad');
    const cs = $('#camstat');
    if(j.cam) cs.textContent = j.tag ? ('TAG ' + j.tag.id) : 'live · no tag';
  }catch(e){ $('#link').textContent = 'link lost'; $('#link').classList.add('bad'); }
}, 250);
</script>
"""


class Deadman:
    """Stops the robot if the browser stops asking for motion.

    The Uno's own watchdog only protects against THIS process dying. If the
    phone locks, the tab closes, or WiFi drops mid-press, the browser never
    sends /stop while drive.py's keepalive happily keeps the motors running.
    So the held button re-sends /drive ~5 Hz and this thread halts everything
    if that stream goes quiet.
    """
    TIMEOUT = 0.7

    def __init__(self, robot):
        self.robot = robot
        self.last = 0.0
        self.moving = False
        threading.Thread(target=self._watch, daemon=True).start()

    def touch(self):
        self.last = time.time()
        self.moving = True

    def clear(self):
        self.moving = False

    def _watch(self):
        while True:
            time.sleep(0.1)
            if self.moving and time.time() - self.last > self.TIMEOUT:
                self.moving = False
                print("[deadman] browser went quiet -> stop")
                try:
                    self.robot.stop()
                except Exception:
                    pass


class Handler(BaseHTTPRequestHandler):
    robot = None
    deadman = None
    vision = None

    def log_message(self, *a):
        pass                                   # keep the console clean

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/state"):
            v = self.vision
            tag = v.tag if v else None
            return self._json({
                "sensors": self.robot.sensors,
                "port": self.robot.port,
                "cam": bool(v and v.ok),
                "tag": tag,
                "zones": (v.zones if (v and v.fresh) else None),
            })

        if self.path.startswith("/camera.mjpg"):
            if not (self.vision and self.vision.ok):
                self.send_response(503); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    jpg = self.vision.latest_jpeg()
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(jpg)).encode()
                                         + b"\r\n\r\n" + jpg + b"\r\n")
                    time.sleep(0.1)          # 10 fps is plenty and keeps CPU free
            except (BrokenPipeError, ConnectionResetError):
                return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            data = {}
        p = self.path
        if p.startswith("/drive"):
            self.robot.drive(data.get("vx", 0), data.get("vy", 0), data.get("w", 0))
            self.deadman.touch()
        elif p.startswith("/stop"):
            self.deadman.clear()
            self.robot.stop()
            print("[stop] emergency stop")
        elif p.startswith("/tilt"):
            self.robot.tilt(data.get("deg", 90))
        elif p.startswith("/crab"):
            threading.Thread(target=self.robot.crab_circle, daemon=True).start()
        elif p.startswith("/motor"):
            # single-socket spin for calibration; deadman covers a lost release
            self.robot.motor(int(data.get("i", 0)), int(data.get("spd", 0)))
            if data.get("spd"):
                self.deadman.touch()
            else:
                self.deadman.clear()
        elif p.startswith("/guard"):
            self.robot.guard(bool(data.get("on", True)))
        elif p.startswith("/cal"):
            with open("/home/varun/calibration.json", "w") as fh:
                json.dump(data.get("answers", {}), fh)
            print("[cal] saved", data.get("answers"))
        return self._json({"ok": True})


def my_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="run with no hardware")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--serial", default=None, help="e.g. /dev/ttyACM0")
    args = ap.parse_args()

    if args.fake or Robot is None:
        Handler.robot = FakeRobot()
        print("running in FAKE mode — no robot attached")
    else:
        Handler.robot = Robot(args.serial)
        print(f"connected to {Handler.robot.port}")
    Handler.deadman = Deadman(Handler.robot)

    if Vision is not None and not args.fake:
        Handler.vision = Vision()
        Handler.vision.start()

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"\n  open  http://{my_ip()}:{args.port}   (ctrl-C to quit)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.robot.stop()
        Handler.robot.close()
