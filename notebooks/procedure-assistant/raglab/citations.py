"""Turning a regulation into passages that carry a citation you can trust.

Two halves live here.

**The builder** (needs ``lxml``; runs only inside ``scripts/build_corpus.py``)
walks the eCFR XML and gives every paragraph a full hierarchical citation such
as ``29 CFR 1910.147(c)(4)(ii)(B)``. It also records, beside each one, the
citation a *naive* chunker would have produced - the paragraph's own leading
label pasted onto the section number - so the notebook can measure the
difference instead of asserting it.

**The auditors** (pure pandas; run in the notebook) score both citation sets
against two different ground truths:

1. a *structural* check - does every ancestor of this citation exist in this
   section? The chunker validates its own output here, which is exactly why
   this check can pass while being wrong;
2. an *independent* check - the regulation cites its own paragraphs 194 times
   ("paragraph (c)(4)(ii) of this section"). Those paths were written by OSHA,
   not by our parser. A citation set that cannot resolve them is wrong no
   matter what the structural check says.

Four real bugs the stateful stack fixes, all visible in the source text:

1. parent labels live in *earlier* paragraphs - ``(a)(1)`` in paragraph 12,
   a bare ``(ii)`` in paragraph 47;
2. several labels run in on one paragraph -
   ``(h) <I>PSDI</I>-(1) <I>General.</I> (i) The requirements ...``;
3. ``(i)`` is both the ninth letter and the first lowercase roman numeral;
4. appendices, notes, tables and definition lists restart the numbering
   *inside* a section.
"""

from __future__ import annotations

import collections
import html
import json
import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# The label stack
# ---------------------------------------------------------------------------

ROMAN = {r: n for n, r in enumerate(
    "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx "
    "xxi xxii xxiii xxiv xxv xxvi xxvii xxviii xxix xxx".split(), 1)}

# The CFR's own nesting order: (a) (1) (i) (A) (1) (i)
LEVELS = ["alpha_lower", "num", "roman_lower", "alpha_upper", "num2", "roman_lower2"]


def classify(token: str) -> list[tuple[str, int]]:
    """Every level a bare label token could belong to, with its ordinal.

    ``"i"`` is genuinely ambiguous - the ninth lowercase letter and the first
    lowercase roman numeral - so it comes back as two candidates and something
    else has to choose.
    """
    out: list[tuple[str, int]] = []
    if re.fullmatch(r"\d{1,3}", token):
        out += [("num", int(token)), ("num2", int(token))]
    if re.fullmatch(r"[a-z]{1,6}", token):
        if token in ROMAN:
            out += [("roman_lower", ROMAN[token]), ("roman_lower2", ROMAN[token])]
        if len(token) == 1:
            out.append(("alpha_lower", ord(token) - 96))
        elif len(set(token)) == 1 and len(token) <= 2:
            out.append(("alpha_lower", 26 * (len(token) - 1) + ord(token[0]) - 96))
    if re.fullmatch(r"[A-Z]{1,2}", token):
        if len(token) == 1:
            out.append(("alpha_upper", ord(token) - 64))
        elif len(set(token)) == 1:
            out.append(("alpha_upper", 26 * (len(token) - 1) + ord(token[0]) - 64))
    return out


