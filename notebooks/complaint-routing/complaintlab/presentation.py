"""Readable, offline notebook displays built from the existing explanation helpers."""

from __future__ import annotations

from html import escape

import pandas as pd
from IPython.display import HTML

from . import config, explain


STYLE = """
<style>
.complaint-view {
  --ink: #20242b; --muted: #505761; --line: #d8dde2;
  --teal: #08766d; --amber: #845400; --red: #b3261e;
  box-sizing: border-box; width: 100%; min-width: 0;
  color: var(--ink); background: #fff; font: 16px/1.6 Arial, sans-serif;
  letter-spacing: 0; overflow-wrap: anywhere;
}
.complaint-view *, .complaint-view *::before, .complaint-view *::after { box-sizing: border-box; }
.complaint-view .case-heading { border-top: 4px solid var(--teal); padding: 20px 0 12px; }
.complaint-view .eyebrow { margin: 0 0 6px; color: var(--muted); font-size: 13px; font-weight: 700; }
.complaint-view h3 { margin: 0 0 14px; font-size: 24px; line-height: 1.25; font-weight: 700; }
.complaint-view h4 { margin: 0 0 14px; font-size: 18px; line-height: 1.4; }
.complaint-view p { margin: 0 0 14px; }
.complaint-view .metadata { display: flex; flex-wrap: wrap; gap: 8px 24px; color: var(--muted); font-size: 14px; }
.complaint-view blockquote {
  margin: 14px 0 18px; padding: 8px 0 8px 20px; border-left: 3px solid var(--line);
  color: var(--ink); font: 19px/1.7 Georgia, serif; white-space: pre-wrap;
}
.complaint-view details { border-top: 1px solid var(--line); padding: 8px 0; }
.complaint-view summary { cursor: pointer; min-height: 44px; padding: 8px 0; font-weight: 700; }
.complaint-view summary:focus-visible { outline: 3px solid var(--teal); outline-offset: 3px; }
.complaint-view .note { color: var(--muted); font-size: 14px; }
.complaint-view .decision { border-top: 1px solid var(--line); padding: 20px 0 16px; }
.complaint-view .decision-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(180px, 0.7fr); gap: 24px; }
.complaint-view .route-label { color: var(--teal); font-size: 14px; font-weight: 700; }
.complaint-view .route-label.triage { color: var(--amber); }
.complaint-view .team-name { font-size: 24px; line-height: 1.3; font-weight: 700; }
.complaint-view .confidence-value { font-size: 32px; line-height: 1.2; font-variant-numeric: tabular-nums; }
.complaint-view .confidence-track { position: relative; height: 12px; margin: 14px 0 8px; background: #edf0f2; }
.complaint-view .confidence-fill { display: block; height: 100%; background: var(--teal); }
.complaint-view .confidence-fill.triage { background: #aa710e; }
.complaint-view .cutoff { position: absolute; top: -5px; bottom: -5px; width: 2px; background: var(--ink); }
.complaint-view .scale { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 13px; }
.complaint-view .next-step { margin-top: 18px; padding: 12px 0; border-top: 1px solid var(--line); }
.complaint-view .result { margin: 8px 0 16px; padding: 14px 18px; border-left: 4px solid var(--teal); background: #edf7f4; }
.complaint-view .result.mismatch { border-color: var(--red); background: #fff1ee; }
.complaint-view .result p:last-child { margin-bottom: 0; }
.complaint-view dl { margin: 0 0 12px; }
.complaint-view dt { color: var(--muted); font-size: 14px; }
.complaint-view dd { margin: 0 0 12px; }
.complaint-view .bar-list { display: grid; gap: 12px; padding: 10px 0 18px; }
.complaint-view .bar-row { display: grid; grid-template-columns: minmax(130px, 1fr) minmax(90px, 2fr) 68px; gap: 12px; align-items: center; }
.complaint-view .bar-name { font-size: 15px; line-height: 1.35; }
.complaint-view .bar-track { background: #edf0f2; height: 14px; min-width: 0; }
.complaint-view .bar-fill { display: block; height: 100%; background: #397685; }
.complaint-view .bar-value { text-align: right; font-size: 15px; font-variant-numeric: tabular-nums; }
.complaint-view .bar-row:first-child .bar-name { font-weight: 700; }
.complaint-view .word-bars .bar-fill { background: #915713; }
@media (max-width: 600px) {
  .complaint-view h3 { font-size: 22px; }
  .complaint-view blockquote { font-size: 18px; padding-left: 12px; }
  .complaint-view .decision-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .complaint-view .bar-row { grid-template-columns: minmax(0, 1fr) 64px; gap: 6px 10px; }
  .complaint-view .bar-name { grid-column: 1 / -1; }
}
</style>
"""


def _display(content: str, kind: str, complaint_id: str = "") -> HTML:
    return HTML(
        STYLE + f'<section class="complaint-view" data-view="{escape(kind)}" '
        f'data-complaint-id="{escape(complaint_id)}">{content}</section>'
    )


