"""How a page of regulation becomes passages an embedding model can read.

A retriever does not search documents. It searches *chunks*: short passages,
each one turned into a list of numbers, each one carrying the citation a person
will have to look up afterwards. Two decisions here do more damage than any
model choice.

**Budget in tokens, not words.** ``all-MiniLM-L6-v2`` reads at most 256
wordpiece tokens. Past that it does not warn, error, or truncate loudly - it
simply computes the passage's meaning from the beginning and discards the rest.
A word-count target does not bound tokens: a maintenance table with dot leaders
(``Intake manifold mounting nuts.. . . . . . . 35 lb-ft``) tokenises every run
of dots separately, so a 150-word target still produced a 3,409-token chunk -
in exactly the passages where the numeric answers live.

**Never let a chunk cross a section boundary.** A chunk that packs the end of
one rule and the start of the next has no single correct citation.
"""

from __future__ import annotations

import functools
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import config

WORD_TARGETS = {"words_60": 60, "words_150": 150}
CONFIG_LABELS = {
    "words_60": "~60-word target",
    "words_150": "~150-word target",
    "section": "Whole section, one chunk",
    "tokens_240": "240-token budget (deployed)",
}
CONFIG_ORDER = ["words_60", "words_150", "section", "tokens_240"]


# ---------------------------------------------------------------------------
# Tokenising
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def tokenizer():
    """The encoder's own wordpiece tokenizer - the only honest token counter."""
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(config.EMBEDDER)


def count_tokens(text: str) -> int:
    return len(tokenizer()(text, add_special_tokens=False)["input_ids"])


def count_tokens_batch(texts: list[str], batch: int = 512) -> list[int]:
    tok = tokenizer()
    counts: list[int] = []
    for start in range(0, len(texts), batch):
        encoded = tok(texts[start:start + batch], add_special_tokens=False)["input_ids"]
        counts.extend(len(ids) for ids in encoded)
    return counts


def tokenize_preview(text: str, limit: int = 24) -> pd.DataFrame:
    """Show a short string as the model actually sees it."""
    tok = tokenizer()
    ids = tok(text, add_special_tokens=False)["input_ids"]
    pieces = tok.convert_ids_to_tokens(ids)
    return pd.DataFrame({
        "Position": range(1, len(pieces[:limit]) + 1),
        "Wordpiece token": pieces[:limit],
        "Token id": ids[:limit],
    })


# ---------------------------------------------------------------------------
# Units in, chunks out
# ---------------------------------------------------------------------------

def units_from_paragraphs(paragraphs: pd.DataFrame,
                          include_duplicate: bool = False) -> list[dict]:
    """Paragraph and page-block records -> the packing units, in document order."""
    frame = paragraphs
    if not include_duplicate:
        frame = frame[frame["in_base_corpus"]]
    frame = frame[frame["text"].str.split().str.len() >= 4]
    keep = ["doc_id", "layer", "source", "source_title", "section",
            "citation", "naive_citation", "page", "text", "in_base_corpus"]
    return frame[keep].to_dict("records")


def _split_on_tokens(unit: dict, budget: int) -> list[dict]:
    """Split one over-budget paragraph on sentence boundaries.

    The pieces keep the parent citation and gain a ``[2/3]`` marker, so a
    citation is never invented for a fragment.
    """
    if count_tokens(unit["text"]) <= budget:
        return [unit]
    sentences = re.split(r"(?<=[.;:])\s+", unit["text"])
    parts: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            parts.append(" ".join(buffer))
            buffer.clear()

    for sentence in sentences:
        if buffer and count_tokens(" ".join(buffer) + " " + sentence) > budget:
            flush()
        if count_tokens(sentence) > budget:
            flush()
            words = sentence.split()
            low = 0
            while low < len(words):
                high = low + 1
                while high <= len(words) and count_tokens(" ".join(words[low:high])) <= budget:
                    high += 1
                parts.append(" ".join(words[low:high - 1]))
                low = max(high - 1, low + 1)
        else:
            buffer.append(sentence)
    flush()

    out = []
    for number, part in enumerate(parts, 1):
        piece = dict(unit)
        piece["text"] = part
        piece["cite_base"] = unit["citation"]
        piece["citation"] = "%s [%d/%d]" % (unit["citation"], number, len(parts))
        out.append(piece)
    return out