class LabelStack:
    """The open ancestor path, carried across paragraphs.

    A label is resolved as either the successor of a level that is already open
    (``(2)`` after ``(1)``) or the first item of the next level down (``(i)``
    after ``(1)``). The stack is what makes ``(ii)``, arriving alone thirty
    paragraphs later, still know it belongs under ``(a)(1)``.
    """

    def __init__(self) -> None:
        self.stack: list[dict] = []
        self.def_base: int | None = None

    def reset(self) -> None:
        self.stack = []
        self.def_base = None

    def path(self) -> str:
        return "".join("(%s)" % level["tok"] for level in self.stack)

    def new_definition(self) -> None:
        """An unlabeled italic-term paragraph starts a new definition entry."""
        if self.def_base is None:
            self.def_base = len(self.stack)
        else:
            self.stack = self.stack[:self.def_base]

    def feed(self, token: str, hint: str | None = None) -> str:
        candidates = classify(token)
        if hint:
            filtered = [c for c in candidates if c[0] == hint or
                        (hint == "roman_lower" and c[0] == "roman_lower2")]
            if filtered:
                candidates = filtered
        if not candidates:
            return self.path()
        by_type = {t: o for t, o in candidates}

        # 1) successor of an open level, deepest first
        for i in range(len(self.stack) - 1, -1, -1):
            level = self.stack[i]
            if by_type.get(level["type"]) == level["ord"] + 1:
                self.stack = self.stack[:i] + [
                    {"tok": token, "type": level["type"], "ord": level["ord"] + 1}]
                if self.def_base is not None and len(self.stack) <= self.def_base:
                    self.def_base = None
                return self.path()

        # 2) first item of the next deeper level
        depth = len(self.stack)
        nxt = LEVELS[depth] if depth < len(LEVELS) else LEVELS[-1]
        if by_type.get(nxt) == 1:
            self.stack.append({"tok": token, "type": nxt, "ord": 1})
            return self.path()

        # 3) any first-item reading at or below the current depth
        for t, o in candidates:
            if o == 1 and t in LEVELS and LEVELS.index(t) >= depth:
                self.stack = self.stack[:LEVELS.index(t)] + [
                    {"tok": token, "type": t, "ord": 1}]
                return self.path()

        # 4) restart a known level (a gap, or a [Reserved] paragraph skipped)
        for t, o in candidates:
            if t in LEVELS:
                i = LEVELS.index(t)
                self.stack = self.stack[:i] + [{"tok": token, "type": t, "ord": o}]
                if self.def_base is not None and len(self.stack) <= self.def_base:
                    self.def_base = None
                return self.path()
        return self.path()


# ---------------------------------------------------------------------------
# Reading one XML paragraph
# ---------------------------------------------------------------------------

I_OPEN, I_CLOSE = "\x01", "\x02"

LBL = re.compile(r"^\(([A-Za-z0-9]{1,6})\)\s*")
HEADING = re.compile(r"^\x01([^\x02]{0,110})\x02\s*")
DASH = re.compile(r"^[—–]\s*")
PLAIN_HEAD = re.compile(r"^[A-Z][^.()\x01\x02]{2,55}\.\s+")
DEF_TERM = re.compile(r"^\x01[^\x02]{1,80}\x02")
SUPPRESS = {"NOTE", "EXTRACT", "TABLE", "CITA", "AUTH", "SOURCE", "EDNOTE",
            "THEAD", "TBODY", "TR", "TD", "TH", "CAPTION", "FTNT", "SECAUTH"}

# '(i)' is the ninth letter and the first lowercase roman numeral. Force the
# roman reading only when the NEXT label proves it: '(ii)' continues the roman
# run and '(A)' is the roman level's child. Anything more aggressive makes it
# worse - forcing a letter reading otherwise drops the independent
# cross-reference score from 91.8% to 68.0%.
AMBIGUOUS_NEXT = {"i": ("ii", "A"), "v": ("vi",), "x": ("xi",)}


def marked_text(element) -> str:
    """Flatten an element to text, wrapping italic spans in sentinel characters."""
    parts: list[str] = []

    def walk(node, italic):
        inside = italic or node.tag in ("I", "E")
        if node.tag in ("I", "E") and not italic:
            parts.append(I_OPEN)
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child, inside)
            if child.tail:
                parts.append(child.tail)
        if node.tag in ("I", "E") and not italic:
            parts.append(I_CLOSE)

    walk(element, False)
    return re.sub(r"[ \t\r\n]+", " ", "".join(parts)).strip()