def complaint_excerpt(row: pd.Series, number: int, title: str, limit: int = 1100) -> HTML:
    """Present the original excerpt, with the complete text available if truncated."""
    narrative = str(row[config.TEXT_COLUMN])
    excerpt = narrative[:limit]
    full_text = ""
    if len(narrative) > limit:
        full_text = (
            f'<p class="note">Excerpt: first {limit:,} of {len(narrative):,} characters.</p>'
            f'<details><summary>Full complaint</summary><blockquote>{escape(narrative)}</blockquote></details>'
        )
    return _display(
        f'<header class="case-heading"><p class="eyebrow">EXAMPLE {number:02d} '
        f' / COMPLAINT {escape(str(row["complaint_id"]))}</p><h3>{escape(title)}</h3>'
        f'<div class="metadata"><span>Received {escape(str(row["date_received"]))}</span>'
        f'<span>{len(narrative):,} characters</span></div></header>'
        f'<p class="eyebrow">WHAT THE CONSUMER WROTE</p>'
        f'<blockquote class="complaint-text">{escape(excerpt)}</blockquote>{full_text}',
        "excerpt", str(row["complaint_id"]),
    )


def routing_decision(pipeline, row: pd.Series) -> HTML:
    """Show existing route facts with the recorded label separate from prediction."""
    facts = explain.route_card(pipeline, row).set_index("Field")["Value"].to_dict()
    probabilities = explain.team_probabilities(pipeline, row[config.TEXT_COLUMN])
    confidence = float(probabilities.iloc[0]["Probability"])
    threshold = config.CONFIDENCE_THRESHOLD
    triage = facts["Route"] == config.ROUTE_TRIAGE
    route_class = "triage" if triage else "auto"
    route_label = "HUMAN TRIAGE" if triage else "AUTO-ROUTE"
    suggested_team = str(facts["Model's team"])
    mismatch = suggested_team != row[config.TARGET]
    result_class = "mismatch" if mismatch else "match"
    comparison = "Suggestion differs from the recorded team" if mismatch else "Suggestion matches the recorded team"
    details = "".join(
        f'<dt>{escape(str(label))}</dt><dd>{escape(str(facts[label]))}</dd>'
        for label in ("Complaint ID", "Received", "CFPB issue field (not shown to the model)", "Characters in the narrative")
    )
    content = (
        f'<div class="decision" data-route="{escape(str(facts["Route"]))}" '
        f'data-confidence="{confidence!r}" data-threshold="{threshold!r}">'
        f'<h4>What the model said</h4><div class="decision-grid"><div>'
        f'<p class="route-label {route_class}">{route_label}</p>'
        f'<p class="eyebrow">SUGGESTED TEAM</p><p class="team-name">{escape(suggested_team)}</p></div>'
        f'<div><p class="eyebrow">CONFIDENCE</p><div class="confidence-value">{confidence:.1%}</div>'
        f'<div class="confidence-track" aria-hidden="true"><span class="confidence-fill {route_class}" '
        f'style="width:{confidence * 100:.6f}%"></span>'
        f'<span class="cutoff" style="left:{threshold * 100:.6f}%"></span></div>'
        f'<div class="scale"><span>0%</span><span>Cutoff {threshold:.0%}</span><span>100%</span></div>'
        f'</div></div><p class="next-step"><strong>What happens next</strong><br>'
        f'{escape(str(facts["What happens next"]))}</p></div>'
        f'<div class="result {result_class}"><p class="eyebrow">RECORDED LABEL / SEPARATE FROM THE PREDICTION</p>'
        f'<p><strong>{escape(str(row[config.TARGET]))}</strong><br>{comparison}</p></div>'
        f'<details><summary>Source details</summary><dl>{details}</dl></details>'
    )
    return _display(content, "decision", str(row["complaint_id"]))


def probability_bars(pipeline, narrative: str) -> HTML:
    """Show all eight probabilities on a common 0-100 percent scale."""
    probabilities = explain.team_probabilities(pipeline, narrative)
    rows = "".join(
        f'<div class="bar-row" data-team="{escape(str(item["Team"]))}" '
        f'data-probability="{float(item["Probability"])!r}">'
        f'<span class="bar-name">{escape(str(item["Team"]))}</span>'
        f'<span class="bar-track" aria-hidden="true"><span class="bar-fill" '
        f'style="width:{item["Probability"] * 100:.6f}%"></span></span>'
        f'<span class="bar-value" title="Probability {item["Probability"]:.4f}">{item["Probability"]:.1%}</span></div>'
        for item in probabilities.to_dict("records")
    )
    return _display(
        '<h4>How the eight teams compare</h4>'
        '<p class="note">All bars use the same 0-100% scale. Values are rounded for display.</p>'
        f'<div class="bar-list probability-bars">{rows}</div>', "probabilities",
    )


def routing_word_bars(pipeline, narrative: str, team: str) -> HTML:
    """Display positive word contributions, not probabilities."""
    words = explain.routing_words(pipeline, narrative, team)
    rows = '<p>No positive word contributions were found.</p>'
    if not words.empty:
        maximum = float(words["Push toward this team"].max())
        rows = "".join(
            f'<div class="bar-row" data-word="{escape(str(item["Word or phrase"]))}" '
            f'data-push="{float(item["Push toward this team"])!r}">'
            f'<span class="bar-name">{escape(str(item["Word or phrase"]))}</span>'
            f'<span class="bar-track" aria-hidden="true"><span class="bar-fill" '
            f'style="width:{item["Push toward this team"] / maximum * 100:.6f}%"></span></span>'
            f'<span class="bar-value">{item["Push toward this team"]:.3f}</span></div>'
            for item in words.to_dict("records")
        )
    return _display(
        f'<h4>Words pushing toward {escape(team)}</h4>'
        '<p class="note">Longer bars mean a stronger push within this complaint. '
        'These values are not percentages or proof that the route is correct.</p>'
        f'<div class="bar-list word-bars">{rows}</div>', "routing-words",
    )