def _split_on_words(unit: dict, target: int) -> list[dict]:
    words = unit["text"].split()
    if len(words) <= target:
        return [unit]
    sentences = re.split(r"(?<=[.;:])\s+", unit["text"])
    parts: list[str] = []
    buffer: list[str] = []
    for sentence in sentences:
        if buffer and len(" ".join(buffer).split()) + len(sentence.split()) > target:
            parts.append(" ".join(buffer))
            buffer = []
        buffer.append(sentence)
    if buffer:
        parts.append(" ".join(buffer))
    fixed: list[str] = []
    for part in parts:
        if len(part.split()) <= target * 1.6:
            fixed.append(part)
        else:
            hard = part.split()
            for start in range(0, len(hard), target):
                fixed.append(" ".join(hard[start:start + target]))
    out = []
    for number, part in enumerate(fixed, 1):
        piece = dict(unit)
        piece["text"] = part
        if len(fixed) > 1:
            piece["cite_base"] = unit["citation"]
            piece["citation"] = "%s [%d/%d]" % (unit["citation"], number, len(fixed))
        out.append(piece)
    return out


def indexed_text(source_title: str, text: str) -> str:
    """What actually goes into the index: the section heading, then the passage."""
    return ("%s. %s" % (source_title or "", text)).strip()


def build_chunks(units: list[dict], mode: str = "tokens_240") -> list[dict]:
    """Greedy, section-bounded packing under one of the four size policies."""
    if mode == "tokens_240":
        budget = config.TOKEN_BUDGET
        pieces: list[dict] = []
        for unit in units:
            pieces.extend(_split_on_tokens(unit, budget))
    elif mode in WORD_TARGETS:
        target = WORD_TARGETS[mode]
        pieces = []
        for unit in units:
            pieces.extend(_split_on_words(unit, target))
    elif mode == "section":
        pieces = list(units)
    else:
        raise ValueError(f"unknown chunking mode {mode!r}")

    chunks: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        citations = [u.get("cite_base", u["citation"]) for u in current]
        text = " ".join(u["text"] for u in current)
        chunks.append(dict(
            chunk_id="c%05d" % len(chunks),
            doc_id=current[0]["doc_id"], layer=current[0]["layer"],
            source=current[0]["source"], source_title=current[0]["source_title"],
            section=current[0]["section"], citation=citations[0],
            citations=sorted(set(citations)), n_units=len(current),
            page=current[0]["page"], in_base_corpus=current[0]["in_base_corpus"],
            words=len(text.split()), text=text))
        current.clear()

    for unit in pieces:
        if current:
            same_section = unit["section"] == current[0]["section"]
            if not same_section:
                flush()
            elif mode == "tokens_240":
                joined = indexed_text(
                    current[0]["source_title"],
                    " ".join(u["text"] for u in current) + " " + unit["text"])
                if count_tokens(joined) > config.TOKEN_BUDGET:
                    flush()
            elif mode in WORD_TARGETS:
                packed = len(" ".join(u["text"] for u in current).split())
                if packed + len(unit["text"].split()) > WORD_TARGETS[mode]:
                    flush()
        current.append(unit)
    flush()

    for position, chunk in enumerate(chunks):
        chunk["chunk_id"] = "c%05d" % position
    return chunks


def chunk_frame(chunks: list[dict], with_tokens: bool = True) -> pd.DataFrame:
    frame = pd.DataFrame(chunks)
    if with_tokens:
        frame["tokens"] = count_tokens_batch(
            [indexed_text(t, x) for t, x in zip(frame["source_title"].fillna(""),
                                                frame["text"])])
    return frame


# ---------------------------------------------------------------------------
# Reading the committed chunk table
# ---------------------------------------------------------------------------

def load_chunks(include_duplicate: bool = False) -> pd.DataFrame:
    """The committed chunk table. 30 CFR 57 rides along, switched off by default."""
    frame = pd.read_parquet(config.CHUNKS_PARQUET)
    frame["citations"] = frame["citations"].apply(list)
    if not include_duplicate:
        frame = frame[frame["in_base_corpus"]].reset_index(drop=True)
    return frame.reset_index(drop=True)


def chunk_records(frame: pd.DataFrame) -> list[dict]:
    return frame.to_dict("records")