def leading_labels(text: str) -> list[str]:
    """Read a run-in chain of labels off the front of one paragraph.

    ``(h) <I>PSDI</I>-(1) <I>General.</I> (i) ...`` is a single ``<P>`` that
    opens three levels at once. The chain must stop at a *defined term*,
    though: ``(28) <I>Conductors, runway</I> (main) are the electrical
    conductors ...`` would otherwise contribute the bogus label ``(main)``.
    """
    labels: list[str] = []
    rest = text
    while True:
        match = LBL.match(rest)
        if not match:
            break
        token = match.group(1)
        if not classify(token):
            break
        labels.append(token)
        rest = rest[match.end():]
        heading = HEADING.match(rest)
        if heading:
            after = rest[heading.end():]
            dash = DASH.match(after)
            if dash:
                rest = after[dash.end():]
            elif heading.group(1).rstrip().endswith("."):
                rest = after
            else:
                break
        else:
            dash = DASH.match(rest)
            if dash:
                rest = rest[dash.end():]
            else:
                # some sections leave the run-in heading un-italicised:
                # "(l) Operator training. (1) <I>Safe operation.</I> (i) ..."
                plain = PLAIN_HEAD.match(rest)
                if plain and LBL.match(rest[plain.end():]):
                    rest = rest[plain.end():]
        if not LBL.match(rest):
            break
    return labels


# ---------------------------------------------------------------------------
# The builder (lxml; build-time only)
# ---------------------------------------------------------------------------

def _parse_xml(path: Path):
    """Parse the eCFR XML with whatever tree library is installed.

    ``lxml`` is preferred when present; the standard library's
    ``ElementTree`` produces the same element tree for these files and keeps
    the corpus build free of a compiled dependency. Either way this is
    build-time only - the notebook reads the committed parquet.
    """
    try:
        from lxml import etree  # noqa: WPS433
    except ImportError:
        import xml.etree.ElementTree as etree  # noqa: WPS433
    return etree.parse(str(path))


def parse_cfr_xml(path: Path, part_label: str, title: str,
                  visited: set | None = None,
                  disambiguate: bool = True) -> list[dict]:
    """eCFR XML -> one record per paragraph, with both citation styles.

    ``disambiguate=False`` switches off the one-token lookahead that decides
    whether a bare ``(i)`` is the ninth letter or the first roman numeral. It
    exists so the notebook can run the parser both ways on the same file and
    measure the damage, instead of describing a bug it fixed earlier.
    """
    visited = visited if visited is not None else set()
    tree = _parse_xml(path)
    records: list[dict] = []

    for div8 in tree.iter("DIV8"):
        meta = div8.get("hierarchy_metadata") or ""
        try:
            citation = json.loads(html.unescape(meta)).get("citation")
        except Exception:
            citation = None
        citation = citation or "%s CFR %s" % (title, div8.get("N"))
        head_el = div8.find("HEAD")
        head = (re.sub(r"\s+", " ", "".join(head_el.itertext())).strip()
                if head_el is not None else "")

        # Pass 1: collect the bare token sequence so pass 2 can disambiguate
        # (i)/(v)/(x) with one token of lookahead.
        pre: list[str] = []

        def collect(node, suppressed):
            for el in node:
                if el.tag in SUPPRESS:
                    collect(el, True)
                elif el.tag == "P" and not suppressed:
                    pre.extend(leading_labels(marked_text(el)))
                elif el.tag not in ("P", "FP"):
                    collect(el, suppressed)

        collect(div8, False)
        hints = {}
        for n, token in enumerate(pre if disambiguate else []):
            if token in AMBIGUOUS_NEXT:
                following = pre[n + 1] if n + 1 < len(pre) else None
                if following in AMBIGUOUS_NEXT[token]:
                    hints[n] = "roman_lower"

        stack = LabelStack()
        appendix = None
        seq = 0
        consumed = 0

        def walk(node, suppressed):
            nonlocal appendix, seq, consumed
            for el in node:
                tag = el.tag
                if tag in ("HD1", "HD2", "HD3", "HED", "HEAD"):
                    text = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                    match = re.match(r"Appendix\s+([A-Z])\b", text)
                    if match:
                        appendix = match.group(1)
                        stack.reset()
                    elif re.match(r"Appendix(es)?\s+to", text, re.I):
                        appendix = appendix or "?"
                        stack.reset()
                    continue
                if tag in SUPPRESS:
                    walk(el, True)
                    continue
                if tag in ("P", "FP"):
                    marked = marked_text(el)
                    plain = marked.replace(I_OPEN, "").replace(I_CLOSE, "")
                    if not plain:
                        continue
                    seq += 1
                    naive_token = None
                    if not suppressed and tag == "P":
                        labels = leading_labels(marked)
                        if labels:
                            for label in labels:
                                path = stack.feed(label, hints.get(consumed))
                                consumed += 1
                                visited.add((citation, appendix, path))
                            naive_token = labels[-1]
                        elif DEF_TERM.match(marked):
                            stack.new_definition()
                    path = stack.path()
                    naive_path = "(%s)" % naive_token if naive_token else path
                    if appendix:
                        base = "%s App. %s" % (citation, appendix)
                    else:
                        base = citation
                    records.append(dict(
                        doc_id="CFR-T%s-%s" % (title, part_label),
                        layer="regulation",
                        source=("29 CFR 1910 subpart %s" % part_label if title == "29"
                                else "30 CFR part %s" % part_label),
                        section=citation,
                        section_head=head,
                        appendix=appendix or "",
                        para_path=path,
                        naive_path=naive_path,
                        citation=base + path,
                        naive_citation=base + naive_path,
                        normative=(not suppressed and not appendix),
                        seq=seq,
                        page=-1,
                        text=plain,
                    ))
                    continue
                walk(el, suppressed)

        walk(div8, False)
    return records


