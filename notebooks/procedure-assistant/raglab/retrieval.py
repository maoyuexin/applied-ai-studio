"""Asking a question, and scoring whether the answer came back.

Two different things get measured, and keeping them apart is the whole point of
this lab.

``hit@k``  - a chunk in the top *k* carries the **gold citation**. Right rule.
``sec@k``  - a chunk in the top *k* comes from the **gold section**, whatever
             paragraph label it carries. Right text.

They usually move together. When they come apart - right text, wrong rule - the
system is at its most dangerous, because the passage on screen reads correctly
and the number stamped on it sends a technician to a rule that does not say
that. Stage 5 makes them come apart on purpose.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import config


def section_of(citation: str) -> str:
    """``29 CFR 1910.147(c)(4)(ii)`` -> ``29 CFR 1910.147``; page cites unchanged."""
    return citation.split("(")[0].split("[")[0].strip()


def search(retriever, question: str, k: int = config.TOP_K_SCORED) -> pd.DataFrame:
    """The retrieval result a person would actually be shown."""
    hits = retriever.search(question, k)
    rows = []
    for rank, (position, score) in enumerate(hits, 1):
        chunk = retriever.chunks.iloc[position]
        rows.append({
            "Rank": rank,
            "Score": round(float(score), 4),
            "Citation": chunk["citation"],
            "Source": chunk["source"],
            "Passage": chunk["text"],
        })
    return pd.DataFrame(rows)


def show(retriever, question: str, k: int = config.TOP_K_SHOWN,
         width: int = 260) -> pd.DataFrame:
    frame = search(retriever, question, k)
    frame["Passage"] = frame["Passage"].str.slice(0, width) + "..."
    return frame


def evaluate(retriever, questions: pd.DataFrame,
             ks: tuple[int, ...] = (1, 5)) -> pd.DataFrame:
    """Score one retriever over the evaluation set, one row per question."""
    records = []
    latencies = []
    for row in questions.to_dict("records"):
        gold = [g for g in str(row["gold_citations"]).split("|") if g]
        started = time.perf_counter()
        hits = retriever.search(row["question"], max(ks))
        latencies.append(time.perf_counter() - started)
        citations = [set(retriever.chunks.iloc[i]["citations"]) for i, _ in hits]
        sections = [{section_of(c) for c in group} for group in citations]
        gold_sections = {section_of(g) for g in gold}
        record = {
            "qid": row["qid"], "bucket": row["bucket"], "question": row["question"],
            "top_score": float(hits[0][1]) if hits else 0.0,
            "top_citation": retriever.chunks.iloc[hits[0][0]]["citation"] if hits else "",
            "gold": "|".join(gold), "n_gold": len(gold),
        }
        for k in ks:
            got = set().union(*citations[:k]) if citations[:k] else set()
            got_sections = set().union(*sections[:k]) if sections[:k] else set()
            if gold:
                record[f"hit@{k}"] = int(any(g in got for g in gold))
                record[f"sec@{k}"] = int(bool(gold_sections & got_sections))
                record[f"cov@{k}"] = sum(1 for g in gold if g in got) / len(gold)
            else:
                record[f"hit@{k}"] = np.nan
                record[f"sec@{k}"] = np.nan
                record[f"cov@{k}"] = np.nan
        records.append(record)
    frame = pd.DataFrame(records)
    frame.attrs["query_ms"] = 1000 * float(np.mean(latencies))
    frame.attrs["retriever"] = retriever.name
    frame.attrs["display"] = retriever.display
    return frame


ANSWERABLE = ("A", "B", "C")


def overall(results: pd.DataFrame, buckets: tuple[str, ...] = ANSWERABLE) -> dict:
    part = results[results["bucket"].isin(buckets)]
    return {
        "questions": len(part),
        "hit@1": round(part["hit@1"].mean(), 3),
        "hit@5": round(part["hit@5"].mean(), 3),
        "cov@5": round(part["cov@5"].mean(), 3),
        "sec@1": round(part["sec@1"].mean(), 3),
        "sec@5": round(part["sec@5"].mean(), 3),
        "query_ms": round(results.attrs.get("query_ms", float("nan")), 2),
    }


def leaderboard(results_by_retriever: dict) -> pd.DataFrame:
    """The head-to-head table over the 45 answerable questions."""
    rows = []
    for display, results in results_by_retriever.items():
        summary = overall(results)
        rows.append({
            "Retriever": display,
            "Questions": summary["questions"],
            "hit@1": summary["hit@1"], "hit@5": summary["hit@5"],
            "coverage@5": summary["cov@5"],
            "sec@1": summary["sec@1"], "sec@5": summary["sec@5"],
            "Query time": f"{summary['query_ms']:.1f} ms",
        })
    return pd.DataFrame(rows)


def per_bucket(results_by_retriever: dict,
               buckets: tuple[str, ...] = ("A", "B", "C", "E")) -> pd.DataFrame:
    rows = []
    for bucket in buckets:
        row = {"Bucket": f"{bucket} - {config.BUCKETS[bucket][0]}"}
        for display, results in results_by_retriever.items():
            part = results[results["bucket"] == bucket]
            row["n"] = len(part)
            row[f"{display} hit@1"] = round(part["hit@1"].mean(), 3)
            row[f"{display} hit@5"] = round(part["hit@5"].mean(), 3)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def retriever_comparison(results_by_retriever: dict) -> go.Figure:
    """hit@1 and hit@5 for both retrievers on the 45 answerable questions."""
    figure = go.Figure()
    metrics = ["hit@1", "hit@5", "sec@1", "sec@5"]
    labels = ["Right rule,<br>top 1", "Right rule,<br>top 5",
              "Right text,<br>top 1", "Right text,<br>top 5"]
    for display, results in results_by_retriever.items():
        summary = overall(results)
        name = results.attrs.get("retriever", "")
        values = [summary[m] for m in metrics]
        figure.add_bar(
            x=labels, y=values, name=display,
            marker_color=config.RETRIEVER_COLORS.get(name, config.COLOR_MUTED),
            text=[f"{v:.1%}" for v in values], textposition="outside",
            hovertemplate="%{fullData.name}<br>%{y:.1%} of 45 answerable questions"
                          "<extra></extra>")
    figure.update_yaxes(title="Share of the 45 answerable questions",
                        tickformat=".0%", range=[0, 1.05])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=-0.16))
    return config.layout(
        figure,
        "On technician-phrased questions the embedding model wins on every measure",
        height=470)


def question_phrasing_figure(measured: dict) -> go.Figure:
    """The same retriever, the same corpus, two ways of writing the questions."""
    labels = ["Questions copied from<br>the passage text<br>(the research phase)",
              "Questions phrased the way<br>a technician talks<br>(this evaluation set)"]
    tfidf = [measured["research_tfidf_hit1"], measured["technician_tfidf_hit1"]]
    minilm = [np.nan, measured["technician_minilm_hit1"]]
    figure = go.Figure()
    figure.add_bar(x=labels, y=tfidf, name="TF-IDF word counts",
                   marker_color=config.COLOR_WARN,
                   text=[f"{v:.0%}" if v == v else "" for v in tfidf],
                   textposition="outside",
                   hovertemplate="TF-IDF hit@1 %{y:.1%}<extra></extra>")
    figure.add_bar(x=labels, y=minilm, name="MiniLM embeddings",
                   marker_color=config.COLOR_PRIMARY,
                   text=[f"{v:.0%}" if v == v else "not measured" for v in minilm],
                   textposition="outside",
                   hovertemplate="MiniLM hit@1 %{y:.1%}<extra></extra>")
    figure.add_annotation(
        x=labels[0], y=measured["research_tfidf_hit1"],
        text="a keyword matcher handed the answer", showarrow=True, arrowhead=2,
        ax=0, ay=-45, font=dict(size=12, color=config.COLOR_DARK))
    figure.update_yaxes(title="hit@1 - the gold citation is the top result",
                        tickformat=".0%", range=[0, 1.08])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=-0.2))
    return config.layout(
        figure,
        "The same retriever scores 90% or 33% depending on who wrote the questions",
        height=470)


def score_distribution(results_by_bucket: pd.DataFrame) -> go.Figure:
    """Top-1 similarity per bucket - the evidence behind the refusal threshold."""
    figure = go.Figure()
    for bucket in config.BUCKET_ORDER:
        part = results_by_bucket[results_by_bucket["bucket"] == bucket]
        figure.add_trace(go.Box(
            y=part["top_score"], name=f"{bucket} (n={len(part)})",
            marker_color=config.BUCKET_COLORS[bucket], boxpoints="all",
            jitter=0.45, pointpos=0, width=0.55,
            hovertemplate="%{text}<br>top-1 score %{y:.3f}<extra></extra>",
            text=part["qid"]))
    figure.add_hline(y=config.REFUSAL_TAU, line_color=config.COLOR_DARK,
                     line_dash="dash", line_width=2)
    figure.add_annotation(x=1.0, xref="paper", y=config.REFUSAL_TAU,
                          text=f"tau = {config.REFUSAL_TAU}", showarrow=False,
                          yshift=12, xanchor="right",
                          font=dict(size=12, color=config.COLOR_DARK))
    figure.update_yaxes(title="Top-1 cosine similarity")
    figure.update_xaxes(title="Question bucket")
    figure.update_layout(showlegend=False)
    return config.layout(
        figure,
        "Bucket E sits with the answerable questions - a score rule cannot see it",
        height=480)
