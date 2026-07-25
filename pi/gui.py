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
    from autopilot import Autopilot, TiltSweep
    from tag_map import TagMap
    from path_store import PathStore
except Exception as _e:
    Autopilot = TiltSweep = None
    print(f"[gui] autopilot unavailable: {_e}")

try:
    from fetch_auto import Vision
except Exception as _e:            # camera libs missing etc - GUI still runs
    Vision = None
    print(f"[gui] vision unavailable: {_e}")


class FakeRobot:
    """Stand-in so the UI can be developed and tested with no robot attached."""
    port = "FAKE"

    def __init__(self):
        self.sensors = {k: 0 for k in ("f", "lf", "rf")}
        self._vel = (0, 0, 0)

    def drive(self, vx, vy=0, w=0):
        self._vel = (vx, vy, w)
        print(f"[fake] drive vx={vx} vy={vy} w={w}")

    def stop(self):
        self._vel = (0, 0, 0)
        print("[fake] stop")

    def motor(self, i, spd):
        print(f"[fake] motor {i} spd={spd}")

    def max_rate(self, sps):
        print(f"[fake] max_rate {sps}")

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
  .sensors{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center}
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

<div class="card" id="autocard">
  <h2>Go to art piece <span class="val" id="autostat">idle</span></h2>
  <div id="tagrow" style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px">
    <button class="tagbtn" data-t="0" style="height:52px;font-size:15px">0</button>
    <button class="tagbtn" data-t="1" style="height:52px;font-size:15px">1</button>
    <button class="tagbtn" data-t="2" style="height:52px;font-size:15px">2</button>
    <button class="tagbtn" data-t="3" style="height:52px;font-size:15px">3</button>
    <button class="tagbtn" data-t="4" style="height:52px;font-size:15px">4</button>
  </div>
  <div id="autodetail" style="font-size:11.5px;color:var(--dim);margin-top:8px;
       min-height:15px">tap a tag number to drive there autonomously</div>
</div>

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
  <h2>Calibrate art piece locations</h2>
  <img id="cal" src="/camera.mjpg" style="width:100%;border-radius:10px;
       background:#000;aspect-ratio:4/3;object-fit:cover">
  <div id="callive" style="text-align:center;font-size:13px;margin:8px 0;
       color:var(--dim)">looking for a tag...</div>
  <button id="calbtn" style="width:100%;height:52px;font-size:16px"
          disabled>hold up a tag</button>
  <div id="calmsg" style="text-align:center;font-size:12px;min-height:16px;
       margin-top:6px;color:var(--dim)"></div>
  <div id="callist" style="font-size:12px;margin-top:10px"></div>
  <div style="font-size:11px;color:var(--dim);margin-top:8px;line-height:1.5">
    Park the robot exactly where it should end up, point it at the art
    piece's tag, then press Calibrate. It saves how the tag LOOKS from
    that spot - which is what "go to N" then drives back to.
    Press again any time to recalibrate.</div>
</div>

<div class="card">
  <h2>Motor rate <span class="val" id="ratev">520 steps/s</span></h2>
  <input type="range" id="rate" min="120" max="1200" step="20" value="520">
  <div style="font-size:11px;color:var(--dim);margin-top:6px">
    Steppers are loud at some rates and quiet at others (resonance).
    Sweep this while driving and stop where it sounds smoothest.</div>
</div>