# ---------------------------------------------------------------------------
# The auditors (pandas; notebook-time)
# ---------------------------------------------------------------------------

def hierarchical(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """The paragraphs whose citations have a hierarchy that can be got wrong.

    29 CFR 1910 nests six levels deep - ``(a)(1)(ii)(B)`` - so a label can be
    hung off the wrong ancestor. MSHA's 30 CFR 56 numbers its rules flat, and
    the PDF layers cite by page, so neither can fail this way. Scoring them
    would only dilute the measurement with rows that cannot lose.
    """
    return paragraphs[paragraphs["source"].str.startswith(
        config_scope())].reset_index(drop=True)


def config_scope() -> str:
    from . import config
    return config.CITATION_AUDIT_SCOPE


def load_open_paths(path: Path | None = None) -> pd.DataFrame:
    """The ancestor paths the label stack opened while walking the regulation.

    A run-in paragraph such as ``(h) PSDI-(1) General. (i) The requirements...``
    opens three levels but emits only one paragraph, at ``(h)(1)(i)``. The
    ancestors ``(h)`` and ``(h)(1)`` are real paragraphs of the rule that never
    appear as a row of their own, so a structural check that only knows about
    emitted rows would report them as invalid. The builder records every path
    it opened; this is that record.
    """
    from . import config
    return pd.read_parquet(path or config.OPEN_PATHS_PARQUET)


def _valid_paths(paragraphs: pd.DataFrame,
                 open_paths: pd.DataFrame | None = None) -> dict:
    """Every paragraph path that genuinely exists, keyed by (section, appendix)."""
    valid: dict = collections.defaultdict(set)
    for section, appendix, path in zip(paragraphs["section"],
                                       paragraphs["appendix"],
                                       paragraphs["para_path"]):
        valid[(section, appendix)].add(path)
    if open_paths is not None:
        for section, appendix, path in zip(open_paths["section"],
                                           open_paths["appendix"],
                                           open_paths["path"]):
            valid[(section, appendix)].add(path)
    return valid


def _naive_paths(paragraphs: pd.DataFrame) -> dict:
    naive: dict = collections.defaultdict(set)
    for section, appendix, path in zip(paragraphs["section"],
                                       paragraphs["appendix"],
                                       paragraphs["naive_path"]):
        naive[(section, appendix)].add(path)
    return naive


def naive_versus_stateful(paragraphs: pd.DataFrame,
                          open_paths: pd.DataFrame | None = None) -> pd.DataFrame:
    """Score the naive chunker's citations against the paths that exist.

    A naive chunker pastes the paragraph's *own* leading label onto the section
    number: ``29 CFR 1910.147(B)`` for a paragraph that is really
    ``29 CFR 1910.147(a)(1)(ii)(B)``. The result is confident, plausible, and
    points at a paragraph nobody can look up.
    """
    labelled = paragraphs[paragraphs["para_path"].str.len() > 0]
    valid = _valid_paths(paragraphs, open_paths)
    exact = int((labelled["naive_citation"] == labelled["citation"]).sum())
    nonexistent = sum(
        1 for section, appendix, path in zip(labelled["section"],
                                             labelled["appendix"],
                                             labelled["naive_path"])
        if path not in valid[(section, appendix)]
    )
    total = len(labelled)
    return pd.DataFrame([
        {"Measure": "Labelled paragraphs scored", "Naive chunker": total,
         "Share": ""},
        {"Measure": "Citation exactly correct", "Naive chunker": exact,
         "Share": f"{exact / total:.1%}"},
        {"Measure": "Citation wrong", "Naive chunker": total - exact,
         "Share": f"{(total - exact) / total:.1%}"},
        {"Measure": "Citation names a paragraph that does not exist",
         "Naive chunker": nonexistent, "Share": f"{nonexistent / total:.1%}"},
    ])


def structural_check(paragraphs: pd.DataFrame,
                     open_paths: pd.DataFrame | None = None) -> dict:
    """Does every ancestor of each stateful citation exist in that section?

    This is the self-check, and it is circular by construction: the chunker is
    grading its own output against a list of paths the chunker itself produced.
    It reports 0 invalid citations - and it stayed at 0 while the parser was
    emitting ``1910.217(i)(iii)`` for ``1910.217(h)(1)(iii)``.
    """
    labelled = paragraphs[paragraphs["para_path"].str.len() > 0]
    valid = _valid_paths(paragraphs, open_paths)

    def ancestors(path: str) -> list[str]:
        tokens = re.findall(r"\(([^)]*)\)", path)
        return ["".join("(%s)" % t for t in tokens[:i]) for i in range(1, len(tokens))]

    invalid = [
        cit for cit, section, appendix, path in zip(
            labelled["citation"], labelled["section"],
            labelled["appendix"], labelled["para_path"])
        if any(a not in valid[(section, appendix)] for a in ancestors(path))
    ]
    return {
        "labelled_paragraphs": len(labelled),
        "structurally_invalid": len(invalid),
        "examples": invalid[:5],
        "note": "A self-check. It grades the chunker against the chunker.",
    }


XREF = re.compile(
    r"paragraphs?\s+(\((?:[A-Za-z0-9]{1,4})\)(?:\([A-Za-z0-9]{1,4}\))*)\s+of this section",
    re.I)


def cross_reference_check(paragraphs: pd.DataFrame,
                          open_paths: pd.DataFrame | None = None) -> dict:
    """The independent ground truth: the regulation cites its own paragraphs.

    OSHA wrote every ``"paragraph (c)(4)(ii) of this section"`` in the text.
    Those paths owe nothing to our parser, so a citation set that cannot
    resolve them is wrong however clean its self-check looks.
    """
    valid = _valid_paths(paragraphs, open_paths)
    naive = _naive_paths(paragraphs)
    seen: set = set()
    unresolved: list[tuple[str, str]] = []
    stateful_hits = 0
    for section, appendix, text in zip(paragraphs["section"],
                                       paragraphs["appendix"],
                                       paragraphs["text"]):
        key = (section, appendix)
        for match in XREF.finditer(text):
            path = match.group(1)
            if (key, path) in seen:
                continue
            seen.add((key, path))
            if path in valid[key]:
                stateful_hits += 1
            else:
                unresolved.append((section, path))
    naive_hits = sum(1 for (key, path) in seen if path in naive[key])
    total = len(seen)
    return {
        "cross_references": total,
        "stateful_resolved": stateful_hits,
        "stateful_rate": round(stateful_hits / total, 3),
        "naive_resolved": naive_hits,
        "naive_rate": round(naive_hits / total, 3),
        "unresolved_examples": unresolved[:6],
    }


def verify_audit_sample(paragraphs: pd.DataFrame,
                        path: Path | None = None) -> dict:
    """Re-derive the 20 hand-audited citations from the current parse.

    The 20 rows in ``citation_sample20.json`` were read by a person against the
    published regulation: for each one, someone opened 29 CFR and confirmed the
    paragraph really sits where the citation says it sits. That makes them a
    fixed, external answer key. Re-deriving them here proves the parser still
    produces the citations that were checked by hand, rather than 20 rows that
    happen to agree with whatever it does today.
    """
    sample = audit_sample(path)
    key = ["section", "appendix", "seq"]
    merged = sample.merge(
        paragraphs[key + ["citation", "naive_citation", "text"]],
        on=key, how="left", suffixes=("_audited", "_rebuilt"))
    matched = int(merged["citation_rebuilt"].notna().sum())
    identical = int((merged["citation_audited"] == merged["citation_rebuilt"]).sum())
    text_identical = int((merged["text_audited"].str.strip()
                          == merged["text_rebuilt"].str.strip()).sum())
    return {
        "hand_audited_paragraphs": len(sample),
        "found_in_the_current_parse": matched,
        "citation_identical": f"{identical}/{len(sample)}",
        "passage_text_identical": f"{text_identical}/{len(sample)}",
        "naive_citation_would_have_been_wrong": int(
            (merged["naive_citation_audited"] != merged["citation_audited"]).sum()),
        "verdict": ("PASS - every hand-checked citation is reproduced exactly"
                    if identical == len(sample) else "FAIL"),
    }


def audit_table(paragraphs: pd.DataFrame, rows: int = 6) -> pd.DataFrame:
    """A readable slice of the hand-audited sample: stateful vs naive."""
    sample = audit_sample().head(rows)
    return pd.DataFrame({
        "Section": sample["section"],
        "Citation (stateful label stack)": sample["citation"],
        "Citation a naive chunker emits": sample["naive_citation"],
        "The passage": sample["text"].str.slice(0, 96) + "...",
    })


def audit_sample(path: Path | None = None) -> pd.DataFrame:
    """The 20 hand-audited citations committed with the lab."""
    from . import config
    payload = json.loads(Path(path or config.CITATION_AUDIT_JSON).read_text())
    rows = payload if isinstance(payload, list) else payload.get("sample", [])
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def citation_figure(naive: pd.DataFrame, xref: dict, structural: dict) -> "go.Figure":
    """Three graders of the same citations, and only one of them is independent.

    Left pair: the two chunkers scored against the paragraph paths that exist.
    Right pair: the two chunkers scored against the regulation's own internal
    cross-references, which OSHA wrote and our parser did not. The self-check
    sits on top as an annotation, at a clean 100%, because it is the one grader
    that cannot fail.
    """
    import plotly.graph_objects as go

    from . import config

    share = dict(zip(naive["Measure"], naive["Share"]))
    naive_correct = 1 - float(share["Citation wrong"].rstrip("%")) / 100
    labels = ["Citation exactly correct<br>(scored against the paths<br>that exist)",
              "Resolves the regulation's own<br>cross-references<br>(independent ground truth)"]
    stateful = [1.0, xref["stateful_rate"]]
    naive_values = [naive_correct, xref["naive_rate"]]

    figure = go.Figure()
    figure.add_bar(x=labels, y=stateful, name="Stateful label stack (deployed)",
                   marker_color=config.COLOR_PRIMARY,
                   text=[f"{v:.1%}" for v in stateful], textposition="outside",
                   hovertemplate="%{x}<br>%{y:.1%}<extra>stateful</extra>")
    figure.add_bar(x=labels, y=naive_values, name="Naive chunker (the paragraph's own label)",
                   marker_color=config.COLOR_ALERT,
                   text=[f"{v:.1%}" for v in naive_values], textposition="outside",
                   hovertemplate="%{x}<br>%{y:.1%}<extra>naive</extra>")
    figure.add_annotation(
        x=0.5, xref="paper", y=1.14, yref="paper", showarrow=False,
        text=(f"The structural self-check reports {structural['structurally_invalid']} "
              f"invalid citations out of {structural['labelled_paragraphs']:,}. "
              "It graded the chunker against the chunker."),
        font=dict(size=12, color=config.COLOR_DARK))
    figure.update_yaxes(title="Share of citations that are correct",
                        tickformat=".0%", range=[0, 1.12])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=-0.22))
    return config.layout(
        figure,
        "Both graders agree the naive chunker is wrong; only the right-hand one could have said so",
        height=480)


