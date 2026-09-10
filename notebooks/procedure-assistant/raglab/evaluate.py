"""The evaluation set, the refusal policy, and the duplicate-corpus experiment.

Four metrics, in the order they matter for a safety assistant:

1. **retrieval hit@k** - did the right passage come back at all;
2. **citation correctness** - does the passage carry the rule number a person
   can look up. This is the headline safety metric, because a wrong citation is
   the failure a reader cannot detect;
3. **unsupported-claim rate** - does the drafted answer assert anything the
   retrieved passages do not contain;
4. **correct-refusal rate** - the one everyone forgets. A system that answers
   every question is not a good system; it is an unmeasured one.

The 60 questions are deliberately *not* paraphrases of the passages. They are
written the way a technician asks, which is the difference between a benchmark
and a demonstration.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import config, retrieval

# ---------------------------------------------------------------------------
# The evaluation set
# ---------------------------------------------------------------------------

def load_eval(path=None) -> pd.DataFrame:
    frame = pd.read_csv(path or config.EVAL_CSV).fillna("")
    frame["gold_list"] = frame["gold_citations"].apply(
        lambda s: [g for g in str(s).split("|") if g])
    return frame


def load_msha_eval() -> pd.DataFrame:
    frame = pd.read_csv(config.EVAL_MSHA_CSV).fillna("")
    frame["twin"] = frame["gold_citations"].str.replace("30 CFR 56.", "30 CFR 57.",
                                                        regex=False)
    return frame


def bucket_table(questions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ground_truth = {
        "A": "the gold citation string", "B": "a set of citations",
        "C": "a citation plus the exact value",
        "D": "a refusal", "E": "a bounded refusal that names the standard"}
    grading = {"A": "any-of", "B": "any-of for hit, fraction for coverage",
               "C": "any-of plus the value string", "D": "binary", "E": "binary"}
    for bucket in config.BUCKET_ORDER:
        part = questions[questions["bucket"] == bucket]
        rows.append({
            "Bucket": bucket,
            "What it tests": config.BUCKETS[bucket][0],
            "Questions": len(part),
            "Correct answer is": ground_truth[bucket],
            "Graded": grading[bucket],
        })
    return pd.DataFrame(rows)


def validate_gold(questions: pd.DataFrame, chunks: pd.DataFrame) -> dict:
    """Every gold citation must name a chunk that exists, or the score is fiction."""
    available: set[str] = set()
    for group in chunks["citations"]:
        available.update(group)
    gold = [g for group in questions["gold_list"] for g in group]
    missing = sorted({g for g in gold if g not in available})

    value_misses = []
    for row in questions[questions["bucket"] == "C"].to_dict("records"):
        text = " ".join(
            chunks.loc[chunks["citations"].apply(lambda cs: any(g in cs for g in row["gold_list"])),
                       "text"])
        for numeral in re.findall(r"\d[\d,\.]*", str(row["gold_value"])):
            if numeral.replace(",", "") not in text.replace(",", ""):
                value_misses.append((row["qid"], numeral))
    return {
        "gold_citations": len(gold),
        "missing_from_the_chunk_table": len(missing),
        "missing_examples": missing[:5],
        "numeric_values_checked": int((questions["bucket"] == "C").sum()),
        "values_not_found_in_the_gold_chunk": len(value_misses),
    }


# ---------------------------------------------------------------------------
# The refusal policy
# ---------------------------------------------------------------------------

INCORPORATION = re.compile(
    r"(incorporated by reference|shall conform to the specifications|"
    r"shall meet the design specifications|"
    r"in accordance with (the )?(ANSI|NFPA|ASTM|ASME|CGA|AWS|API)|"
    r"complying with the American National Standard|requirements of ANSI)", re.I)
NAMED_STANDARD = re.compile(
    r"\b(?:ANSI|NFPA|ASTM|ASME|CGA|AWS|API|USAS|ASA)\s*(?:No\.\s*)?"
    r"[A-Z]?\s?[0-9][0-9A-Za-z\.\-]*")
ASKS_FOR_SPEC = re.compile(
    r"\b(rating|specification|specs?|pressure|design|standard|level|bright|"
    r"connection|required|require|must meet|conform|comply|value|limit|"
    r"size|dimension|stored|handled|rated)\b", re.I)


def policy_signals(retriever, questions: pd.DataFrame,
                   context_chunks: int = 3) -> pd.DataFrame:
    """For each question: the top score, and whether the two-rule policy fires.

    Rule 1 is a confidence rule. Rule 2 exists because bucket E is invisible to
    rule 1 by construction: the passage that answers an E question *is* in the
    corpus, retrieves confidently, and names a standard the corpus does not
    contain.
    """
    rows = []
    for row in questions.to_dict("records"):
        hits = retriever.search(row["question"], config.TOP_K_SCORED)
        context = " ".join(retriever.chunks.iloc[i]["text"] for i, _ in hits[:context_chunks])
        standards = sorted({m.group(0) for m in NAMED_STANDARD.finditer(context)})
        rows.append({
            "qid": row["qid"], "bucket": row["bucket"], "question": row["question"],
            "top_score": float(hits[0][1]),
            "incorporates_standard": bool(INCORPORATION.search(context)),
            "names_standard": bool(standards),
            "asks_for_spec": bool(ASKS_FOR_SPEC.search(row["question"])),
            "standards": standards[:3],
        })
    return pd.DataFrame(rows)


def apply_policy(signals: pd.DataFrame, tau: float = config.REFUSAL_TAU) -> pd.Series:
    low_confidence = signals["top_score"] < tau
    incorporated = (signals["incorporates_standard"] & signals["names_standard"]
                    & signals["asks_for_spec"])
    return low_confidence | incorporated


def refusal_reason(signals: pd.DataFrame, tau: float = config.REFUSAL_TAU) -> pd.Series:
    incorporated = (signals["incorporates_standard"] & signals["names_standard"]
                    & signals["asks_for_spec"])
    return np.where(signals["top_score"] < tau, "refused_low_confidence",
                    np.where(incorporated, "refused_incorporated_by_reference",
                             "answered"))


def score_rule_only(signals: pd.DataFrame, taus) -> pd.DataFrame:
    """What a confidence threshold alone can do - the reason rule 2 exists."""
    rows = []
    for tau in taus:
        rows.append({
            "tau": round(float(tau), 2),
            "Correct refusal, D": _rate(signals, "D", signals["top_score"] < tau),
            "Correct refusal, E": _rate(signals, "E", signals["top_score"] < tau),
            "False refusal, A+B+C": _rate(signals, ("A", "B", "C"),
                                          signals["top_score"] < tau),
        })
    return pd.DataFrame(rows)


def _rate(signals: pd.DataFrame, buckets, mask) -> float:
    buckets = (buckets,) if isinstance(buckets, str) else tuple(buckets)
    part = signals["bucket"].isin(buckets)
    return round(float(mask[part].mean()), 3)


def policy_sweep(signals: pd.DataFrame, taus=(0.44, 0.46, 0.48, 0.50, 0.54, 0.56)
                 ) -> pd.DataFrame:
    """The two-rule policy across candidate thresholds, with counts."""
    rows = []
    for tau in taus:
        refuse = apply_policy(signals, tau)
        row = {"tau": round(float(tau), 2)}
        for label, buckets in (("D - outside the corpus", ("D",)),
                               ("E - incorporated by reference", ("E",))):
            part = signals["bucket"].isin(buckets)
            row[f"Correct refusal, {label.split(' -')[0]}"] = (
                f"{refuse[part].mean():.1%} ({int(refuse[part].sum())}/{int(part.sum())})")
        part = signals["bucket"].isin(("A", "B", "C"))
        row["False refusal, A+B+C"] = (
            f"{refuse[part].mean():.1%} ({int(refuse[part].sum())}/{int(part.sum())})")
        rows.append(row)
    return pd.DataFrame(rows)


def policy_result(signals: pd.DataFrame, tau: float = config.REFUSAL_TAU) -> dict:
    refuse = apply_policy(signals, tau)
    outcome = {}
    for bucket in config.BUCKET_ORDER:
        part = signals["bucket"] == bucket
        outcome[bucket] = {
            "questions": int(part.sum()),
            "refused": int(refuse[part].sum()),
            "rate": round(float(refuse[part].mean()), 3),
        }
    answerable = signals["bucket"].isin(("A", "B", "C"))
    return {
        "tau": tau,
        "by_bucket": outcome,
        "correct_refusal_D": outcome["D"]["rate"],
        "correct_refusal_E": outcome["E"]["rate"],
        "false_refusal_rate": round(float(refuse[answerable].mean()), 3),
        "false_refusals": sorted(signals.loc[answerable & refuse, "qid"]),
        "missed_refusals": sorted(
            signals.loc[signals["bucket"].isin(("D", "E")) & ~refuse, "qid"]),
    }


# ---------------------------------------------------------------------------
# The duplicate-corpus experiment
# ---------------------------------------------------------------------------

def duplicate_similarity(paragraphs: pd.DataFrame) -> dict:
    """How alike 30 CFR 56 and 30 CFR 57 actually are, measured not assumed."""
    import difflib

    def section_text(part: str) -> dict:
        rows = paragraphs[paragraphs["source"] == f"30 CFR part {part}"]
        grouped = rows.groupby("section")["text"].apply(" ".join)
        return {k.split()[-1].split(".", 1)[-1]: v for k, v in grouped.items()}

    left, right = section_text("56"), section_text("57")
    shared = sorted(set(left) & set(right))
    identical = 0
    similarities = []
    for key in shared:
        a, b = left[key], right[key]
        if a == b:
            identical += 1
            similarities.append(1.0)
        else:
            similarities.append(difflib.SequenceMatcher(None, a, b).ratio())
    return {
        "shared_section_numbers": len(shared),
        "byte_identical": identical,
        "at_least_95_percent_similar": int(sum(s >= 0.95 for s in similarities)),
        "mean_similarity": round(float(np.mean(similarities)), 3),
    }


def duplicate_measure(retriever, questions: pd.DataFrame,
                      ks: tuple[int, ...] = (1, 5)) -> dict:
    """Separate 'found the right text' from 'cited the right rule'.

    ``text_hit`` counts a Part 57 twin as correct - the sentence on screen is
    the right sentence. ``cite_hit`` requires the Part 56 citation the question
    was asked about. The gap between them is the damage.
    """
    counts = {f"text_hit@{k}": 0 for k in ks} | {f"cite_hit@{k}": 0 for k in ks}
    wrong_rule = 0
    detail = []
    for row in questions.to_dict("records"):
        gold, twin = row["gold_citations"], row["twin"]
        hits = retriever.search(row["question"], max(ks))
        sections = [[retrieval.section_of(c) for c in retriever.chunks.iloc[i]["citations"]]
                    for i, _ in hits]
        for k in ks:
            flat = set(sum(sections[:k], []))
            counts[f"cite_hit@{k}"] += int(gold in flat)
            counts[f"text_hit@{k}"] += int(gold in flat or twin in flat)
        top = set(sections[0])
        swapped = gold not in top and twin in top
        wrong_rule += int(swapped)
        detail.append({"qid": row["qid"], "gold": gold,
                       "top_citation": retriever.chunks.iloc[hits[0][0]]["citation"],
                       "right_text_wrong_rule": swapped})
    n = len(questions)
    result = {key: round(value / n, 3) for key, value in counts.items()}
    result["questions"] = n
    result["right_text_wrong_rule@1"] = round(wrong_rule / n, 3)
    result["detail"] = detail
    return result


def duplicate_table(results: dict) -> pd.DataFrame:
    rows = []
    for (corpus, retriever), result in results.items():
        rows.append({
            "Corpus": corpus, "Retriever": retriever,
            "Right text, top 1": result["text_hit@1"],
            "Right rule, top 1": result["cite_hit@1"],
            "Right text, top 5": result["text_hit@5"],
            "Right rule, top 5": result["cite_hit@5"],
            "Right text but wrong rule": f"{result['right_text_wrong_rule@1']:.1%}",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def bucket_figure(questions: pd.DataFrame) -> go.Figure:
    counts = [int((questions["bucket"] == b).sum()) for b in config.BUCKET_ORDER]
    labels = [f"{b}<br>{config.BUCKETS[b][0]}" for b in config.BUCKET_ORDER]
    answerable = ["Answerable" if b in "ABC" else "Correct answer is a refusal"
                  for b in config.BUCKET_ORDER]
    figure = go.Figure(go.Bar(
        x=labels, y=counts,
        marker_color=[config.BUCKET_COLORS[b] for b in config.BUCKET_ORDER],
        text=counts, textposition="outside", customdata=answerable,
        hovertemplate="%{x}<br>%{y} questions<br>%{customdata}<extra></extra>"))
    figure.add_vrect(x0=2.5, x1=4.5, fillcolor=config.COLOR_ALERT, opacity=0.07,
                     line_width=0)
    figure.add_annotation(x=3.5, y=max(counts) * 0.95,
                          text="15 of 60 questions have no answer in the corpus",
                          showarrow=False, font=dict(size=12, color=config.COLOR_DARK))
    figure.update_yaxes(title="Questions", range=[0, max(counts) * 1.2])
    figure.update_xaxes(title="")
    return config.layout(
        figure, "A quarter of the evaluation set is questions the system must refuse",
        height=450)


def sweep_figure(signals: pd.DataFrame) -> go.Figure:
    """Both refusal rules across thresholds, with the chosen knee marked."""
    taus = np.round(np.arange(0.36, 0.62, 0.01), 2)
    correct_d, correct_e, false_refusal = [], [], []
    for tau in taus:
        result = policy_result(signals, float(tau))
        correct_d.append(result["correct_refusal_D"])
        correct_e.append(result["correct_refusal_E"])
        false_refusal.append(result["false_refusal_rate"])
    figure = go.Figure()
    figure.add_scatter(x=taus, y=correct_d, name="Correct refusal, bucket D",
                       mode="lines+markers", line=dict(color=config.COLOR_ACCENT, width=3),
                       hovertemplate="tau %{x}<br>%{y:.1%} of the 8 D questions refused"
                                     "<extra></extra>")
    figure.add_scatter(x=taus, y=correct_e, name="Correct refusal, bucket E",
                       mode="lines+markers", line=dict(color=config.COLOR_PRIMARY, width=3,
                                                       dash="dot"),
                       hovertemplate="tau %{x}<br>%{y:.1%} of the 7 E questions refused"
                                     "<extra></extra>")
    figure.add_scatter(x=taus, y=false_refusal, name="False refusal, answerable questions",
                       mode="lines+markers", line=dict(color=config.COLOR_ALERT, width=3),
                       hovertemplate="tau %{x}<br>%{y:.1%} of the 45 answerable questions"
                                     " wrongly refused<extra></extra>")
    figure.add_vline(x=config.REFUSAL_TAU, line_dash="dash", line_width=2,
                     line_color=config.COLOR_DARK)
    figure.add_annotation(x=config.REFUSAL_TAU, y=1.02, yref="paper",
                          text=f"chosen tau = {config.REFUSAL_TAU}", showarrow=False,
                          xanchor="left", font=dict(size=12, color=config.COLOR_DARK))
    figure.update_yaxes(title="Share of that bucket", tickformat=".0%", range=[-0.03, 1.08])
    figure.update_xaxes(title="Refusal threshold tau (top-1 cosine similarity)")
    figure.update_layout(legend=dict(orientation="h", y=-0.2))
    return config.layout(
        figure, "tau = 0.48 is the knee: high correct refusal, false refusal under 5%",
        height=470)


def duplicate_figure(results: dict) -> go.Figure:
    """Right text holds; right rule collapses. Same retriever, bigger corpus."""
    figure = go.Figure()
    # Keep each retriever's before/after pair adjacent, in the order the caller
    # supplied them, so the plot never depends on a hard-coded display name.
    retrievers = list(dict.fromkeys(name for _, name in results))
    corpora = list(dict.fromkeys(label for label, _ in results))
    order = [(label, name) for name in retrievers for label in corpora]
    labels = [f"{r}<br>{c}" for c, r in order]
    text_hits = [results[key]["text_hit@1"] for key in order]
    cite_hits = [results[key]["cite_hit@1"] for key in order]
    figure.add_bar(x=labels, y=text_hits, name="Right text (Part 56 or its twin)",
                   marker_color=config.COLOR_MUTED,
                   text=[f"{v:.1%}" for v in text_hits], textposition="outside",
                   hovertemplate="%{x}<br>right text %{y:.1%}<extra></extra>")
    figure.add_bar(x=labels, y=cite_hits, name="Right rule (Part 56 citation)",
                   marker_color=config.COLOR_ALERT,
                   text=[f"{v:.1%}" for v in cite_hits], textposition="outside",
                   hovertemplate="%{x}<br>right rule %{y:.1%}<extra></extra>")
    figure.update_yaxes(title="Share of the 30 MSHA questions, top-1",
                        tickformat=".0%", range=[0, 1.05])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=-0.2))
    return config.layout(
        figure,
        "Adding a near-identical regulation leaves the text intact and destroys the citation",
        height=480)


def collateral_figure(before: dict, after: dict) -> go.Figure:
    """The aggregate score barely moves while one domain is destroyed."""
    labels = ["Main 60-question set<br>(no MSHA questions)",
              "The 30 MSHA questions<br>(citation, top 1)"]
    before_values = [before["main_hit@5"], before["msha_cite@1"]]
    after_values = [after["main_hit@5"], after["msha_cite@1"]]
    figure = go.Figure()
    figure.add_bar(x=labels, y=before_values, name="Part 56 only",
                   marker_color=config.COLOR_PRIMARY,
                   text=[f"{v:.1%}" for v in before_values], textposition="outside",
                   hovertemplate="%{x}<br>%{y:.1%}<extra>Part 56 only</extra>")
    figure.add_bar(x=labels, y=after_values, name="Part 56 + Part 57",
                   marker_color=config.COLOR_ALERT,
                   text=[f"{v:.1%}" for v in after_values], textposition="outside",
                   hovertemplate="%{x}<br>%{y:.1%}<extra>Part 56 + Part 57</extra>")
    for position, (b, a) in enumerate(zip(before_values, after_values)):
        figure.add_annotation(x=position, y=max(b, a) + 0.12,
                              text=f"{a - b:+.1%}", showarrow=False,
                              font=dict(size=13, color=config.COLOR_DARK))
    figure.update_yaxes(title="Score", tickformat=".0%", range=[0, 1.12])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=-0.18))
    return config.layout(
        figure,
        "The dashboard average barely moves while one domain stops working",
        height=460)