<div class="card">
  <h2>Teach a route</h2>
  <button id="homebtn" style="width:100%;height:48px;font-size:15px">
    Set HOME (robot is on the start spot)</button>
  <div id="homest" style="text-align:center;font-size:12px;margin:8px 0;
       color:var(--dim)">home not set</div>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px">
    <button class="recbtn" data-t="0" style="height:44px">rec 0</button>
    <button class="recbtn" data-t="1" style="height:44px">rec 1</button>
    <button class="recbtn" data-t="2" style="height:44px">rec 2</button>
    <button class="recbtn" data-t="3" style="height:44px">rec 3</button>
    <button class="recbtn" data-t="4" style="height:44px">rec 4</button>
  </div>
  <button id="recstop" style="width:100%;height:48px;font-size:15px;
          margin-top:8px;display:none;background:var(--warn)">
    STOP recording &amp; save</button>
  <div id="recmsg" style="text-align:center;font-size:12px;min-height:16px;
       margin-top:6px;color:var(--dim)"></div>
  <div id="reclist" style="font-size:12px;margin-top:8px"></div>
  <div style="font-size:11px;color:var(--dim);margin-top:8px;line-height:1.5">
    Put the robot on HOME, press Set HOME, then press rec N and drive to
    art piece N by hand. Turn to face its tag, calibrate it above, then
    STOP recording. "Go to N" replays that route and the tag corrects the
    last stretch.</div>
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
// --- calibration ---
let liveTag = null;
$('#calbtn').onclick = async () => {
  const r = await (await fetch('/calibrate', {method:'POST',
                    body:JSON.stringify({})})).json();
  $('#calmsg').textContent = r.msg || '';
  $('#calmsg').style.color = r.ok ? 'var(--ok)' : 'var(--warn)';
  if (r.calib) renderCalib(r.calib);
};
function renderCalib(c){
  const ids = Object.keys(c).sort();
  $('#callist').innerHTML = ids.length
    ? ids.map(i=>`<div style="display:flex;justify-content:space-between;
        padding:4px 0;border-top:1px solid var(--line)">
        <span>tag ${i} <span style="color:var(--dim)">${c[i].label||''}</span></span>
        <span style="color:var(--dim)">${Math.round(c[i].area)} px
        <a href="#" data-f="${i}" style="color:var(--warn);margin-left:8px">clear</a></span>
      </div>`).join('')
    : '<div style="color:var(--dim);text-align:center">nothing calibrated yet</div>';
  $('#callist').querySelectorAll('a[data-f]').forEach(a=>{
    a.onclick = async e => { e.preventDefault();
      const r = await (await fetch('/forget',{method:'POST',
        body:JSON.stringify({id:+a.dataset.f})})).json();
      renderCalib(r.calib); };
  });
}

let rateT = null;
$('#rate').oninput = e => {
  $('#ratev').textContent = e.target.value + ' steps/s';
  clearTimeout(rateT);                       // don't spam the serial link
  rateT = setTimeout(()=> post('/rate', {sps:+e.target.value}), 120);
};
// --- teach & repeat ---
$('#homebtn').onclick = async () => {
  const r = await (await fetch('/sethome',{method:'POST',body:'{}'})).json();
  $('#recmsg').textContent = r.msg || '';
  $('#recmsg').style.color = 'var(--ok)';
};
document.querySelectorAll('.recbtn').forEach(b=>{
  b.onclick = async () => {
    const r = await (await fetch('/record',{method:'POST',
                      body:JSON.stringify({id:+b.dataset.t})})).json();
    $('#recmsg').textContent = r.msg || '';
    $('#recmsg').style.color = r.ok ? 'var(--ok)' : 'var(--warn)';
    if (r.ok) $('#recstop').style.display = 'block';
  };
});
$('#recstop').onclick = async () => {
  const r = await (await fetch('/recstop',{method:'POST',body:'{}'})).json();
  $('#recmsg').textContent = r.msg || '';
  $('#recmsg').style.color = r.ok ? 'var(--ok)' : 'var(--warn)';
  $('#recstop').style.display = 'none';
  if (r.routes) renderRoutes(r.routes);
};
function renderRoutes(rt){
  const ids = Object.keys(rt).sort();
  $('#reclist').innerHTML = ids.length
    ? ids.map(i=>`<div style="display:flex;justify-content:space-between;
        padding:4px 0;border-top:1px solid var(--line)">
        <span>route to ${i}</span>
        <span style="color:var(--dim)">${rt[i].moves} moves · ${rt[i].secs}s</span>
      </div>`).join('')
    : '<div style="color:var(--dim);text-align:center">no routes taught yet</div>';
}

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

// --- autonomous: go to tag ---
document.querySelectorAll('.tagbtn').forEach(b=>{
  b.onclick = ()=>{
    const already = b.classList.contains('on');
    document.querySelectorAll('.tagbtn').forEach(x=>x.classList.remove('on'));
    if(already){ post('/auto', {}); }            // tapping again cancels
    else { b.classList.add('on'); post('/auto', {target:+b.dataset.t}); }
  };
});

