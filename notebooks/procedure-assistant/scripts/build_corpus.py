"""Build every derived corpus table this lab reads, from the committed raw files.

Two modes, and the difference matters for a classroom.

``--fetch`` downloads the 13 source documents. It is run **once**, by hand, by
whoever prepares the lab, and its output is committed. It is not wired into
``npm run setup:procedures`` and it is never run in class. The eCFR API is
date-pinned to 2025-08-01 so the text cannot drift underneath the evaluation
set, and every call goes out with ``curl --compressed`` - the API answers HTTP
406 to a client that does not accept compression - behind a browser user agent,
because the developer portal serves a CAPTCHA wall to repeat callers. Thirty
students hitting it live would all fail, and they would all fail differently.

The default mode rebuilds the derived tables from what is already on disk:

- ``data/corpus_raw/provenance.csv``   one row per document: publisher, URL,
  licence, distribution status, retrieval date, checksum, size, words
- ``data/corpus_raw/LICENSES.md``      the same facts in prose, plus what was
  rejected and why
- ``data/corpus_paragraphs.parquet``   one row per paragraph or page block,
  carrying both the stateful citation and the naive one, so the notebook can
  measure the difference rather than assert it
- ``data/corpus_chunks.parquet``       the deployed 240-token chunk table,
  30 CFR 57 included but flagged ``in_base_corpus = False``
- ``data/chunk_size_evidence.parquet`` the same corpus chunked four ways, so
  the silent-truncation cell has something real to measure

Neither mode needs ``lxml``, ``pypdf`` or ``pdfminer``: the PDF text layers were
extracted once and committed beside the PDFs, page-separated by form feeds.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from raglab import chunking, citations, config, corpus  # noqa: E402


# ---------------------------------------------------------------------------
# Fetching - once, by hand, never at setup
# ---------------------------------------------------------------------------

def fetch_all() -> None:
    """Download all 13 documents into ``data/corpus_raw``. Run once."""
    print("Fetching the corpus. This is a one-time, by-hand step.")
    print(config.ECFR_FETCH_NOTE)
    for record in corpus.DOCUMENTS:
        destination = config.RAW_DIR / record["file"]
        print(f"  {record['doc']:<24} -> {record['file']}")
        corpus.fetch_document(record, destination)
        time.sleep(2)  # be a polite client; the portal rate-limits hard
    print(
        "\nDownloaded. Now extract the PDF text layers once into\n"
        "data/corpus_raw/text/ with pdfminer.six -- `extract_text(path)` emits the\n"
        "page separators (form feed) this build reads -- then re-run with no flags.\n"
        "pdfminer.six is needed for that one step only; nothing else in the lab,\n"
        "including the notebook, imports a PDF library."
    )


# ---------------------------------------------------------------------------
# The paragraph table
# ---------------------------------------------------------------------------

CFR_FILES = [
    ("cfr/title29_1910_subpartJ.xml", "J", "29"),
    ("cfr/title29_1910_subpartN.xml", "N", "29"),
    ("cfr/title29_1910_subpartO.xml", "O", "29"),
    ("cfr/title29_1910_subpartQ.xml", "Q", "29"),
    ("cfr/title29_1910_subpartS.xml", "S", "29"),
    ("cfr/title30_part56.xml", "56", "30"),
    ("cfr/title30_part57.xml", "57", "30"),
]

BASE_CORPUS = {record["doc"] for record in corpus.DOCUMENTS if record["in_base_corpus"]}


def cfr_paragraphs(opened: set) -> list[dict]:
    """Every CFR paragraph, with the stateful citation and the naive one beside it.

    ``opened`` collects every ancestor path the label stack opened, including
    the ones that never become a paragraph row of their own.
    """
    records: list[dict] = []
    for relative, label, title in CFR_FILES:
        parsed = citations.parse_cfr_xml(config.RAW_DIR / relative, label, title,
                                         visited=opened)
        sections = len({row["section"] for row in parsed})
        words = sum(len(row["text"].split()) for row in parsed)
        print(f"  {relative:<34} {len(parsed):5,} paragraphs  "
              f"{sections:4} sections  {words:7,} words")
        records.extend(parsed)
    for row in records:
        row["source_title"] = row["section_head"]
        row["in_base_corpus"] = row["source"] in BASE_CORPUS
    return records


PDF_LAYOUT = {record["doc"]: record for record in corpus.DOCUMENTS
              if record["kind"] == "pdf"}


def pdf_paragraphs() -> list[dict]:
    """Every PDF page block, cited by page number.

    A page block is a run of text between blank lines on one page. Blocks
    shorter than six words are page furniture - headers, footers, figure
    labels - and are dropped rather than indexed as if they were rules.
    """
    records: list[dict] = []
    for document, filename in corpus.PDF_TEXT_NAME.items():
        meta = PDF_LAYOUT[document]
        text = (config.RAW_TEXT_DIR / filename).read_text(
            encoding="utf-8", errors="replace")
        pages = text.split("\f")
        kept = 0
        for number, page in enumerate(pages, 1):
            for block in re.split(r"\n\s*\n", page):
                block = re.sub(r"[ \t]+", " ", block).strip()
                block = re.sub(r"\n", " ", block)
                if len(block.split()) < 6:
                    continue
                kept += 1
                citation = "%s p. %d" % (meta["short"], number)
                records.append(dict(
                    doc_id=filename.removesuffix(".txt"),
                    layer=meta["layer"], source=meta["short"],
                    source_title=meta["title"], section=citation,
                    section_head=meta["title"], appendix="", para_path="",
                    naive_path="", citation=citation, naive_citation=citation,
                    normative=True, seq=kept, page=number, text=block,
                    in_base_corpus=meta["in_base_corpus"]))
        print(f"  {filename:<34} {kept:5,} page blocks  {len(pages):4} pages  "
              f"{len(text.split()):7,} words")
    return records


def build_paragraphs() -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Parsing the regulations (stateful label stack)...")
    opened: set = set()
    records = cfr_paragraphs(opened)
    print("Reading the committed PDF text layers...")
    records += pdf_paragraphs()
    frame = pd.DataFrame(records)
    frame["page"] = frame["page"].fillna(-1).astype(int)
    frame.to_parquet(config.PARAGRAPHS_PARQUET, index=False, compression="zstd")
    print(f"Wrote {config.PARAGRAPHS_PARQUET.name}: {len(frame):,} paragraphs")

    open_paths = pd.DataFrame(
        [{"section": section, "appendix": appendix or "", "path": path}
         for section, appendix, path in sorted(opened)])
    open_paths.to_parquet(config.OPEN_PATHS_PARQUET, index=False, compression="zstd")
    print(f"Wrote {config.OPEN_PATHS_PARQUET.name}: {len(open_paths):,} ancestor "
          "paths the label stack opened")
    return frame, open_paths


# ---------------------------------------------------------------------------
# The chunk tables
# ---------------------------------------------------------------------------

def build_chunk_tables(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """The deployed chunk table, plus the four-way size comparison."""
    print("Packing chunks at the 240-token budget (30 CFR 57 included, flagged)...")
    units = chunking.units_from_paragraphs(paragraphs, include_duplicate=True)
    chunks = chunking.build_chunks(units, mode="tokens_240")
    frame = chunking.chunk_frame(chunks, with_tokens=True)
    frame.to_parquet(config.CHUNKS_PARQUET, index=False, compression="zstd")
    base = frame[frame["in_base_corpus"]]
    print(f"Wrote {config.CHUNKS_PARQUET.name}: {len(frame):,} chunks "
          f"({len(base):,} in the base corpus, "
          f"{len(frame) - len(base):,} in the opt-in duplicate)")

    print("Chunking the base corpus four ways for the size evidence...")
    base_units = chunking.units_from_paragraphs(paragraphs, include_duplicate=False)
    evidence = []
    for mode in chunking.CONFIG_ORDER:
        built = chunking.chunk_frame(chunking.build_chunks(base_units, mode=mode))
        built["config"] = mode
        over = int((built["tokens"] > config.MODEL_TOKEN_WINDOW).sum())
        print(f"  {chunking.CONFIG_LABELS[mode]:<30} {len(built):5,} chunks  "
              f"median {int(built['tokens'].median()):4} tokens  "
              f"max {int(built['tokens'].max()):6,}  over the window: {over:,}")
        evidence.append(built[["config", "layer", "source", "section",
                               "citation", "words", "tokens"]])
    size_evidence = pd.concat(evidence, ignore_index=True)
    size_evidence.to_parquet(config.CHUNK_SIZE_PARQUET, index=False, compression="zstd")
    print(f"Wrote {config.CHUNK_SIZE_PARQUET.name}: {len(size_evidence):,} rows")
    return frame


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def build_provenance(paragraphs: pd.DataFrame) -> pd.DataFrame:
    """One row per document: where it came from, and whether we may republish it."""
    words = paragraphs.groupby("source")["text"].apply(
        lambda column: sum(len(text.split()) for text in column))
    rows = []
    for record in corpus.DOCUMENTS:
        path = config.RAW_DIR / record["file"]
        pages = -1
        if record["kind"] == "pdf":
            text = (config.RAW_TEXT_DIR / corpus.PDF_TEXT_NAME[record["doc"]]).read_text(
                encoding="utf-8", errors="replace")
            pages = len(text.split("\f"))
        rows.append({
            "doc": record["doc"],
            "short": record["short"],
            "title": record["title"],
            "layer": record["layer"],
            "kind": record["kind"],
            "file": record["file"],
            "publisher": record["publisher"],
            "url": record["url"],
            "license": record["license"],
            "distribution": record["distribution"],
            "retrieved": config.CORPUS_RETRIEVED,
            "date_pin": config.ECFR_DATE_PIN if record["kind"] == "xml" else "",
            "md5": corpus.md5(path),
            "bytes": path.stat().st_size,
            "pages": pages,
            "words": int(words.get(record["short"], 0)),
            "in_base_corpus": record["in_base_corpus"],
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(config.PROVENANCE_CSV, index=False)
    print(f"Wrote {config.PROVENANCE_CSV.name}: {len(frame)} documents, "
          f"{frame['bytes'].sum() / 1e6:.1f} MB, {frame['words'].sum():,} words")
    return frame


def build_license_notes(manifest: pd.DataFrame) -> None:
    """The licence facts in prose, including the documents we could not use."""
    lines = [
        "# Corpus provenance and licensing",
        "",
        "Every document here is a US Government work, and that is only half of",
        "the question. A work with no copyright can still be restricted from",
        "redistribution by a **distribution statement** printed on its cover.",
        "Copyright and distribution control are independent gates, and a corpus",
        "has to pass both.",
        "",
        f"Retrieved {config.CORPUS_RETRIEVED}. Every eCFR document is date-pinned",
        f"to {config.ECFR_DATE_PIN}, so the regulation text cannot change under the",
        "evaluation set.",
        "",
        "## What is in the corpus",
        "",
        "| Document | Layer | Publisher | Licence | Distribution | In base corpus |",
        "|---|---|---|---|---|---|",
    ]
    for row in manifest.to_dict("records"):
        lines.append("| {doc} | {layer} | {publisher} | {license} | {distribution} | "
                     "{base} |".format(base="yes" if row["in_base_corpus"] else
                                       "opt-in (duplicate lab only)", **row))
    lines += [
        "",
        "## What was rejected, and why",
        "",
        "| Document | What it looked like | Why it was rejected | The rule it teaches |",
        "|---|---|---|---|",
    ]
    for row in corpus.REJECTED:
        lines.append("| {document} | {looked_like} | {why_rejected} | {lesson} |".format(**row))
    lines += [
        "",
        "## The vetting rule",
        "",
        "Check page 1 of the document. Accept **DISTRIBUTION STATEMENT A** -",
        '"Approved for public release; distribution is unlimited" - and nothing',
        "else. Statements B through F all restrict who may hold the document,",
        "and several carry a destruction notice as well.",
        "",
        f"{config.FETCH_POLICY}",
        "",
    ]
    config.LICENSE_NOTES.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {config.LICENSE_NOTES.name}")


# ---------------------------------------------------------------------------
# Build-time checks
# ---------------------------------------------------------------------------

def report_checks(paragraphs: pd.DataFrame, chunks: pd.DataFrame,
                  open_paths: pd.DataFrame) -> None:
    """Reproduce, at build time, the numbers the notebook will teach."""
    base = citations.hierarchical(paragraphs)

    manual = corpus.raw_text("TM 9-6115-464-12")
    scan = corpus.distribution_statement_scan(manual)
    print(f"\nLicence gate  TM 9-6115-464-12: {scan['verdict']} "
          f"(naive matches {scan['naive_matches']}, "
          f"normalised {scan['normalised_matches']})")

    naive = citations.naive_versus_stateful(base, open_paths)
    print("Naive citations wrong: "
          f"{naive.loc[naive['Measure'] == 'Citation wrong', 'Share'].iloc[0]}; "
          "pointing at a paragraph that does not exist: "
          f"{naive.loc[naive['Measure'].str.startswith('Citation names'), 'Share'].iloc[0]}")

    structural = citations.structural_check(base, open_paths)
    print(f"Structural self-check: {structural['structurally_invalid']} invalid "
          f"of {structural['labelled_paragraphs']:,} labelled paragraphs")

    xref = citations.cross_reference_check(base, open_paths)
    print(f"Independent cross-references: {xref['cross_references']} found, "
          f"stateful {xref['stateful_rate']:.1%}, naive {xref['naive_rate']:.1%}")

    evidence = pd.read_parquet(config.CHUNK_SIZE_PARQUET)
    for mode in ("section", "tokens_240"):
        share = chunking.truncation_share(evidence, mode)
        print(f"Tokens discarded, {chunking.CONFIG_LABELS[mode]:<30} {share:.1%}")

    available: set[str] = set()
    for group in chunks.loc[chunks["in_base_corpus"], "citations"]:
        available.update(group)
    questions = pd.read_csv(config.EVAL_CSV).fillna("")
    gold = [g for row in questions["gold_citations"]
            for g in str(row).split("|") if g]
    missing = sorted({g for g in gold if g not in available})
    print(f"Gold citations: {len(gold)} in the eval set, "
          f"{len(missing)} missing from the chunk table"
          + (f" -> {missing[:4]}" if missing else ""))


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true",
                        help="download the corpus (one-time, by hand, never at setup)")
    arguments = parser.parse_args()

    if arguments.fetch:
        fetch_all()
        return

    started = time.perf_counter()
    paragraphs, open_paths = build_paragraphs()
    chunks = build_chunk_tables(paragraphs)
    manifest = build_provenance(paragraphs)
    build_license_notes(manifest)
    report_checks(paragraphs, chunks, open_paths)
    print(f"\nCorpus rebuilt in {time.perf_counter() - started:.1f}s. "
          "Nothing here touched the network.")


if __name__ == "__main__":
    main()