# ---------------------------------------------------------------------------
# The ambiguity that a self-check cannot see
# ---------------------------------------------------------------------------

AMBIGUITY_SECTION = "29 CFR 1910.217"
AMBIGUITY_MARKER = "(iii) Full revolution"
AMBIGUITY_SUBPART = ("cfr/title29_1910_subpartO.xml", "O", "29")


def label_stack_readings() -> pd.DataFrame:
    """Feed the same five labels to the stack with and without the lookahead.

    ``(i)`` is the ninth lowercase letter and the first lowercase roman
    numeral. After ``(h)`` and ``(1)``, the letter reading is a perfectly legal
    successor of ``(h)``, so the stack takes it and the whole branch shifts up
    a level. One token of lookahead - the next label is ``(ii)``, which only a
    roman run produces - settles it.
    """
    tokens = ["h", "1", "i", "ii", "A"]
    plain, hinted = LabelStack(), LabelStack()
    rows = []
    for position, token in enumerate(tokens):
        without = plain.feed(token)
        with_hint = hinted.feed(token, "roman_lower" if position == 2 else None)
        rows.append({
            "Label read": f"({token})",
            "Without lookahead": without,
            "With one token of lookahead": with_hint,
            "Same?": "yes" if without == with_hint else "NO",
        })
    return pd.DataFrame(rows)