// --- camera feed ---
// Polled stills rather than an MJPEG <img>: multipart/x-mixed-replace is
// unreliable in several mobile browsers and fails silently, showing nothing.
// Fetching a JPEG every 150 ms works everywhere. Decode into an off-screen
// Image first and only swap once it has loaded, so the view never flickers.
(function(){
  const img = $('#cam'), stat = $('#camstat');
  let busy = false, fails = 0;

  function tick(){
    if(busy) return;
    busy = true;
    const probe = new Image();
    probe.onload = ()=>{
      img.src = probe.src;              // swap only after a full decode
      busy = false; fails = 0;
      $('#camcard').style.opacity = 1;
    };
    probe.onerror = ()=>{
      busy = false;
      if(++fails > 6){ stat.textContent = 'camera offline';
                       $('#camcard').style.opacity = .5; }
    };
    probe.src = '/snapshot.jpg?t=' + Date.now();
  }
  setInterval(tick, 150);               // ~6-7 fps, plenty to drive by
  tick();
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
    liveTag = j.tag;
    const cb = $('#calbtn'), cl = $('#callive');
    if (cb) {
      if (j.tag) {
        cb.disabled = false;
        cb.textContent = 'Calibrate location for tag ' + j.tag.id;
        cl.textContent = `tag ${j.tag.id} · ${Math.round(j.tag.area)} px · `
                       + `offset ${j.tag.cx_norm.toFixed(2)}`;
      } else {
        cb.disabled = true;
        cb.textContent = 'hold up a tag';
        cl.textContent = j.cam ? 'no tag in view' : 'camera not detected';
      }
    }
    if (j.calib) renderCalib(j.calib);
    if(j.auto){
      $('#autostat').textContent = j.auto.state;
      $('#autodetail').textContent = j.auto.detail || '';
      const running = (j.auto.state==='searching'||j.auto.state==='approaching');
      document.querySelectorAll('.tagbtn').forEach(b=>{
        b.classList.toggle('on', running && +b.dataset.t === j.auto.target);
      });
    }
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
    tag_map = None
    paths = None
    auto = None

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
                "auto": (self.auto.status() if self.auto else None),
                "calib": (self.tag_map.as_dict() if self.tag_map else {}),
                "routes": (self.paths.as_dict() if self.paths else {}),
                "home": (self.paths.home_set if self.paths else False),
            })

        if self.path.startswith("/snapshot.jpg"):
            jpg = self.vision.latest_jpeg() if (self.vision and self.vision.ok) else None
            if not jpg:
                self.send_response(503); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(jpg)))
            self.end_headers()
            try:
                self.wfile.write(jpg)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

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
        # The page changes every time the robot code is redeployed. Without
        # this, phones happily serve a cached copy for hours and new panels
        # (like the camera) simply never appear.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
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
            if self.auto and self.auto.busy:
                self.auto.abort()      # a human taking the controls wins
            self.robot.drive(data.get("vx", 0), data.get("vy", 0), data.get("w", 0))
            self.deadman.touch()
        elif p.startswith("/stop"):
            self.deadman.clear()
            if self.auto:
                self.auto.abort()      # STOP outranks autonomy
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
        elif p.startswith("/auto"):
            if self.auto:
                tgt = data.get("target")
                if tgt is None:
                    self.auto.abort()
                else:
                    self.auto.go(int(tgt))
        elif p.startswith("/sethome"):
            ok, msg = (self.paths.set_home() if self.paths
                       else (False, "no path store"))
            return self._json({"ok": ok, "msg": msg})
        elif p.startswith("/record"):
            ok, msg = (self.paths.start_recording(int(data.get("id", -1)))
                       if self.paths else (False, "no path store"))
            if ok:
                self.robot.recorder = self.paths      # arm the drive() tap
            return self._json({"ok": ok, "msg": msg})
        elif p.startswith("/recstop"):
            ok, msg = (self.paths.stop_recording() if self.paths
                       else (False, "no path store"))
            self.robot.recorder = None
            return self._json({"ok": ok, "msg": msg,
                               "routes": self.paths.as_dict() if self.paths else {}})
        elif p.startswith("/calibrate"):
            # Snapshot the CURRENT view of whatever tag is visible. The tilt
            # goes in too, so a tag mounted high is re-found at the same angle.
            tag = self.vision.tag if self.vision else None
            tilt = getattr(self.auto.tilt, "angle", None) if self.auto else None
            ok, msg = (self.tag_map.calibrate(tag, tilt=tilt)
                       if self.tag_map else (False, "no tag map"))
            return self._json({"ok": ok, "msg": msg,
                               "calib": self.tag_map.as_dict() if self.tag_map else {}})
        elif p.startswith("/forget"):
            if self.tag_map:
                self.tag_map.forget(int(data.get("id", -1)))
            return self._json({"ok": True,
                               "calib": self.tag_map.as_dict() if self.tag_map else {}})
        elif p.startswith("/rate"):
            self.robot.max_rate(int(data.get("sps", 520)))
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

    Handler.tag_map = TagMap() if TagMap is not None else None
    Handler.paths = PathStore() if PathStore is not None else None

    if Autopilot is not None:
        Handler.auto = Autopilot(Handler.robot, Handler.vision,
                                 TiltSweep(Handler.robot),
                                 tag_map=Handler.tag_map,
                                 path_store=Handler.paths)

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"\n  open  http://{my_ip()}:{args.port}   (ctrl-C to quit)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.robot.stop()
        Handler.robot.close()