def size_table(evidence: pd.DataFrame) -> pd.DataFrame:
    """The chunk-size comparison, with the number that matters computed here.

    ``Tokens discarded`` is the share of all tokens in the index that fall past
    the model's 256-token window: ``sum(max(0, tokens - 256)) / sum(tokens)``.
    Nothing reports it at build time. The index looks complete either way.
    """
    rows = []
    for mode in CONFIG_ORDER:
        part = evidence[evidence["config"] == mode]
        tokens = part["tokens"].to_numpy()
        over = np.maximum(0, tokens - config.MODEL_TOKEN_WINDOW)
        rows.append({
            "Chunking policy": CONFIG_LABELS[mode],
            "Chunks": len(part),
            "Words (median)": int(np.median(part["words"])),
            "Tokens (median)": int(np.median(tokens)),
            "Tokens (max)": int(tokens.max()),
            "Chunks over 256 tokens": int((tokens > config.MODEL_TOKEN_WINDOW).sum()),
            "Tokens discarded": f"{over.sum() / tokens.sum():.1%}",
        })
    return pd.DataFrame(rows)


def truncation_share(evidence: pd.DataFrame, mode: str) -> float:
    tokens = evidence.loc[evidence["config"] == mode, "tokens"].to_numpy()
    over = np.maximum(0, tokens - config.MODEL_TOKEN_WINDOW)
    return float(over.sum() / tokens.sum())


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def token_length_figure(evidence: pd.DataFrame) -> go.Figure:
    """Where each policy's chunks sit against the model's 256-token wall."""
    figure = go.Figure()
    colors = {"words_60": config.COLOR_MUTED, "words_150": config.COLOR_WARN,
              "section": config.COLOR_ALERT, "tokens_240": config.COLOR_PRIMARY}
    for mode in CONFIG_ORDER:
        tokens = evidence.loc[evidence["config"] == mode, "tokens"].clip(upper=600)
        figure.add_trace(go.Histogram(
            x=tokens, name=CONFIG_LABELS[mode], marker_color=colors[mode],
            opacity=0.72, xbins=dict(start=0, end=600, size=20),
            hovertemplate="%{y} chunks between %{x} tokens<extra>"
                          + CONFIG_LABELS[mode] + "</extra>"))
    figure.add_vline(x=config.MODEL_TOKEN_WINDOW, line_color=config.COLOR_DARK,
                     line_width=2, line_dash="dash")
    figure.add_annotation(x=config.MODEL_TOKEN_WINDOW, y=1.02, yref="paper",
                          text="256 tokens: everything to the right is discarded",
                          showarrow=False, xanchor="left",
                          font=dict(size=12, color=config.COLOR_DARK))
    figure.update_layout(barmode="overlay", legend_title_text="Chunking policy",
                         legend=dict(orientation="h", y=-0.22))
    figure.update_xaxes(title="Tokens in the chunk (clipped at 600 for display)")
    figure.update_yaxes(title="Number of chunks", type="log",
                        title_text="Number of chunks (log scale)")
    return config.layout(
        figure, "Only the token-budget policy keeps every chunk inside the window",
        height=470)


def discarded_tokens_figure(evidence: pd.DataFrame) -> go.Figure:
    """The share of the corpus each policy silently throws away."""
    shares, labels, counts = [], [], []
    for mode in CONFIG_ORDER:
        shares.append(truncation_share(evidence, mode) * 100)
        labels.append(CONFIG_LABELS[mode])
        counts.append(int((evidence["config"] == mode).sum()))
    colors = [config.COLOR_MUTED, config.COLOR_WARN, config.COLOR_ALERT,
              config.COLOR_PRIMARY]
    figure = go.Figure(go.Bar(
        x=labels, y=shares, marker_color=colors,
        text=[f"{s:.1f}%" for s in shares], textposition="outside",
        customdata=counts,
        hovertemplate="%{x}<br>%{y:.1f}% of tokens never encoded"
                      "<br>%{customdata:,} chunks<extra></extra>"))
    figure.update_yaxes(title="Share of all corpus tokens never encoded (%)",
                        range=[0, 75])
    figure.update_xaxes(title="")
    return config.layout(
        figure,
        "Whole-section chunking silently discards two thirds of the corpus",
        height=440)
