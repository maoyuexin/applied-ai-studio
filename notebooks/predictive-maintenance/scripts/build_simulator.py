"""Build the single-file, offline compressor telemetry simulator.

The classroom simulator used to live only in the web app, backed by the
maintenance-api service and the older robust-score model. This script builds
the same demonstration as one HTML file that needs no server, no network and
no installed library, so it can be copied to any laptop and opened in a
browser. It replays packaged windows of real MetroPT-3 hours through the
notebook's own Isolation Forest and its frozen review line, so what students
see in class is exactly what the notebook taught.

Everything the page shows is computed here, once, and embedded as JSON:
readings per hour, the six numbers, the anomaly score, the flag, the report
overlap and the typical learning-month range for each number. The page cannot
score a new window live, and neither could the app: both replay saved hours.

    node scripts/venv-python.mjs notebooks/predictive-maintenance/scripts/build_simulator.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

PROJECT_DIR = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.insert(0, str(PROJECT_DIR))
from pdmlab import config, data, features, teaching  # noqa: E402

OUTPUT = PROJECT_DIR / "backup" / "02_pdm_simulator.html"
EXPECTED_CUTOFF = 0.6792839227835988

# Packaged windows: (id, label, purpose, start, end). Each is a slice of real
# clock hours; hours the quality gate dropped stay in the replay as holds.
WINDOWS = [
    ("S1_learning_days", "Three normal days in the learning months (Feb 15-17)",
     "What normal looks like. Short working bursts, long rests, scores well under the line.",
     "2020-02-15 00:00", "2020-02-17 23:00"),
    ("S2_F1", "F1: the day before and the day of the first reported leak (Apr 17-18)",
     "Reported at midnight on April 18. The first flag comes at 06:00, so no warning.",
     "2020-04-17 00:00", "2020-04-18 23:00"),
    ("S3_F2", "F2: an overnight leak (May 28-30)",
     "Reported at 23:30 on May 29. The first flag comes at 05:00 the next morning.",
     "2020-05-28 23:00", "2020-05-30 06:00"),
    ("S4_F3", "F3: the longest reported leak (Jun 4-7)",
     "Reported at 10:00 on June 5. The flagged hour is the reported hour itself.",
     "2020-06-04 10:00", "2020-06-07 14:00"),
    ("S5_F4_warning", "F4: the one leak with real warning (Jul 14-15)",
     "A recorder gap, then readings resume, then the 00:00 hour is flagged. The leak is reported at 14:30.",
     "2020-07-14 14:00", "2020-07-15 19:00"),
    ("S6_busy_may", "Busier days in the practice months, no report (May 19-21)",
     "Seven flagged hours and no maintenance report. Advance warning, a busier timetable, or a sensor? Only an inspection can say.",
     "2020-05-19 16:00", "2020-05-21 01:00"),
    ("S7_gap_then_high", "Recorder gap, then the highest score of the final check (Jul 7-8)",
     "Twenty-three hours with no readings, then the 18:00 hour on July 8 scores 0.750 with no report anywhere near it.",
     "2020-07-07 06:00", "2020-07-08 23:00"),
    ("S8_summer_days", "Three normal summer days (Aug 8-10)",
     "Same machine, healthy, on the summer timetable. Busier than February, still under the line.",
     "2020-08-08 00:00", "2020-08-10 23:00"),
]

STORY_STEP = {
    "load_share": "restarts sooner", "cycles_per_hour": "restarts sooner",
    "rest_minutes_per_cycle": "restarts sooner", "oil_temp_mean": "runs hot",
    "tp3_std": "pressure falls faster", "pressure_fall_rate": "pressure falls faster",
}
FEATURE_WHAT = {
    "load_share": "share of the hour working hard", "cycles_per_hour": "how often it kicked in",
    "rest_minutes_per_cycle": "minutes off between starts", "oil_temp_mean": "average for the hour",
    "tp3_std": "how much panel pressure varied", "pressure_fall_rate": "how fast it changed while resting",
}


def _fmt(feature: str, value: float) -> str:
    multiplier, unit = teaching.FEATURE_FORMATS[feature]
    decimals = 1 if feature not in {"tp3_std", "pressure_fall_rate"} else 3
    return f"{value * multiplier:.{decimals}f}{unit}"


def fit_forest():
    minutes = data.load_minutes()
    matrix = features.model_matrix(features.hourly_features(minutes))
    training = matrix.loc[(matrix.index >= config.TRAIN_START) & (matrix.index < config.TRAIN_END)]
    validation = matrix.loc[(matrix.index >= config.DEV_START) & (matrix.index < config.DEV_END)]
    forest = IsolationForest(n_estimators=300, max_samples=256,
                             random_state=config.RANDOM_STATE, contamination="auto").fit(training)
    cutoff = float(pd.Series(-forest.score_samples(validation), index=validation.index).quantile(0.98))
    if abs(cutoff - EXPECTED_CUTOFF) > 1e-9:
        raise SystemExit(f"Review line {cutoff!r} differs from the notebook's {EXPECTED_CUTOFF!r}.")
    scores = pd.Series(-forest.score_samples(matrix), index=matrix.index)
    return minutes, matrix, training, scores, cutoff


def build_windows(minutes, matrix, scores, cutoff) -> list[dict]:
    coverage_minutes = minutes["Motor_current"].resample("1h").count()
    events = config.failure_windows()
    out = []
    for window_id, label, purpose, start, end in WINDOWS:
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        hours = []
        for stamp in pd.date_range(start, end, freq="h"):
            event = next((name for name, onset, finish, _ in events
                          if stamp < finish and stamp + pd.Timedelta(hours=1) > onset), None)
            record = {"hour": stamp.strftime("%Y-%m-%d %H:%M"),
                      "minutes": int(coverage_minutes.get(stamp, 0)),
                      "event": event}
            if stamp in matrix.index:
                score = float(scores.loc[stamp])
                record.update({
                    "features": {name: float(matrix.loc[stamp, name]) for name in config.MODEL_FEATURES},
                    "texts": {name: _fmt(name, float(matrix.loc[stamp, name])) for name in config.MODEL_FEATURES},
                    "score": round(score, 6), "flag": bool(score >= cutoff), "hold": False,
                })
            else:
                record.update({"features": None, "texts": None, "score": None, "flag": False, "hold": True})
            hours.append(record)
        onset = next((onset for name, onset, finish, _ in events if start <= onset <= end + pd.Timedelta(hours=1)), None)
        out.append({"id": window_id, "label": label, "purpose": purpose,
                    "start": str(start), "end": str(end), "hours": hours,
                    "reported_at": onset.strftime("%Y-%m-%d %H:%M") if onset is not None else None,
                    "event": next((name for name, o, f, _ in events if start <= o <= end + pd.Timedelta(hours=1)), None)})
    return out


def build_payload() -> dict:
    minutes, matrix, training, scores, cutoff = fit_forest()
    low, high = training.quantile(0.25), training.quantile(0.75)
    feature_meta = [{
        "name": name, "label": teaching.FEATURE_LABELS[name], "what": FEATURE_WHAT[name],
        "step": STORY_STEP[name], "low": float(low[name]), "high": float(high[name]),
        "range_text": f"{_fmt(name, float(low[name]))} to {_fmt(name, float(high[name]))}",
    } for name in config.MODEL_FEATURES]
    return {
        "model": "Isolation Forest, 300 trees, learned from February-March",
        "cutoff": cutoff, "cutoff_text": f"{cutoff:.6f}",
        "features": feature_meta,
        "windows": build_windows(minutes, matrix, scores, cutoff),
        "boundary": ("The model reads saved readings and produces a score. It never sends a command to the "
                     "machine, never diagnoses a fault, and never certifies that it is safe to work on."),
        "source": "MetroPT-3, Metro do Porto air compressor, UCI dataset 791, CC BY 4.0. Same data, features, model and review line as 01_pdm_build.",
    }


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compressor Telemetry Simulator</title>
<style>
:root{--bg:#0F1117;--card:#171A22;--card2:#1C2029;--rule:#2A2F3A;--text:#F2F4F8;--dim:#AAB2C0;--faint:#6B7482;
--cyan:#22D3EE;--blue:#38BDF8;--amber:#FBBF24;--indigo:#818CF8;--violet:#A78BFA;--ok:#4ADE80;--no:#94A3B8;
--tintAmber:#2A2313;--tintBlue:#121C2B;--tintViolet:#1E1830;--tintGreen:#10241A;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 -apple-system,"Segoe UI",Calibri,Helvetica,Arial,sans-serif}
.shell{max-width:1500px;margin:0 auto;padding:18px 22px 30px}
header.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;border-bottom:1px solid var(--rule);padding-bottom:12px}
header.top h1{margin:2px 0 4px;font-size:24px}
header.top p{margin:0;color:var(--dim);max-width:900px}
.kicker{color:var(--cyan);font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.badge{border:1px solid var(--ok);color:var(--ok);border-radius:6px;padding:8px 12px;font-size:12px;white-space:nowrap;background:var(--tintGreen)}
.controls{display:grid;grid-template-columns:minmax(280px,2fr) minmax(160px,1fr) auto;gap:12px;align-items:end;margin:14px 0}
label{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
select{width:100%;background:var(--card2);color:var(--text);border:1px solid var(--rule);border-radius:6px;padding:9px 10px;font-size:13px}
.actions{display:flex;gap:8px}
button{background:var(--card2);color:var(--text);border:1px solid var(--rule);border-radius:6px;padding:9px 14px;font-size:13px;cursor:pointer}
button.primary{background:var(--cyan);color:#0F1117;border-color:var(--cyan);font-weight:700;min-width:96px}
button:disabled{opacity:.5;cursor:default}
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--rule);border-radius:8px;overflow:hidden;margin-bottom:14px}
.kpi{padding:10px 14px;border-right:1px solid var(--rule);background:var(--card)}
.kpi:last-child{border-right:0}
.kpi span{display:block;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.kpi strong{display:block;font-size:20px;margin:3px 0 1px;font-variant-numeric:tabular-nums}
.kpi small{color:var(--dim);font-size:11px}
.kpi.warn strong{color:var(--ok)}
.grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px}
.panel{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px}
.panel h2{margin:0 0 2px;font-size:15px}
.panel .sub{color:var(--faint);font-size:12px;margin-bottom:10px}
.ticker{display:grid;grid-template-columns:repeat(60,1fr);gap:2px;margin:8px 0 6px}
.ticker i{display:block;height:14px;border-radius:2px;background:var(--rule)}
.ticker i.on{background:var(--blue)}
.ticker i.missing{background:transparent;border:1px dashed var(--faint)}
.ticker-note{color:var(--dim);font-size:12px;min-height:18px}
.features{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}
.feat{border:1px solid var(--rule);border-radius:8px;padding:10px 12px;background:var(--card2);min-height:112px;opacity:.35;transition:opacity .25s}
.feat.shown{opacity:1}
.feat .name{font-weight:700;font-size:13px}
.feat .what{color:var(--faint);font-size:11px;margin-bottom:6px}
.feat .val{font-size:20px;font-variant-numeric:tabular-nums}
.feat .typ{color:var(--dim);font-size:11px;margin-top:2px}
.feat .cmp{font-size:11px;font-weight:700;margin-top:3px}
.feat.amber{border-color:var(--amber)} .feat.amber .name{color:var(--amber)}
.feat.indigo{border-color:var(--indigo)} .feat.indigo .name{color:var(--indigo)}
.feat.blue{border-color:var(--blue)} .feat.blue .name{color:var(--blue)}
.cmp.high,.cmp.low{color:var(--amber)} .cmp.within{color:var(--ok)}
.outcome{margin-top:12px;border-radius:8px;padding:14px 16px;border:1px solid var(--rule);background:var(--card2);display:flex;gap:16px;align-items:center;min-height:86px}
.outcome .big{font-size:22px;font-weight:700;min-width:210px}
.outcome p{margin:0;color:var(--dim);font-size:13px}
.outcome.flag{border-color:var(--amber);background:var(--tintAmber)} .outcome.flag .big{color:var(--amber)}
.outcome.clear{border-color:var(--ok);background:var(--tintGreen)} .outcome.clear .big{color:var(--ok)}
.outcome.hold{border-color:var(--violet);background:var(--tintViolet)} .outcome.hold .big{color:var(--violet)}
.outcome.wait .big{color:var(--faint)}
svg.chart{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;color:var(--dim);font-size:11px;margin:6px 0 10px;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.log{border-top:1px solid var(--rule);max-height:230px;overflow:auto;font-size:12px}
.log div{display:grid;grid-template-columns:130px 70px 1fr;gap:8px;padding:5px 0;border-bottom:1px solid var(--rule)}
.log time{color:var(--faint)} .log b{font-variant-numeric:tabular-nums}
.log .f{color:var(--amber)} .log .h{color:var(--violet)} .log .r{color:var(--violet)}
footer{margin-top:14px;color:var(--dim);font-size:12px;border-top:1px solid var(--rule);padding-top:10px}
footer b{color:var(--text)}
@media (max-width:1000px){.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(3,1fr)}.kpi{border-bottom:1px solid var(--rule)}.controls{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
<header class="top">
  <div>
    <div class="kicker">ITAI 2372 · Module 5 · classroom simulator</div>
    <h1>Compressor telemetry simulator</h1>
    <p>Replays saved readings from a real train compressor, one hour at a time. When an hour's readings are all in, the six numbers are computed, the notebook's model scores them, and the frozen review line decides whether to ask a person to look. Nothing here is connected to a machine.</p>
  </div>
  <div class="badge" id="badge"></div>
</header>

<section class="controls">
  <div><label for="win">Saved window</label><select id="win"></select></div>
  <div><label for="speed">Replay speed</label><select id="speed">
    <option value="12">Fast · 0.7 s per hour</option><option value="30" selected>Normal · 1.8 s per hour</option>
    <option value="70">Slow · 4 s per hour</option><option value="140">Study · 8 s per hour</option></select></div>
  <div class="actions"><button class="primary" id="run">Run</button><button id="step" title="Finish this hour, or move to the next">Step</button><button id="reset">Reset</button></div>
</section>

<section class="kpis">
  <div class="kpi"><span>Clock</span><strong id="k-clock">--</strong><small>hour beginning</small></div>
  <div class="kpi"><span>Readings this hour</span><strong id="k-min">0 / 60</strong><small id="k-min-note">waiting</small></div>
  <div class="kpi"><span>Latest score</span><strong id="k-score">--</strong><small>unusualness, not probability</small></div>
  <div class="kpi"><span>Review line</span><strong id="k-line">--</strong><small>at or above: ask a person to look</small></div>
  <div class="kpi warn"><span>Warning so far</span><strong id="k-warn">--</strong><small id="k-warn-note">first flag to reported leak</small></div>
  <div class="kpi"><span>Progress</span><strong id="k-prog">0%</strong><small id="k-prog-note">0 hours · 0 flags · 0 holds</small></div>
</section>

<section class="grid">
  <div class="panel">
    <h2>This hour</h2>
    <div class="sub" id="hour-title">Pick a window and press Run.</div>
    <div class="ticker" id="ticker"></div>
    <div class="ticker-note" id="ticker-note"></div>
    <div class="features" id="features"></div>
    <div class="outcome wait" id="outcome"><div class="big">Waiting for readings</div><p>The six numbers and the score exist only after the hour ends.</p></div>
  </div>
  <div class="panel">
    <h2>Scores over the window</h2>
    <div class="sub">One point per completed hour. The dashed line is the review line from the notebook.</div>
    <svg class="chart" id="chart" viewBox="0 0 720 330" role="img"></svg>
    <div class="legend"><span><i style="background:var(--blue)"></i>hour score</span><span><i style="background:var(--amber)"></i>flagged: ask a person to look</span><span><i style="background:var(--violet)"></i>hold: not enough readings</span><span><i style="background:rgba(167,139,250,.35);border-radius:2px"></i>reported leak</span></div>
    <div class="log" id="log"></div>
  </div>
</section>

<footer id="foot"></footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const stepClass = {"restarts sooner":"amber","runs hot":"indigo","pressure falls faster":"blue"};
let win = null, hourIdx = 0, minute = 0, phase = 'tick', timer = null, running = false, speed = 30;

const fmtHour = s => { const [d,t] = s.split(' '); const [,m,day] = d.split('-'); const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']; return `${M[+m-1]} ${+day}, ${t}`; };
const toMs = s => Date.parse(s.replace(' ','T') + ':00');

function init(){
  $('badge').textContent = `${DATA.model} · review line ${DATA.cutoff_text}`;
  $('k-line').textContent = DATA.cutoff.toFixed(6);
  $('foot').innerHTML = `<b>${DATA.boundary}</b> ${DATA.source}`;
  DATA.windows.forEach(w => { const o = document.createElement('option'); o.value = w.id; o.textContent = w.label; $('win').appendChild(o); });
  $('win').value = 'S5_F4_warning';
  $('win').onchange = () => load($('win').value);
  $('speed').onchange = () => { speed = +$('speed').value; };
  $('run').onclick = toggle; $('step').onclick = step; $('reset').onclick = reset;
  const fx = $('features');
  DATA.features.forEach(f => { const d = document.createElement('div'); d.className = `feat ${stepClass[f.step]}`; d.id = `f-${f.name}`;
    d.innerHTML = `<div class="name">${f.label}</div><div class="what">${f.what} · ${f.step}</div><div class="val">--</div><div class="typ">typical ${f.range_text}</div><div class="cmp"></div>`; fx.appendChild(d); });
  const tk = $('ticker'); for (let i=0;i<60;i++){ const s=document.createElement('i'); tk.appendChild(s); }
  load('S5_F4_warning');
}

function load(id){ win = DATA.windows.find(w => w.id === id); reset(); }

function reset(){ stop(); hourIdx = 0; minute = 0; phase = 'tick'; render(); }
function stop(){ running = false; clearTimeout(timer); $('run').textContent = 'Run'; }
function toggle(){ if (running) { stop(); return; } if (phase === 'done') { hourIdx = 0; minute = 0; phase = 'tick'; } running = true; $('run').textContent = 'Pause'; tick(); }
function step(){ stop(); if (phase === 'done') { hourIdx = 0; minute = 0; phase = 'tick'; render(); return; }
  if (phase === 'tick') { minute = 60; phase = 'scored'; } else if (phase === 'scored') { advance(); } render(); }
function advance(){ if (hourIdx >= win.hours.length - 1) { phase = 'done'; } else { hourIdx += 1; minute = 0; phase = 'tick'; } }

function tick(){
  if (!running) return;
  if (phase === 'tick') { minute += 1; if (minute >= 60) { minute = 60; phase = 'scored'; } render(); timer = setTimeout(tick, phase === 'scored' ? speed * 12 : speed); return; }
  if (phase === 'scored') { advance(); render(); if (phase === 'done') { stop(); return; } timer = setTimeout(tick, speed); return; }
}

function firstFlagIndex(upto){ for (let i=0;i<=upto;i++){ if (win.hours[i].flag) return i; } return -1; }

function render(){
  const h = win.hours[Math.min(hourIdx, win.hours.length-1)];
  const scored = phase !== 'tick';
  const present = Math.min(minute, h.minutes);
  $('k-clock').textContent = fmtHour(h.hour);
  $('k-min').textContent = `${present} / 60`;
  $('k-min-note').textContent = phase === 'tick' ? (h.minutes === 0 ? 'no readings arriving' : 'readings arriving') : (h.hold ? `${h.minutes} recorded, hour held` : 'hour complete');
  $('hour-title').textContent = `${fmtHour(h.hour)} · ${scored ? (h.hold ? 'held: not enough readings' : 'six numbers computed, score produced') : 'readings arriving minute by minute'}`;
  const cells = $('ticker').children;
  for (let i=0;i<60;i++){ const c = cells[i]; c.className = i < minute ? (i < h.minutes ? 'on' : 'missing') : ''; }
  $('ticker-note').textContent = phase === 'tick' ? `${present} of ${minute} minutes so far carried a reading` : (h.hold ? `Only ${h.minutes} of 60 minutes had readings. The quality gate needs at least 30, so no numbers and no score.` : `${h.minutes} of 60 minutes recorded. Six numbers computed from them.`);
  DATA.features.forEach(f => { const d = $(`f-${f.name}`); const show = scored && !h.hold; d.classList.toggle('shown', show);
    d.querySelector('.val').textContent = show ? h.texts[f.name] : '--';
    const c = d.querySelector('.cmp'); if (!show) { c.textContent=''; c.className='cmp'; return; }
    const v = h.features[f.name]; const k = v > f.high ? 'high' : v < f.low ? 'low' : 'within';
    c.className = `cmp ${k}`; c.textContent = k === 'high' ? 'higher than typical' : k === 'low' ? 'lower than typical' : 'within typical range'; });
  const o = $('outcome');
  if (!scored) { o.className = 'outcome wait'; o.innerHTML = `<div class="big">Waiting for readings</div><p>The six numbers and the score exist only after the hour ends, at ${fmtHour(h.hour).slice(-5)} plus one hour.</p>`; }
  else if (h.hold) { o.className = 'outcome hold'; o.innerHTML = `<div class="big">HOLD · no score</div><p>Not enough readings to trust this hour. This is a data-quality problem, not an anomaly, and the machine keeps running under the normal maintenance process.</p>`; }
  else if (h.flag) { o.className = 'outcome flag'; o.innerHTML = `<div class="big">Ask a person to look</div><p>Score ${h.score.toFixed(6)} is at or above the line ${DATA.cutoff_text}. A planner and technician inspect the compressor and its context. The model does not diagnose, stop the machine, or authorize work.${h.event ? ` A maintenance report (${h.event}) overlaps this hour; the report was never an input.` : ''}</p>`; }
  else { o.className = 'outcome clear'; o.innerHTML = `<div class="big">No model flag</div><p>Score ${h.score.toFixed(6)} is below the line ${DATA.cutoff_text}. Below the line is not proof of health; it means this hour looks like the learning months.${h.event ? ` A maintenance report (${h.event}) overlaps this hour: a missed leak hour.` : ''}</p>`; }
  const done = scored ? hourIdx + 1 : hourIdx;
  const completed = win.hours.slice(0, done);
  const flags = completed.filter(x => x.flag).length, holds = completed.filter(x => x.hold).length;
  const last = [...completed].reverse().find(x => !x.hold);
  $('k-score').textContent = last ? last.score.toFixed(3) : '--';
  $('k-prog').textContent = `${Math.round(100*done/win.hours.length)}%`;
  $('k-prog-note').textContent = `${done} of ${win.hours.length} hours · ${flags} flags · ${holds} holds`;
  const ff = firstFlagIndex(done-1);
  if (win.reported_at && ff >= 0) {
    const ready = toMs(win.hours[ff].hour) + 3600e3, onset = toMs(win.reported_at);
    const now = Math.min(toMs(h.hour) + (scored ? 3600e3 : 0), onset);
    const hrs = (Math.min(now, onset) - ready) / 3600e3;
    if (ready < onset) { $('k-warn').textContent = `${hrs.toFixed(1)} h`; $('k-warn-note').textContent = now >= onset ? `first flag ready ${fmtHour(win.hours[ff].hour).slice(-5)}+1h, leak reported ${win.reported_at.slice(-5)}` : `counting toward the report at ${win.reported_at.slice(-5)}`; }
    else { $('k-warn').textContent = 'none'; $('k-warn-note').textContent = `first flag's score came ${(-hrs).toFixed(1)} h after the report`; }
  } else { $('k-warn').textContent = win.reported_at ? '--' : 'n/a'; $('k-warn-note').textContent = win.reported_at ? 'no flag yet' : 'no reported leak in this window'; }
  drawChart(completed);
  $('log').innerHTML = completed.slice(-8).reverse().map(x => `<div><time>${fmtHour(x.hour)}</time><b>${x.hold ? '--' : x.score.toFixed(3)}</b><span class="${x.hold ? 'h' : x.flag ? 'f' : ''}">${x.hold ? 'hold, not enough readings' : x.flag ? 'ask a person to look' : 'no model flag'}${x.event ? ` <span class="r">· ${x.event} report</span>` : ''}</span></div>`).join('');
}

function drawChart(completed){
  const svg = $('chart'); const W=720,H=330,L=52,R=16,T=18,B=44; const pw=W-L-R, ph=H-T-B;
  const n = win.hours.length; const lo=0.3, hi=0.8;
  const x = i => L + (n === 1 ? pw/2 : i/(n-1)*pw); const y = v => T + ph - (v-lo)/(hi-lo)*ph;
  let s = '';
  win.hours.forEach((h,i) => { if (h.event) s += `<rect x="${x(i)-pw/(n-1)/2}" y="${T}" width="${pw/(n-1)}" height="${ph}" fill="rgba(167,139,250,.18)"/>`; });
  [0.3,0.4,0.5,0.6,0.7,0.8].forEach(v => { s += `<line x1="${L}" x2="${L+pw}" y1="${y(v)}" y2="${y(v)}" stroke="#2A2F3A"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" fill="#6B7482" font-size="11">${v.toFixed(1)}</text>`; });
  s += `<line x1="${L}" x2="${L+pw}" y1="${y(DATA.cutoff)}" y2="${y(DATA.cutoff)}" stroke="#4ADE80" stroke-width="1.5" stroke-dasharray="6 4"/><text x="${L+pw-2}" y="${y(DATA.cutoff)-6}" text-anchor="end" fill="#4ADE80" font-size="11">review line ${DATA.cutoff.toFixed(3)}</text>`;
  const pts = completed.map((h,i) => h.hold ? null : `${x(i)},${y(h.score)}`);
  let path = '', open = false; pts.forEach(p => { if (!p) { open = false; return; } path += (open ? ' L' : ' M') + p; open = true; });
  if (path) s += `<path d="${path}" fill="none" stroke="#38BDF8" stroke-width="1.6"/>`;
  completed.forEach((h,i) => { if (h.hold) { s += `<line x1="${x(i)}" x2="${x(i)}" y1="${T+ph-10}" y2="${T+ph}" stroke="#A78BFA" stroke-width="2"/>`; return; }
    s += `<circle cx="${x(i)}" cy="${y(h.score)}" r="${h.flag ? 4.5 : 3}" fill="${h.flag ? '#FBBF24' : '#38BDF8'}"><title>${fmtHour(h.hour)}: ${h.score.toFixed(4)}${h.flag ? ' · ask a person to look' : ''}</title></circle>`; });
  if (win.reported_at) { const ri = win.hours.findIndex(h => h.event); if (ri >= 0) s += `<text x="${x(ri)}" y="${T-5}" text-anchor="middle" fill="#A78BFA" font-size="11">leak reported ${win.reported_at.slice(-5)}</text>`; }
  [0, Math.floor((n-1)/2), n-1].forEach(i => { s += `<text x="${x(i)}" y="${H-14}" text-anchor="${i===0?'start':i===n-1?'end':'middle'}" fill="#6B7482" font-size="11">${fmtHour(win.hours[i].hour)}</text>`; });
  svg.innerHTML = s;
}
init();
</script>
</body>
</html>
"""


def main() -> None:
    payload = build_payload()
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")).replace("</", "<\\/"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    hours = sum(len(w["hours"]) for w in payload["windows"])
    print(f"Wrote {OUTPUT.relative_to(PROJECT_DIR)} ({OUTPUT.stat().st_size / 1e3:.0f} kB): "
          f"{len(payload['windows'])} windows, {hours} hours, review line {payload['cutoff_text']}")


if __name__ == "__main__":
    main()
