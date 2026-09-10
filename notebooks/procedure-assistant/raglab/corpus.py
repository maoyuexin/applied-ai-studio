"""What is in the corpus, where each document came from, and whether we may use it.

The corpus has four deliberate layers - the law, the site procedure, the
equipment manual, and the plain-language guide - because a technician's
question is rarely answered by only one of them. "Can I work under someone
else's lock?" is a site-procedure question that the law constrains and the
OSHA booklet explains.

The licensing rule this module teaches is narrower than "is it public domain".
A US Government work carries no copyright, and can still be restricted from
redistribution by a *distribution statement*. Copyright and distribution
control are independent gates and you have to pass both.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from . import config

# ---------------------------------------------------------------------------
# The manifest: one row per committed document
# ---------------------------------------------------------------------------

ECFR = "https://www.ecfr.gov/api/versioner/v1/full/%s/title-%s.xml?%s"

DOCUMENTS = [
    # -- The law -------------------------------------------------------------
    dict(doc="29 CFR 1910 subpart J", short="29 CFR 1910 subpart J",
         title="General environmental controls (lockout/tagout, confined spaces)",
         layer="regulation", kind="xml", file="cfr/title29_1910_subpartJ.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "29", "part=1910&subpart=J"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="29 CFR 1910 subpart N", short="29 CFR 1910 subpart N",
         title="Materials handling and storage (forklifts, cranes, slings)",
         layer="regulation", kind="xml", file="cfr/title29_1910_subpartN.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "29", "part=1910&subpart=N"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="29 CFR 1910 subpart O", short="29 CFR 1910 subpart O",
         title="Machinery and machine guarding",
         layer="regulation", kind="xml", file="cfr/title29_1910_subpartO.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "29", "part=1910&subpart=O"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="29 CFR 1910 subpart Q", short="29 CFR 1910 subpart Q",
         title="Welding, cutting and brazing",
         layer="regulation", kind="xml", file="cfr/title29_1910_subpartQ.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "29", "part=1910&subpart=Q"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="29 CFR 1910 subpart S", short="29 CFR 1910 subpart S",
         title="Electrical",
         layer="regulation", kind="xml", file="cfr/title29_1910_subpartS.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "29", "part=1910&subpart=S"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="30 CFR part 56", short="30 CFR part 56",
         title="MSHA safety and health standards, surface metal and nonmetal mines",
         layer="regulation", kind="xml", file="cfr/title30_part56.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "30", "part=56"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="30 CFR part 57", short="30 CFR part 57",
         title="MSHA underground mines - OPT-IN, the duplicate-corpus lab only",
         layer="regulation", kind="xml", file="cfr/title30_part57.xml",
         publisher="US Office of the Federal Register (eCFR)",
         url=ECFR % (config.ECFR_DATE_PIN, "30", "part=57"),
         license="US Government edict - public domain (17 USC 105)",
         distribution="Unrestricted", in_base_corpus=False),
    # -- The site procedure --------------------------------------------------
    dict(doc="USBR FIST 1-1", short="USBR FIST 1-1",
         title="Hazardous Energy Control Program",
         layer="site_procedure", kind="pdf", file="pdf/FIST_1-1.pdf",
         publisher="US Bureau of Reclamation",
         url="https://www.usbr.gov/power/data/fist/fist1_1/FIST_1-1.pdf",
         license="US Government work - public domain",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="USBR FIST 2-4", short="USBR FIST 2-4",
         title="Preventive Maintenance",
         layer="site_procedure", kind="pdf", file="pdf/FIST_2-4.pdf",
         publisher="US Bureau of Reclamation",
         url="https://www.usbr.gov/power/data/fist/FIST_2-4_(5-2024).pdf",
         license="US Government work - public domain",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="USBR FIST 2-6", short="USBR FIST 2-6",
         title="Water and Oil Systems Maintenance",
         layer="site_procedure", kind="pdf", file="pdf/FIST_2-6.pdf",
         publisher="US Bureau of Reclamation",
         url="https://www.usbr.gov/power/data/fist/FIST_2-6_(01-2026).pdf",
         license="US Government work - public domain",
         distribution="Unrestricted", in_base_corpus=True),
    # -- The equipment manual ------------------------------------------------
    dict(doc="TM 9-6115-464-12", short="TM 9-6115-464-12",
         title="15 kW Generator Set, Operator and Unit Maintenance",
         layer="equipment", kind="pdf", file="pdf/TM-9-6115-464-12.pdf",
         publisher="US Army (public mirror: liberatedmanuals.com)",
         url="https://liberatedmanuals.com/TM-9-6115-464-12.pdf",
         license="US Government work - public domain",
         distribution="DISTRIBUTION STATEMENT A - verified in the extracted text",
         in_base_corpus=True),
    # -- The plain-language guide -------------------------------------------
    dict(doc="OSHA 3120", short="OSHA 3120",
         title="Control of Hazardous Energy (Lockout/Tagout)",
         layer="plain_language", kind="pdf", file="pdf/osha3120.pdf",
         publisher="US Occupational Safety and Health Administration",
         url="https://www.osha.gov/sites/default/files/publications/osha3120.pdf",
         license="US Government work - public domain",
         distribution="Unrestricted", in_base_corpus=True),
    dict(doc="OSHA 3170", short="OSHA 3170",
         title="Safeguarding Equipment and Protecting Employees from Amputations",
         layer="plain_language", kind="pdf", file="pdf/osha3170.pdf",
         publisher="US Occupational Safety and Health Administration",
         url="https://www.osha.gov/sites/default/files/publications/osha3170.pdf",
         license="US Government work - public domain",
         distribution="Unrestricted", in_base_corpus=True),
]

# Text extracted from each PDF, committed beside the PDF so the licence check
# and a full rebuild both run with no PDF library installed.
PDF_TEXT_NAME = {
    "USBR FIST 1-1": "FIST_1-1.txt",
    "USBR FIST 2-4": "FIST_2-4.txt",
    "USBR FIST 2-6": "FIST_2-6.txt",
    "TM 9-6115-464-12": "TM_9-6115-464-12.txt",
    "OSHA 3120": "OSHA_3120.txt",
    "OSHA 3170": "OSHA_3170.txt",
}

# ---------------------------------------------------------------------------
# What was rejected, and why - the other half of the licensing lesson
# ---------------------------------------------------------------------------

REJECTED = [
    dict(document="Army TM 9-6115-641-24 (generator set)",
         looked_like="A US Government work: no copyright, 684 pages, real text, "
                     "ideal content, and already uploaded to a public site",
         why_rejected="Page 1 carries DISTRIBUTION STATEMENT C - distribution "
                      "limited to government agencies and their contractors - "
                      "plus a destruction notice",
         lesson="Public domain does not mean redistributable. Copyright and "
                "distribution control are independent gates."),
    dict(document="iFixit repair guides",
         looked_like="An open licence: Creative Commons BY-NC-SA",
         why_rejected="NonCommercial alone is a problem for a course, and the "
                      "site terms state that using the data to train a machine "
                      "learning or AI model violates the terms of use",
         lesson="An open-looking licence can be explicitly closed to this "
                "particular use. Read the terms, not the badge."),
    dict(document="OEM service manuals (Caterpillar, Deere, Siemens, Fanuc, "
                  "Rockwell, ABB)",
         looked_like="Exactly the content a real plant assistant would need",
         why_rejected="Dealer-portal only; no public licence exists at any price "
                      "we can accept for a classroom",
         lesson="The most useful corpus is often the one you are not allowed to "
                "have. Say so, and build on what you may use."),
]

# The statement to look for, and the two ways this one document writes it.
STATEMENT_A = "approved for public release; distribution is unlimited"
NAIVE_PATTERN = "Approved for public release"


# ---------------------------------------------------------------------------
# Loading and verifying what is committed
# ---------------------------------------------------------------------------

def md5(path: Path) -> str:
    digest = hashlib.md5()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> pd.DataFrame:
    """The committed provenance table: one row per document."""
    return pd.read_csv(config.PROVENANCE_CSV)


def raw_text(document: str) -> str:
    """The extracted text of one PDF document, as the pipeline consumed it."""
    return (config.RAW_TEXT_DIR / PDF_TEXT_NAME[document]).read_text(
        encoding="utf-8", errors="replace")


def verify_checksums() -> pd.DataFrame:
    """Recompute the MD5 of every committed file against the manifest.

    Provenance has two halves and only one of them is checkable here. The
    *source* checksum was recorded when the file was downloaded and can only be
    re-verified by downloading again; the *committed* checksum is recomputed
    from the bytes in this repository every time this cell runs.
    """
    manifest = load_manifest()
    rows = []
    for record in manifest.to_dict("records"):
        path = config.RAW_DIR / record["file"]
        actual = md5(path)
        rows.append({
            "Document": record["doc"],
            "Committed file": record["file"],
            "Bytes": f"{path.stat().st_size:,}",
            "MD5 recorded": record["md5"][:12],
            "MD5 recomputed": actual[:12],
            "Match": "yes" if actual == record["md5"] else "NO",
        })
    return pd.DataFrame(rows)


def summary(manifest: pd.DataFrame) -> pd.DataFrame:
    """Documents, words and megabytes per layer."""
    rows = []
    for layer, (name, _) in config.LAYERS.items():
        part = manifest[manifest["layer"] == layer]
        if part.empty:
            continue
        rows.append({
            "Layer": name,
            "Documents": len(part),
            "Words": int(part["words"].sum()),
            "Megabytes": round(part["bytes"].sum() / 1e6, 2),
        })
    total = pd.DataFrame([{
        "Layer": "All layers",
        "Documents": len(manifest),
        "Words": int(manifest["words"].sum()),
        "Megabytes": round(manifest["bytes"].sum() / 1e6, 2),
    }])
    return pd.concat([pd.DataFrame(rows), total], ignore_index=True)


def layer_table() -> pd.DataFrame:
    return pd.DataFrame([
        {"Layer": name, "What it is": description,
         "The question it answers": q}
        for (name, description), q in zip(
            config.LAYERS.values(),
            ["What am I legally required to do?",
             "What does this employer's own written program say?",
             "What does this machine need, in numbers?",
             "What does the rule actually mean, in English?"])
    ])


# ---------------------------------------------------------------------------
# The licence gate
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    """Collapse whitespace and case before matching a licence statement."""
    return re.sub(r"\s+", " ", text).lower()


def distribution_statement_scan(text: str) -> dict:
    """Look for DISTRIBUTION STATEMENT A two ways: naively, and properly.

    The naive scan matches the raw string. The proper scan lowercases the text
    and collapses runs of whitespace first, because a PDF cover page renders
    the same sentence with doubled spaces and a capitalised "Is". One document
    can therefore appear to carry the statement once, or twice, depending only
    on how the matcher treats formatting.
    """
    naive = [m.start() for m in re.finditer(re.escape(NAIVE_PATTERN), text)]
    flat = normalise(text)
    proper = [m.start() for m in re.finditer(re.escape(normalise(STATEMENT_A)), flat)]
    restricted = {
        letter: bool(re.search(r"distribution\s+statement\s+" + letter + r"\b", flat))
        for letter in "BCDEF"
    }
    destruction = bool(re.search(r"destroy(?:ing)? (?:this|the) (?:report|document|manual)"
                                 r"|destruction notice", flat))
    return {
        "naive_matches": len(naive),
        "normalised_matches": len(proper),
        "statement_a_present": len(proper) > 0,
        "restrictive_statement_present": any(restricted.values()),
        "restrictive_letters": [k for k, v in restricted.items() if v],
        "destruction_notice": destruction,
        "verdict": ("ACCEPT - Statement A verified in the document's own text"
                    if len(proper) > 0 and not any(restricted.values())
                    else "REJECT"),
    }


def statement_excerpts(text: str, width: int = 96) -> pd.DataFrame:
    """Every rendering of the distribution statement, as it appears in the text."""
    flat_positions = [m.start() for m in
                      re.finditer(r"DISTRIBUTION\s+STATEMENT", text, re.I)]
    rows = []
    for position in flat_positions[:6]:
        excerpt = re.sub(r"\s+", " ", text[position:position + width]).strip()
        rows.append({
            "Character offset": f"{position:,}",
            "As it appears in the extracted text": excerpt,
            "Matches the naive pattern": "yes" if NAIVE_PATTERN in
                                         text[position:position + width] else "no",
        })
    return pd.DataFrame(rows)


def rejected_table() -> pd.DataFrame:
    return pd.DataFrame(REJECTED).rename(columns={
        "document": "Document", "looked_like": "What it looked like",
        "why_rejected": "Why it was rejected", "lesson": "The rule it teaches"})


# ---------------------------------------------------------------------------
# Fetching (never runs at setup or in class)
# ---------------------------------------------------------------------------

def fetch_document(record: dict, destination: Path) -> Path:
    """Download one document. Called only by scripts/build_corpus.py --fetch."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ["curl", "--compressed", "-sSL", "--fail",
               "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
               "-o", str(destination), record["url"]]
    subprocess.run(command, check=True)
    return destination


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def corpus_composition(manifest: pd.DataFrame) -> go.Figure:
    """Words per document, coloured by layer, base corpus only."""
    base = manifest[manifest["in_base_corpus"]].sort_values("words", ascending=True)
    figure = go.Figure()
    for layer, (name, _) in config.LAYERS.items():
        part = base[base["layer"] == layer]
        if part.empty:
            continue
        figure.add_bar(
            y=part["doc"], x=part["words"], name=name, orientation="h",
            marker_color=config.LAYER_COLORS[layer],
            text=[f"{w:,}" for w in part["words"]], textposition="outside",
            hovertemplate="%{y}<br>%{x:,} words<extra>" + name + "</extra>",
        )
    figure.update_xaxes(title="Words in the document", rangemode="tozero")
    figure.update_yaxes(title="")
    figure.update_layout(legend_title_text="Layer", barmode="stack",
                         legend=dict(orientation="h", y=-0.18))
    figure.update_xaxes(range=[0, base["words"].max() * 1.22])
    return config.layout(
        figure,
        "One equipment manual carries a quarter of the corpus's words",
        height=520)