def ambiguity_experiment() -> pd.DataFrame:
    """Parse one real subpart both ways and let three graders score each parse.

    This is the same file, the same code path, and one boolean. The structural
    self-check cannot separate the two parses, because each one defines the set
    of paths it is then graded against. The regulation's own cross-references
    can, because OSHA wrote them.
    """
    relative, label, title = AMBIGUITY_SUBPART
    rows = []
    for disambiguate in (False, True):
        opened: set = set()
        records = parse_cfr_xml(config_path(relative), label, title,
                                visited=opened, disambiguate=disambiguate)
        frame = pd.DataFrame(records)
        open_paths = pd.DataFrame(
            [{"section": section, "appendix": appendix or "", "path": path}
             for section, appendix, path in sorted(opened)])
        structural = structural_check(frame, open_paths)
        xref = cross_reference_check(frame, open_paths)
        target = frame[(frame["section"] == AMBIGUITY_SECTION)
                       & frame["text"].str.startswith(AMBIGUITY_MARKER)]
        rows.append({
            "Parser": ("With the lookahead (deployed)" if disambiguate
                       else "Without the lookahead (the bug)"),
            "Citation it gives one known paragraph":
                target["citation"].iloc[0] if len(target) else "not found",
            "Structural self-check: invalid citations":
                f"{structural['structurally_invalid']} of "
                f"{structural['labelled_paragraphs']:,}",
            "Independent check: cross-references resolved":
                f"{xref['stateful_rate']:.1%} of {xref['cross_references']}",
        })
    return pd.DataFrame(rows)


def config_path(relative: str) -> Path:
    from . import config
    return config.RAW_DIR / relative
