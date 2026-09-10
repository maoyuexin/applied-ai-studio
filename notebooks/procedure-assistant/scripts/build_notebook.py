"""Build 01_procedure_build.ipynb in the five Module 5 teaching stages.

This file is the canonical source of the notebook. Never hand-edit the .ipynb:
change a cell here and regenerate, then execute the notebook so its committed
outputs match the code that produced them.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_procedure_build.ipynb"

notebook = nbf.v4.new_notebook()
cells: list = []


def cell_metadata(language: str) -> tuple[str, dict[str, str]]:
    cell_id = f"procedure-build-{len(cells) + 1:03d}"
    return cell_id, {"id": cell_id, "language": language}


def md(text: str) -> None:
    cell_id, metadata = cell_metadata("markdown")
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n"), id=cell_id,
                                          metadata=metadata))


def code(text: str) -> None:
    cell_id, metadata = cell_metadata("python")
    cells.append(nbf.v4.new_code_cell(text.strip("\n"), id=cell_id,
                                      metadata=metadata))


def guide(question: str, marks: str, denominator: str, notice: str,
          term: str, matters: str, boundary: str) -> None:
    md(f"""
### How to read this plot

- **Question:** {question}
- **Marks and axes:** {marks}
- **Denominator:** {denominator}
- **What to notice:** {notice}
- **Term:** {term}
- **Why it matters:** {matters}
- **Boundary:** {boundary}
""")


# ═══════════════════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
# From a technician's question to the rule that answers it

**ITAI 2372 - Module 5 - AI in Manufacturing and Industry**

The finance cases scored a table of numbers and read a complaint letter. This one has to
find a *specific passage in a specific document* and put the right rule number on it - and
say "I cannot answer that" when the passage is not there.

| | Stage | What happens |
|---|---|---|
| **1** | **Ingestion, Provenance and Licensing** | The four corpus layers, where each document came from, and the licence gate that rejected the best one |
| **2** | **Chunking and Citation** | How a passage becomes numbers, why the budget is tokens and not words, and how a citation gets built |
| **3** | **Retrieval** | Word counting against sentence embeddings on 60 technician-phrased questions |
| **4** | **Evaluation and Refusal** | Four metrics, five question buckets, one threshold - and two checks that pass while being wrong |
| **5** | **Duplicate Corpus, Answers and Handoff** | What a near-identical document does to citations, three answers end to end, and the exported contract |

> **The assistant retrieves and drafts. It never authorizes work.** It does not approve a
> lockout, it does not issue a clearance, it does not decide that a machine is safe to open,
> and it never answers a safety question from the model's own memory. Every answer it gives
> is written from passages it retrieved, shown beside those passages, and read by a qualified
> person before anyone touches anything.

### The case

A plant's maintenance technicians ask the same kinds of question all day. *Who is allowed to
cut this lock off? How long do we keep the confined-space permit? What is the torque on that
manifold?* The answers exist - in federal regulation, in the site's own written program, in
the equipment manual - and finding them means knowing which of thirteen documents to open and
where to look. The narrow question is:

> **Which passage answers this question, what is its citation, and is the answer in the corpus at all?**

That last clause is the entire safety argument. A system that answers every question is not a
good system; it is an unmeasured one.

### The corpus

- **13 documents**, four deliberate layers: the law, the site procedure, the equipment manual,
  and the plain-language guide
- Every regulation **date-pinned to 2025-08-01**, so the text cannot change under the
  evaluation set
- Every document checked against **two independent licence gates**, not one
- **60 evaluation questions** in five buckets, 15 of which have no answer in the corpus
- Plus a 30-question set used only for the duplicate-corpus experiment in stage 5

Everything is committed beside this notebook. Running it needs no download, no API key and no
network - not for the corpus, not for the evaluation set, and not for the sentence encoder.
""")

code(r"""
# ===============================================================
# SETUP
# ===============================================================
import json
import warnings

import numpy as np
import pandas as pd
import plotly.io as pio

from raglab import (answers, chunking, citations, config, corpus,
                    evaluate, handoff, index, retrieval)

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 170)
pd.set_option("display.max_colwidth", 110)
pio.renderers.default = "notebook"
print(config.describe())
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 1
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 1 - Ingestion, Provenance and Licensing

**Question:** Which documents may we put in front of a technician, and how do we know we are
allowed to redistribute every one of them?

**What to expect in this stage:** the four layers a real maintenance question crosses, one row
per document with publisher, URL, licence and checksum, a recomputed checksum for every
committed file, and the licence gate that rejected the single best document we found.

**Why this stage exists:** a retrieval system is its corpus. Every later measurement -
retrieval accuracy, citation correctness, refusal rate - is a statement about *these thirteen
documents* and nothing else. And a corpus that cannot be redistributed cannot be shipped to a
class, however good it is.

**What passes to stage 2:** a verified 13-document manifest and 14,279 paragraphs of text with
provenance attached to every one.
""")

md(r"""
## 1.1 Four layers, because one question crosses all of them

Ask *"can I work under someone else's lock?"* and no single document answers it. The
regulation says what is legally required. The site's own written program says what this
employer decided to do about it, which is stricter. The manual says what this machine needs.
The OSHA booklet says what the rule means in English. A corpus with only the regulation in it
answers a third of the question and sounds certain doing it.
""")

code(r"""
# ===============================================================
# 1.1 THE FOUR LAYERS
# ===============================================================
corpus.layer_table()
""")

md(r"""
## 1.2 One row per document: where it came from, and whether we may use it

**Provenance** means the recorded answer to "where did this file come from and has it changed
since?". It has two halves and only one of them is checkable here.

The **source checksum** was recorded the moment the file was downloaded. Re-verifying it would
mean downloading again, which this notebook will not do. The **committed checksum** is
recomputed from the bytes in this repository every time the cell below runs. If a file were
edited, truncated or replaced after it was committed, that check fails - and it is the check
that matters for reproducing a result.

Every eCFR URL is pinned to `2025-08-01`. Regulations are amended. Without the pin, a question
whose gold citation is `1910.147(c)(6)(i)` could quietly stop being correct.
""")

code(r"""
# ===============================================================
# 1.2 THE PROVENANCE MANIFEST
# ===============================================================
manifest = corpus.load_manifest()
manifest[["doc", "layer", "publisher", "license", "distribution", "in_base_corpus"]]
""")

code(r"""
# ===============================================================
# 1.3 RECOMPUTE EVERY CHECKSUM FROM THE COMMITTED BYTES
# ===============================================================
checksums = corpus.verify_checksums()
print(f"Files verified: {len(checksums)}   "
      f"Mismatches: {(checksums['Match'] != 'yes').sum()}")
checksums
""")

code(r"""
# ===============================================================
# 1.4 WHAT THE CORPUS IS MADE OF
# ===============================================================
summary = corpus.summary(manifest)
print(summary.to_string(index=False))
figure = corpus.corpus_composition(manifest)
figure.show()
""")

guide(
    "Which documents carry the weight of this corpus, and which layer does each belong to?",
    "One horizontal bar per document, length = words in that document after extraction. "
    "Colour = layer: blue for the law, green for the site procedure, orange for the equipment "
    "manual, grey for the plain-language guide. The bar label is the word count.",
    "Words in the 12 base-corpus documents. 30 CFR part 57 is excluded here - it is opt-in and "
    "used only in the stage 5 duplicate experiment.",
    "One document - the generator set manual - carries about a quarter of all the words, and it "
    "is the only member of its layer. The equipment layer is one machine deep. A question about "
    "any other machine in the plant has no equipment layer at all to land in.",
    "**Layer** is our label, not the publisher's: it records what kind of question a document "
    "can answer, so that a thin layer is visible as a gap rather than discovered as a wrong "
    "answer.",
    "Corpus composition sets the ceiling on every later number. Bucket D of the evaluation set "
    "exists precisely because a technician will ask about the machines that are not in here.",
    "Length is not authority. The manual has the most words and the least legal force; the "
    "shortest bars include the regulation that governs everything else.",
)

md(r"""
## 1.5 Public domain is not the same as redistributable

This is the part that catches people, and it caught us.

A **US Government work** carries no copyright - 17 USC 105. That settles the *copyright*
question and it settles nothing else. Military and agency documents also carry a
**distribution statement** printed on page 1, which controls *who may hold the document*.
The two are independent gates and a corpus has to pass both.

The best equipment manual we found was **TM 9-6115-641-24**, a 684-page generator set manual.
No copyright. Real text layer. Exactly the content this lab needs. Already sitting on a public
website. Page 1 carries:

> **DISTRIBUTION STATEMENT C** - Distribution authorized to U.S. Government agencies and their
> contractors ... accompanied by a **destruction notice** instructing the holder to destroy the
> document by any method that will prevent disclosure of contents.

It was rejected. The rule we adopted is narrow enough to apply without a lawyer:

> **Check page 1. Accept DISTRIBUTION STATEMENT A - "Approved for public release; distribution
> is unlimited" - and nothing else.** Statements B through F all restrict who may hold the
> document.

The manual that *is* in this corpus, TM 9-6115-464-12, has to pass that gate on its own
evidence. The cell below does not consult a spreadsheet; it searches the document's own
extracted text.
""")

code(r"""
# ===============================================================
# 1.5 THE LICENCE GATE, RUN AGAINST THE DOCUMENT'S OWN TEXT
# ===============================================================
manual_text = corpus.raw_text("TM 9-6115-464-12")
scan = corpus.distribution_statement_scan(manual_text)
print(f"Document: TM 9-6115-464-12   ({len(manual_text.split()):,} words of extracted text)")
print(json.dumps(scan, indent=2))

assert scan["statement_a_present"], "Statement A is not present - this document cannot ship."
assert not scan["restrictive_statement_present"], "A restrictive statement is present."
print("\nGATE PASSED: DISTRIBUTION STATEMENT A verified in the document's own text,")
print("and no restrictive statement (B-F) appears anywhere in it.")
""")

md(r"""
### Why the same document matches once or three times

`naive_matches` and `normalised_matches` disagree above, and the reason is worth ten minutes
of anyone's time. A PDF cover page renders the sentence with doubled spaces and inconsistent
capitalisation. A matcher that searches for the exact string `"Approved for public release"`
finds it once. A matcher that lowercases the text and collapses runs of whitespace first finds
every rendering.

The document did not change. Only the matcher did. A licence check that is one space away from
returning "not found" is not a licence check - and "not found" here would have thrown away a
document we are entitled to use.
""")

code(r"""
# ===============================================================
# 1.6 EVERY RENDERING OF THE STATEMENT, AS IT APPEARS IN THE TEXT
# ===============================================================
corpus.statement_excerpts(manual_text)
""")

md(r"""
## 1.7 What we rejected, and what each rejection teaches

The third row is the one that surprises people. **iFixit** publishes repair guides under
Creative Commons BY-NC-SA - an open licence, with a badge. The site's terms of use then state
that using the data to train a machine learning or AI model violates those terms. The badge
and the terms say different things, and the terms win.

An open-looking licence can be explicitly closed to *this particular use*. Read the terms, not
the badge.
""")

code(r"""
# ===============================================================
# 1.7 THE REJECTED DOCUMENTS
# ===============================================================
corpus.rejected_table()
""")

md(r"""
### Stage 1 conclusion

Thirteen documents, four layers, two independent licence gates, and every committed file
verified against its recorded checksum. The most useful equipment manual we found is not here,
and neither are the OEM service manuals a real plant would actually want - they are
dealer-portal only at any price a classroom can accept. That is the honest shape of this
problem: **the most useful corpus is usually the one you are not allowed to have.** Say so,
and build on what you may use.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 2
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 2 - Chunking and Citation

**Question:** How does a page of regulation become something a machine can search, and how
does the rule number survive the trip?

**What to expect in this stage:** the tokeniser applied to a real sentence, four chunking
policies measured against the encoder's hard limit, and two citation builders scored against
two different ground truths.

**Why this stage exists:** a retriever does not search documents, it searches **chunks**. Two
decisions taken here - how big a chunk is, and what citation it carries - do more damage than
any model choice made later. Both fail *silently*.

**What passes to stage 3:** a table of 3,098 chunks, each under 240 tokens, each carrying a
citation that has been checked against evidence the chunker did not produce.
""")

md(r"""
## 2.1 How a question and a passage become numbers

**Retrieval** here means: turn every passage into a fixed-length list of numbers once, turn
the question into the same kind of list at query time, and return the passages whose numbers
point in the most similar direction.

- **Input:** a string of text.
- **The local operation:** the text is split into **wordpiece tokens** - sub-word units from a
  fixed 30,522-entry vocabulary. `"de-energize"` is not one word to the model; it becomes
  several pieces. The model then combines those pieces into a single 384-number summary.
- **What is learned:** the mapping from wordpieces to that 384-dimensional space. It was
  trained on general English, not on OSHA.
- **What is configured:** everything else - the 256-token window, cosine similarity, float16
  storage, and the chunk size we choose.
- **Output:** one 384-number vector per chunk, 3,098 of them.
- **What it does not prove:** that a retrieved passage *answers* the question. The model places
  things near each other. Nothing in it reads the question and the passage together and judges
  relevance.

`all-MiniLM-L6-v2` reads at most **256 wordpiece tokens**. Not 256 words - tokens. That
difference is the whole of section 2.2.
""")

code(r"""
# ===============================================================
# 2.1 ONE SENTENCE, AS THE MODEL ACTUALLY SEES IT
# ===============================================================
sentence = "Each lockout device shall be removed by the employee who applied it."
preview = chunking.tokenize_preview(sentence, limit=20)
print(f"{len(sentence.split())} words  ->  "
      f"{chunking.count_tokens(sentence)} wordpiece tokens")
preview
""")

md(r"""
## 2.2 Why the budget is tokens and not words

A word target does not bound tokens, and the gap is worst in exactly the passages that hold
numeric answers. A maintenance table is typeset with dot leaders:

```
Intake manifold mounting nuts.. . . . . . . . . . . . . . . . 35 lb-ft
```

The tokeniser turns each run of dots into its own tokens. A 150-word target produced a
**3,398-token** chunk in this corpus. Anything past 256 is not truncated with an error - it is
simply never encoded. The vector describes the beginning of the passage and the rest does not
exist as far as the index is concerned.

Four policies, measured on the same corpus: two word targets, whole-section chunks, and the
240-token budget this lab deploys. 240 leaves room under 256 for `[CLS]`, `[SEP]` and the
section-heading prefix that every indexed passage carries.
""")

code(r"""
# ===============================================================
# 2.2 FOUR CHUNKING POLICIES, MEASURED
# ===============================================================
size_evidence = pd.read_parquet(config.CHUNK_SIZE_PARQUET)
sizes = chunking.size_table(size_evidence)
print(f"Chunking rule deployed: {config.CHUNKING_RULE}\n")
sizes
""")

code(r"""
# ===============================================================
# 2.3 WHERE EACH POLICY SITS AGAINST THE 256-TOKEN WALL
# ===============================================================
chunking.token_length_figure(size_evidence).show()
""")

guide(
    "Do the chunks any policy produces actually fit inside the window the encoder can read?",
    "One overlaid histogram per policy; x = tokens in a chunk, clipped at 600 so the long tail "
    "does not flatten everything; y = number of chunks on a log scale. The dashed vertical line "
    "is the encoder's hard 256-token limit.",
    "Every chunk the policy produced from the 12 base-corpus documents: 7,744 chunks at the "
    "60-word target, 3,312 at 150 words, 1,139 whole sections, 3,098 at the 240-token budget.",
    "The blue distribution stops dead at the line - by construction. Every other policy has "
    "mass to the right of it, and the whole-section policy has chunks past 22,000 tokens.",
    "**Token** = a wordpiece unit, not a word. The y axis is log-scaled because the counts span "
    "four orders of magnitude; equal vertical distances are equal *ratios*, not equal counts.",
    "Anything right of the line is text that exists in the chunk table, looks indexed, and was "
    "never read by the encoder.",
    "This plot shows fit, not quality. A chunk inside the window can still be the wrong size for "
    "answering questions - it just is not silently amputated.",
)

md(r"""
## 2.4 Required: whole-section chunking silently discards two thirds of the corpus

"One section, one chunk" is the most natural chunking rule anyone proposes, and it is the worst
one here. A CFR section is not a paragraph; `1910.217` alone runs to 470 paragraphs.

The measurement below is the share of *all tokens in the index* that fall past the encoder's
window: `sum(max(0, tokens - 256)) / sum(tokens)`. There is no warning at build time. The
index builds, the chunk count looks reasonable, and queries return results. Nothing anywhere
reports that most of the corpus was never encoded.
""")

code(r"""
# ===============================================================
# 2.4 THE TOKENS EACH POLICY THROWS AWAY WITHOUT SAYING SO
# ===============================================================
for mode in chunking.CONFIG_ORDER:
    share = chunking.truncation_share(size_evidence, mode)
    print(f"  {chunking.CONFIG_LABELS[mode]:<32} {share:6.1%} of all tokens never encoded")

section_loss = chunking.truncation_share(size_evidence, "section")
budget_loss = chunking.truncation_share(size_evidence, "tokens_240")
print(f"\nWhole-section chunking discards {section_loss:.1%} of the corpus.")
print(f"The 240-token budget discards {budget_loss:.1%}.")
print("Neither policy raised an error, a warning, or a log line.")
chunking.discarded_tokens_figure(size_evidence).show()
""")

guide(
    "How much of the corpus does each chunking policy throw away before the encoder ever sees it?",
    "One bar per policy; height = the share of all tokens in that policy's chunks that sit past "
    "the 256-token limit. Red is the whole-section policy, blue is the deployed budget.",
    "All tokens produced by that policy across the 12 base-corpus documents - "
    "`sum(max(0, tokens - 256)) / sum(tokens)`, so the denominator is the whole corpus as that "
    "policy chunked it, not a sample.",
    "The whole-section bar is roughly two thirds. The deployed policy is a flat zero, and it is "
    "zero by construction rather than by luck.",
    "**Silent truncation** = input beyond a model's window is dropped with no error. The system "
    "does not fail; it succeeds on less text than you think it has.",
    "A technician searching for a torque value in a long section would get no result and "
    "reasonably conclude the manual does not contain it.",
    "A 0% bar does not mean the chunks are well chosen - only that none of them is being cut "
    "off. Chunk *quality* is measured in stage 3, by retrieval.",
)

md(r"""
## 2.5 The citation is the safety-critical field

A wrong passage is visible: a technician reads it and sees it is about something else. A wrong
**citation** is not. `29 CFR 1910.147(c)(4)(ii)` is confident, correctly formatted, and looks
exactly like a right answer. Someone writes it on a permit.

A **naive chunker** builds the citation from the paragraph's own leading label: it sees a
paragraph starting `(B)` inside section 1910.147 and emits `1910.147(B)`. That is wrong
whenever the paragraph is nested, which is almost always, because CFR paragraphs nest six
levels deep - `(a)(1)(ii)(B)` - and **the parent labels live in earlier paragraphs**.

The fix is a **stateful label stack**: a running record of the open ancestor path, carried
across paragraphs, so a bare `(ii)` arriving thirty paragraphs later still knows it belongs
under `(a)(1)`. Four real problems it has to survive, all present in this corpus:

1. parent labels in earlier paragraphs - `(a)(1)` in paragraph 12, a bare `(ii)` in paragraph 47;
2. several labels running in on one paragraph - `(h) PSDI-(1) General. (i) The requirements ...`;
3. `(i)` is both the ninth letter and the first lowercase roman numeral;
4. appendices, notes, tables and definition lists restart the numbering *inside* a section.
""")

code(r"""
# ===============================================================
# 2.5 THE SAME PARAGRAPHS, CITED TWO WAYS
# ===============================================================
paragraphs = pd.read_parquet(config.PARAGRAPHS_PARQUET)
open_paths = citations.load_open_paths()
hierarchy = citations.hierarchical(paragraphs)
print(f"Citation audit scope: {config.CITATION_AUDIT_SCOPE} "
      f"({len(hierarchy):,} paragraphs)")
print(config.CITATION_AUDIT_NOTE)
citations.audit_table(paragraphs)
""")

md(r"""
## 2.6 Required: scoring both chunkers against evidence they did not produce

Two graders, and the difference between them is the lesson.

**The structural check** asks: does every ancestor of this citation exist in this section? The
chunker is grading its own output against a list of paths the chunker itself produced. It is
circular by construction, which is why section 4.6 comes back to it.

**The cross-reference check** is independent. The regulation cites its own paragraphs 194
times - *"the requirements of paragraph (c)(4)(ii) of this section"*. Those paths were written
by OSHA. A citation set that cannot resolve them is wrong however clean its self-check looks.
""")

code(r"""
# ===============================================================
# 2.6 NAIVE vs STATEFUL, SCORED TWO WAYS
# ===============================================================
naive = citations.naive_versus_stateful(hierarchy, open_paths)
structural = citations.structural_check(hierarchy, open_paths)
xref = citations.cross_reference_check(hierarchy, open_paths)

print(naive.to_string(index=False))
print(f"\nSTRUCTURAL SELF-CHECK (the chunker grading itself)")
print(f"  structurally invalid citations : {structural['structurally_invalid']} "
      f"of {structural['labelled_paragraphs']:,} labelled paragraphs")
print(f"  {structural['note']}")
print(f"\nINDEPENDENT CHECK (OSHA's own internal cross-references)")
print(f"  distinct cross-references found : {xref['cross_references']}")
print(f"  resolved by the stateful stack  : {xref['stateful_rate']:.1%}")
print(f"  resolved by the naive chunker   : {xref['naive_rate']:.1%}")
""")

code(r"""
# ===============================================================
# 2.7 THE HAND-AUDITED SAMPLE: 20 CITATIONS CHECKED BY A PERSON
# ===============================================================
verification = citations.verify_audit_sample(paragraphs)
print(json.dumps(verification, indent=2))
""")

code(r"""
# ===============================================================
# 2.8 BOTH GRADERS, SIDE BY SIDE
# ===============================================================
citations.citation_figure(naive, xref, structural).show()
""")

guide(
    "How correct is each citation builder, and does the answer depend on who is grading?",
    "Two grouped pairs of bars. Blue = the deployed stateful label stack, red = the naive "
    "chunker. The left pair scores citations against the paragraph paths that exist; the right "
    "pair scores them against the regulation's own internal cross-references. The annotation "
    "above reports the structural self-check.",
    "Left pair: 3,678 labelled paragraphs in 29 CFR 1910. Right pair: 194 distinct internal "
    "cross-references written by OSHA in that same text.",
    "The naive chunker is wrong on about four citations in five, and three quarters of its "
    "citations name a paragraph that does not exist anywhere in that section. Both graders "
    "agree - but only the right-hand grader *could* have disagreed, because only it was written "
    "by someone other than us.",
    "**Independent ground truth** = an answer key produced by a party with no stake in the "
    "system being graded. The left-hand bars are a consistency check; the right-hand bars are a "
    "test.",
    "A plausible citation to a rule that does not exist is the exact failure this module is "
    "about, and it came from a parsing bug, not from a model.",
    "91.8% is not 100%. The remaining cross-references point into tables and appendices this "
    "parser deliberately suppresses. High is not perfect, and the gap is known rather than "
    "hidden.",
)

md(r"""
### Stage 2 conclusion

Two silent failures, both fixed and both measured: a chunk size that throws away most of the
corpus without an error message, and a citation builder that is wrong four times in five while
looking entirely correct. Neither involved a model. Both would have shipped.

The chunk table that goes to stage 3 has every chunk inside the encoder's window, a citation
built by the stateful stack, and 20 citations that a person opened the regulation and checked
by hand.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 3
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 3 - Retrieval

**Question:** Does a small transformer actually beat counting words, on questions phrased the
way a technician asks them?

**What to expect in this stage:** both retrievers built on the identical chunk table, one real
query shown through each, a head-to-head on 45 answerable questions, and the finding that
matters more than the winner.

**Why this stage exists:** this is the choice everyone thinks is the project. It is not. It is
the smallest decision made in this notebook, and stage 3 exists partly to show how easy it is
to make the benchmark say whatever you want.

**What passes to stage 4:** two fitted retrievers and per-question results for all 60 questions.
""")

md(r"""
## 3.1 Two ways to turn text into numbers

**TF-IDF** counts words. Each passage becomes a long sparse vector over the vocabulary,
weighted so rare words count for more than common ones, and similarity is the overlap of those
weighted counts. Nothing is learned about meaning. `"de-energize"` and `"shut off the power"`
share no tokens at all, so their similarity is zero.

**MiniLM** is a six-layer transformer trained so that sentences meaning the same thing land
near each other in a 384-dimensional space. `"de-energize"` and `"shut off the power"` land
close together because the training data used them interchangeably.

Both produce one vector per chunk. Both are indexed on the same text: the section heading, then
the passage. Neither reads the question and the passage together.
""")

code(r"""
# ===============================================================
# 3.1 BUILD BOTH RETRIEVERS ON THE SAME 3,098 CHUNKS
# ===============================================================
all_chunks = chunking.load_chunks(include_duplicate=True)
chunks = all_chunks[all_chunks["in_base_corpus"]].reset_index(drop=True)
print(f"Base corpus: {len(chunks):,} chunks   "
      f"Opt-in duplicate held back for stage 5: "
      f"{len(all_chunks) - len(chunks):,} chunks")

minilm = index.EmbedRetriever(chunks)
tfidf = index.TfidfRetriever(chunks)
index.build_report({"tfidf": tfidf, "minilm": minilm}, chunks)
""")

md(r"""
## 3.2 The same question through both

A technician does not type the words the regulation uses. They say *"cut the lock off"*, not
*"removal of lockout devices by other than the authorized employee"*.
""")

code(r"""
# ===============================================================
# 3.2 ONE QUERY, TWO RETRIEVERS
# ===============================================================
question = "Can I cut someone else's lock off if they went home?"
print(f"QUESTION: {question}\n")
print("--- TF-IDF word counts ---")
display(retrieval.show(tfidf, question, k=3, width=200))
print("--- MiniLM sentence embeddings ---")
display(retrieval.show(minilm, question, k=3, width=200))
""")

md(r"""
## 3.3 The head-to-head, and what each metric counts

Four numbers, and keeping the first two apart from the second two is the point.

- **hit@1** - the top result carries the **gold citation**. Right rule, first try.
  Numerator: questions where it happened. Denominator: the 45 answerable questions (buckets
  A, B and C). Buckets D and E have no gold citation, so they are excluded here.
- **hit@5** - the gold citation is somewhere in the top 5.
- **sec@1 / sec@5** - a result comes from the gold **section**, whatever paragraph label it
  carries. Right *text*.
- **coverage@5** - for questions with several gold citations, the fraction of them retrieved.
  A question needing the regulation *and* the site procedure scores 0.5 if it finds one.

`hit` and `sec` usually move together. Stage 5 makes them come apart on purpose, and that gap
is where this system is most dangerous.
""")

code(r"""
# ===============================================================
# 3.3 SCORE BOTH RETRIEVERS ON ALL 60 QUESTIONS
# ===============================================================
questions = evaluate.load_eval()
results = {retriever.display: retrieval.evaluate(retriever, questions)
           for retriever in (tfidf, minilm)}
leaderboard = retrieval.leaderboard(results)
leaderboard
""")

code(r"""
# ===============================================================
# 3.4 THE HEAD-TO-HEAD
# ===============================================================
retrieval.retriever_comparison(results).show()
""")

guide(
    "On questions phrased the way a technician talks, does the embedding model beat word counting?",
    "Grouped bars over four measures. Orange = TF-IDF word counts, blue = MiniLM embeddings. "
    "The first pair is 'right rule' (the gold citation), the second pair is 'right text' (the "
    "gold section, any paragraph label).",
    "The 45 answerable questions - buckets A, B and C. The 15 questions that should be refused "
    "are excluded, because they have no correct citation to hit.",
    "MiniLM wins on every one of the four measures. The 'right text' bars sit well above the "
    "'right rule' bars for both retrievers: finding the correct section is markedly easier than "
    "landing on the correct paragraph inside it.",
    "**hit@k** = the share of questions where a correct answer appears in the top k results. "
    "It says nothing about the ones ranked below it, and nothing about whether a person would "
    "accept the answer.",
    "The gap between 'right text' and 'right rule' is the citation-precision problem from stage "
    "2 showing up in retrieval, and it is the gap stage 5 blows wide open.",
    "This is one corpus and 45 questions. It does not show that embeddings beat keywords in "
    "general - the very next plot shows the same comparison reversing.",
)

md(r"""
## 3.4 Required: your benchmark depends on how you wrote the questions

Earlier in this work a keyword baseline scored **90% hit@1** on this corpus. It looked
conclusive: skip the transformer, ship TF-IDF.

That number was measured on questions **generated from the passage text** - take a passage,
paraphrase it into a question, use it as a test. Do that and the question shares its rare words
with the answer, which is precisely the signal TF-IDF scores on. The benchmark handed a keyword
matcher the answer and then congratulated it for finding it.

The 60 questions here were written the other way: phrased the way a technician asks, using the
words a technician uses. Same corpus, same retriever, same metric. TF-IDF goes from 90% to
about a third, and the ranking of the two approaches **reverses**.

This is the opposite of what Module 4's text case found. There, TF-IDF and MiniLM tied on
complaint routing - a fair test, honestly run, where the simple model was genuinely good
enough. The difference between the two modules is not the models. **It is how the questions
were written.** A benchmark is a claim about your evaluation set at least as much as a claim
about your system.
""")

code(r"""
# ===============================================================
# 3.5 THE SAME RETRIEVER, TWO WAYS OF WRITING THE QUESTIONS
# ===============================================================
measured = {
    "research_tfidf_hit1": config.SPIKE["research_tfidf_hit1_claim"],
    "technician_tfidf_hit1": retrieval.overall(results[tfidf.display])["hit@1"],
    "technician_minilm_hit1": retrieval.overall(results[minilm.display])["hit@1"],
}
for name, value in measured.items():
    print(f"  {name:<26} {value:.3f}")
retrieval.question_phrasing_figure(measured).show()
""")

guide(
    "How much of a retrieval score is a property of the retriever, and how much is a property "
    "of the questions?",
    "Two groups on the x axis: questions copied from the passage text, and questions phrased "
    "the way a technician talks. Orange = TF-IDF, blue = MiniLM. Bar height = hit@1. MiniLM was "
    "not measured on the first question style, so it has no bar there.",
    "hit@1 over answerable questions in each style: the earlier passage-derived set on the left, "
    "the 45 technician-phrased questions in this notebook's evaluation set on the right.",
    "The same retriever on the same corpus scores 90% or about 33% depending only on who wrote "
    "the questions. The left-hand bar is not a lie - it is a correct measurement of the wrong "
    "thing.",
    "**Evaluation-set leakage** = the test questions share information with the answers that a "
    "real user's questions would not. Here the leakage is vocabulary: the question was made out "
    "of the passage.",
    "If you accept the left-hand number you ship a keyword matcher and it fails in the field on "
    "the first question that says 'cut the lock off'.",
    "Do not read this as 'keyword search is bad'. Read it as 'this benchmark was measuring the "
    "questions'. Module 4 ran a fair text comparison and the simple model tied.",
)

code(r"""
# ===============================================================
# 3.6 WHERE EACH RETRIEVER WINS AND LOSES, BY QUESTION TYPE
# ===============================================================
retrieval.per_bucket(results)
""")

md(r"""
### Stage 3 conclusion

MiniLM is the deployed retriever because it wins on technician-phrased questions on every
measure. That is a smaller finding than the one beside it: the same comparison, run on
questions written a different way, reverses. Before trusting any retrieval benchmark - ours
included - ask who wrote the questions and what they were made out of.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 4
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 4 - Evaluation and Refusal

**Question:** How often is the system right, how often does it correctly say "I do not know",
and which of our checks are lying to us?

**What to expect in this stage:** 60 questions in five buckets, four metrics, one refusal
threshold chosen on evidence, and two checks that report success while being wrong.

**Why this stage exists:** the ability to refuse is the whole safety argument for this system.
A quarter of the evaluation set has no answer in the corpus, and getting those right is worth
more than another point of retrieval accuracy.

**What passes to stage 5:** a frozen operating policy - tau = 0.48 plus the
incorporation-by-reference rule - and an honest account of what it does not catch.
""")

md(r"""
## 4.1 Sixty questions, five buckets, and why fifteen of them have no answer

| Bucket | What it tests | Correct behaviour |
|---|---|---|
| **A** | Answerable from a single section | Return the passage and its citation |
| **B** | Answerable, but needs several sections | Return all of them; coverage matters |
| **C** | A numeric fact - a distance, a torque, a retention period | Return the passage *and* the value |
| **D** | Outside the corpus entirely | **Refuse** |
| **E** | The rule exists but points at a standard we do not have | **Refuse, and name the standard** |

Bucket E is the interesting one. The passage that answers an E question *is* in the corpus, it
retrieves confidently, and it says something like *"shall conform to the specifications of ANSI
B31.1.0-1967"*. The regulation **incorporates a consensus standard by reference** rather than
reproducing it. A confidence threshold cannot see this: the retrieval is good. The system has
to know that finding the governing rule and being able to answer the question are different
events.

The four metrics, in the order they matter for a safety assistant:

1. **retrieval hit@k** - did the right passage come back at all;
2. **citation correctness** - does it carry the rule number a person can look up. This is the
   headline safety metric, because a wrong citation is the failure a reader cannot detect;
3. **unsupported-claim rate** - does the drafted answer assert anything the passages do not
   contain;
4. **correct-refusal rate** - the one everyone forgets.
""")

code(r"""
# ===============================================================
# 4.1 THE EVALUATION SET
# ===============================================================
print(f"{len(questions)} questions   "
      f"{int(questions['bucket'].isin(['D', 'E']).sum())} of them must be refused\n")
evaluate.bucket_table(questions)
""")

md(r"""
## 4.2 Every gold citation must name a chunk that exists

Before any score means anything: if a gold citation names a passage that is not in the chunk
table, the question is unanswerable by construction and the score is fiction. The same applies
to bucket C's numeric values - the number has to actually appear in the gold passage.
""")

code(r"""
# ===============================================================
# 4.2 VALIDATE THE ANSWER KEY AGAINST THE CHUNK TABLE
# ===============================================================
validation = evaluate.validate_gold(questions, chunks)
print(json.dumps(validation, indent=2))
assert validation["missing_from_the_chunk_table"] == 0
assert validation["values_not_found_in_the_gold_chunk"] == 0
print("\nEvery gold citation resolves to a real chunk, and every bucket-C value")
print("appears in the passage its question points at.")
""")

md(r"""
## 4.3 What a confidence score can and cannot see

The refusal rule starts with the obvious idea: if the best match is weak, refuse. To choose the
threshold we need to see where each bucket's top-1 similarity actually falls.
""")

code(r"""
# ===============================================================
# 4.3 TOP-1 SIMILARITY BY BUCKET
# ===============================================================
signals = evaluate.policy_signals(minilm, questions)
retrieval.score_distribution(signals).show()
""")

guide(
    "Can a single confidence threshold separate the questions we can answer from the ones we "
    "cannot?",
    "One box per bucket with every question drawn as a point; y = top-1 cosine similarity "
    "between the question and its best-matching chunk. The dashed line is the chosen threshold, "
    "tau = 0.48.",
    "All 60 questions, each appearing once in its own bucket: A=25, B=10, C=10, D=8, E=7. The "
    "bucket size is printed in each label.",
    "Bucket D - genuinely outside the corpus - sits low, which is what makes a threshold work at "
    "all. Bucket E sits *among the answerable buckets*, because the passage that governs an E "
    "question really is in the corpus and really does match the question.",
    "**Cosine similarity** = the cosine of the angle between two vectors, 1.0 for identical "
    "direction and 0 for unrelated. It measures closeness in the embedding space, not "
    "correctness.",
    "Bucket E is invisible to any threshold. It needs a second rule that reads the retrieved "
    "text, which is why the policy has two rules and not one.",
    "A high score is not evidence of a correct answer. Section 4.6 shows a confident, "
    "top-ranked, entirely wrong passage.",
)

md(r"""
## 4.4 Two rules, and the threshold that balances them

- **Rule 1 - low confidence.** Top-1 cosine similarity below **tau = 0.48**. Refuse and say
  what the corpus does contain.
- **Rule 2 - incorporated by reference.** The retrieved context incorporates a named consensus
  standard (ANSI, NFPA, ASTM, ASME, ...) **and** the question asks for a specification, rating
  or value. Refuse, name the standard, and tell the reader where to get it.

Rule 2 exists entirely because of what the previous plot showed. Raising tau until it caught
bucket E would refuse a fifth of the answerable questions.

Three rates, and their denominators:

- **correct refusal, D** = D questions refused / 8 D questions
- **correct refusal, E** = E questions refused / 7 E questions
- **false refusal** = answerable questions refused / 45 A+B+C questions
""")

code(r"""
# ===============================================================
# 4.4 SWEEPING THE THRESHOLD
# ===============================================================
sweep = evaluate.policy_sweep(signals)
print(sweep.to_string(index=False))
evaluate.sweep_figure(signals).show()
""")

guide(
    "Where should the refusal threshold sit, and what does moving it cost?",
    "Three lines against tau on the x axis. Green = share of bucket D correctly refused, blue "
    "dotted = share of bucket E correctly refused, red = share of answerable questions wrongly "
    "refused. The dashed vertical line marks the chosen tau = 0.48.",
    "Each line has its own denominator: 8 questions for D, 7 for E, 45 for A+B+C. All three are "
    "plotted as shares so they share a y axis.",
    "The green line reaches its plateau at 0.48 while the red line is still near the floor. Push "
    "tau to 0.54 and bucket E finally rises to 100% - at the cost of wrongly refusing more than "
    "one answerable question in ten.",
    "**False refusal** = the system declines a question it could have answered. It is the cost "
    "side of caution, and it is why 'refuse more' is not a free improvement.",
    "The plateau is where the second rule earns its place: rule 2 catches bucket E without "
    "paying the red line's price.",
    "These curves come from 60 questions. The knee is real but its exact position is not "
    "precise to two decimal places - do not read 0.48 as special beyond 'in the flat region'.",
)

code(r"""
# ===============================================================
# 4.5 THE POLICY, APPLIED
# ===============================================================
policy_result = evaluate.policy_result(signals)
print(json.dumps({k: v for k, v in policy_result.items() if k != "by_bucket"}, indent=2))
print()
for bucket, outcome in policy_result["by_bucket"].items():
    label = config.BUCKETS[bucket][0]
    print(f"  {bucket}  {label:<38} refused {outcome['refused']:>2}/{outcome['questions']:<2}"
          f"  ({outcome['rate']:.1%})")
""")

md(r"""
## 4.6 Required: a self-check that passed 100% while emitting a wrong citation

Stage 2 reported **0 structurally invalid citations**. That number was true, and for a while it
was true of a parser that was emitting `29 CFR 1910.217(i)(iii)` for a paragraph whose real
citation is `29 CFR 1910.217(h)(1)(iii)`.

The cause is problem 3 from stage 2. `(i)` is the ninth lowercase letter *and* the first
lowercase roman numeral. Arriving after `(h)` and `(1)`, the letter reading is a perfectly
legal successor of `(h)`, so the stack takes it and the whole branch shifts up a level. One
token of lookahead fixes it: the next label is `(ii)`, which only a roman run produces.

The structural check could not see any of this. It validates each citation against the set of
paths *the same parser produced*, so a consistently wrong parser is consistently valid. The
cell below runs the real parser over a real subpart twice, with the lookahead on and off, and
lets both graders score both parses.
""")

code(r"""
# ===============================================================
# 4.6 ONE LABEL, TWO LEGAL READINGS
# ===============================================================
citations.label_stack_readings()
""")

code(r"""
# ===============================================================
# 4.7 THE SAME FILE PARSED TWICE, GRADED BY BOTH CHECKS
# ===============================================================
experiment = citations.ambiguity_experiment()
for row in experiment.to_dict("records"):
    print(f"  {row['Parser']}")
    for key in list(row)[1:]:
        print(f"      {key:<46} {row[key]}")
    print()
print("The self-check cannot tell these two parsers apart. The regulation's own")
print("cross-references can, and that is the only reason the bug was found.")
""")

md(r"""
## 4.8 Required: the claim check catches invention, not misattribution

The **unsupported-claim check** takes a drafted answer, strips out the citation strings - those
are metadata, not assertions about the world - and requires every remaining numeral to appear
in the passages that were actually retrieved for that question.

It works. It caught an invented torque figure during development: an answer asserting
`42 lb-ft` for something the corpus never gave a torque for.

Now watch it fail. Question E01 asks for a pressure rating on forging machine air piping. The
**top-ranked** passage is `29 CFR 1910.253(d)(1)(ii)(B)` - welding gas manifold piping, not
forging machines - and it contains a confident number: a working pressure of **250 psi**. An
answer that says "250 psi" copies that number accurately out of a passage that was genuinely
retrieved. The check passes it, because the number really is in the context.

The check tests **provenance**, not **relevance**. "Zero unsupported claims" reads like "zero
hallucinations" and is a materially weaker statement.
""")

code(r"""
# ===============================================================
# 4.8 TWO WRONG ANSWERS TO THE SAME QUESTION
# ===============================================================
pack = answers.build_pack(minilm, questions)
answers.claim_check_demonstration(pack)
""")

md(r"""
### Stage 4 conclusion

The deployed policy refuses 7 of 8 questions that are outside the corpus and 6 of 7 that point
at a standard we do not hold, while wrongly refusing 2 of 45 answerable questions. Those are
good numbers and they are not the stage's finding.

The finding is that **two separate checks reported success while being wrong**, in two
different ways. The structural check was circular - it graded the parser against the parser.
The claim check was too narrow - it verified where a number came from, not whether that source
governed the question. Both were caught only by evidence produced outside the system: OSHA's
own cross-references, and a person reading the top-ranked passage. Build at least one check
your system cannot influence.
""")

# ═══════════════════════════════════════════════════════════════════════════
# Stage 5
# ═══════════════════════════════════════════════════════════════════════════

md(r"""
---
# 5 - Duplicate Corpus, Answers and Handoff

**Question:** What happens to citations when the corpus contains two nearly identical
documents - and what exactly do we hand to the service?

**What to expect in this stage:** a measured near-duplicate, the collapse it causes, three
packaged questions walked end to end, and eight exported files verified by reloading them.

**Why this stage exists:** "add more documents" is the default instinct when a retrieval system
underperforms. On this corpus it destroys the safety-critical field while leaving every
aggregate metric looking fine.

**What passes out of this notebook:** the eight-file artifact contract in `artifacts/`.
""")

md(r"""
## 5.1 Two regulations that say the same thing

**30 CFR 56** covers surface metal and nonmetal mines. **30 CFR 57** covers underground mines.
MSHA wrote them as a matched pair, so `56.14107` and `57.14107` are the same rule about the
same guarding requirement, and for hundreds of sections they are the same *sentences*.

That is not a mistake in the corpus. It is what a real document estate looks like: the 2019
procedure and the 2024 procedure, the US manual and the EU manual, the same standard adopted by
two agencies. Let us measure how alike they are before assuming anything.
""")

code(r"""
# ===============================================================
# 5.1 HOW ALIKE ARE THEY, MEASURED
# ===============================================================
similarity = evaluate.duplicate_similarity(paragraphs)
print(json.dumps(similarity, indent=2))
print(f"\n{similarity['byte_identical']} of {similarity['shared_section_numbers']} shared "
      f"section numbers are byte-for-byte identical.")
print(f"Mean similarity across all shared sections: {similarity['mean_similarity']}")
""")

md(r"""
## 5.2 Right text, wrong rule

Thirty questions ask about surface-mine rules, and every one has a twin in Part 57. Two
different things get measured, and separating them is the whole point:

- **right text@1** - the top result is the correct sentence, whether it came from Part 56 or its
  Part 57 twin. The passage on screen is the right passage.
- **right rule@1** - the top result carries the **Part 56** citation the question was asked
  about.

Before adding Part 57 these are the same number, because there is nothing to confuse. After,
the gap between them is the damage.
""")

code(r"""
# ===============================================================
# 5.2 ADD PART 57 AND RE-MEASURE
# ===============================================================
msha = evaluate.load_msha_eval()
duplicate_chunks = all_chunks[~all_chunks["in_base_corpus"]].reset_index(drop=True)
minilm_dup = minilm.extend(duplicate_chunks)
tfidf_dup = index.TfidfRetriever(all_chunks)

duplicate_results = {
    ("Part 56 only", minilm.display): evaluate.duplicate_measure(minilm, msha),
    ("Part 56 + Part 57", minilm.display): evaluate.duplicate_measure(minilm_dup, msha),
    ("Part 56 only", tfidf.display): evaluate.duplicate_measure(tfidf, msha),
    ("Part 56 + Part 57", tfidf.display): evaluate.duplicate_measure(tfidf_dup, msha),
}
print(f"Corpus grew from {len(chunks):,} to {len(all_chunks):,} chunks "
      f"(+{len(all_chunks) / len(chunks) - 1:.1%})\n")
evaluate.duplicate_table(duplicate_results)
""")

code(r"""
# ===============================================================
# 5.3 THE COLLAPSE
# ===============================================================
evaluate.duplicate_figure(duplicate_results).show()
""")

guide(
    "When a near-identical regulation joins the corpus, what breaks - finding the text, or "
    "citing the rule?",
    "Grouped bars in four groups: each retriever before and after Part 57 is added. Grey = right "
    "text (Part 56 or its twin counts), red = right rule (only the Part 56 citation counts). "
    "Both are top-1.",
    "The 30 MSHA questions, top-1 result only. Every one of them has a known twin section in "
    "Part 57.",
    "The grey bars barely move. The red bars collapse. TF-IDF falls furthest - almost to zero - "
    "because when two passages are byte-identical a word-counting scorer has literally no signal "
    "left to choose between them, so the tie is broken arbitrarily.",
    "**Right text, wrong rule** = the retrieved passage says the correct thing and carries a "
    "citation to a different regulation. It is the most dangerous output this system can "
    "produce, because it reads as correct.",
    "A technician writes the cited rule on a permit. An underground-mine citation on a "
    "surface-mine permit is a compliance failure that the passage text will never reveal.",
    "This is not a MiniLM-versus-TF-IDF result. Both fail. The lesson is about the corpus, and "
    "no retriever choice fixes it.",
)

code(r"""
# ===============================================================
# 5.4 HOW OFTEN IS IT RIGHT TEXT BUT WRONG RULE?
# ===============================================================
for (label, display), result in duplicate_results.items():
    if label == "Part 56 + Part 57":
        print(f"  {display:<28} {result['right_text_wrong_rule@1']:.1%} of the 30 questions")
""")

md(r"""
## 5.5 The aggregate score barely moved

Here is why this would ship. The main 60-question evaluation set contains no MSHA questions.
Adding 23% more corpus and destroying an entire domain moves the headline number by about two
percentage points - the kind of drift a dashboard reports as noise.

**Aggregate metrics hide targeted damage.** If you cannot slice a metric by domain, you cannot
see this class of failure at all.
""")

code(r"""
# ===============================================================
# 5.5 WHAT A DASHBOARD WOULD HAVE SHOWN
# ===============================================================
before = {
    "main_hit@5": retrieval.overall(results[minilm.display])["hit@5"],
    "msha_cite@1": duplicate_results[("Part 56 only", minilm.display)]["cite_hit@1"],
}
after = {
    "main_hit@5": retrieval.overall(retrieval.evaluate(minilm_dup, questions))["hit@5"],
    "msha_cite@1": duplicate_results[("Part 56 + Part 57", minilm.display)]["cite_hit@1"],
}
print(f"Main 60-question set, hit@5 : {before['main_hit@5']:.3f} -> {after['main_hit@5']:.3f}")
print(f"MSHA citation hit@1         : {before['msha_cite@1']:.3f} -> {after['msha_cite@1']:.3f}")
evaluate.collateral_figure(before, after).show()
""")

guide(
    "Would the metric we actually watch have told us that a domain stopped working?",
    "Two pairs of bars. Blue = before Part 57 was added, red = after. The left pair is the main "
    "60-question hit@5; the right pair is citation accuracy on the 30 MSHA questions. The "
    "annotation above each pair is the change.",
    "Left pair: 45 answerable questions of the main evaluation set. Right pair: the 30 MSHA "
    "questions. Two different denominators, deliberately shown together.",
    "The left pair is nearly flat. The right pair falls off a cliff. Both describe the same "
    "change to the same system.",
    "**Collateral damage** = a change that leaves the aggregate metric intact while destroying "
    "performance on a subset nobody is slicing by.",
    "Whatever domains your corpus covers, the evaluation set needs questions from each of them, "
    "and the metrics need to be reported per domain and not only pooled.",
    "The flat left pair is not evidence that the change was safe. It is evidence that the main "
    "evaluation set cannot see MSHA questions - which is a fact about the evaluation set.",
)

md(r"""
## 5.6 Three questions, end to end

The packaged answer set holds 20 questions: 16 answered and 4 refused. Every answer was written
**from the retrieved passages only**, by a person, and is cached - there is no generative model
anywhere in this system.

Each walkthrough shows exactly what the service shows: the question, the passages with their
citations and scores, the status, the drafted answer, and the citations a human has to verify.

**First:** an ordinary answered question, where the site procedure - not the regulation - is
what governs.
""")

code(r"""
# ===============================================================
# 5.6 WALKTHROUGH 1 - ANSWERED, FROM THE SITE PROCEDURE
# ===============================================================
answers.walkthrough(pack, "A21")
""")

md(r"""
**Second: the bucket-E refusal, and the subtly wrong passage sitting at rank 1.**

This is the most important cell in the notebook.

The question asks for a pressure rating on forging machine air piping. Rank 1 comes back at a
high score with `29 CFR 1910.253(d)(1)(ii)(B)`, which is about **welding gas manifold piping**,
and contains a number: **250 psi**. It is relevant-looking, correctly cited, genuinely in the
corpus, and completely wrong for this question.

The passage that actually governs is at **rank 3**, and what it says is that the piping *"shall
conform to the specifications of ANSI B31.1.0-1967"* - a standard the corpus does not contain
and cannot contain. So the correct output is not a number at all. It is a refusal that names
the standard the reader has to go and obtain.

An ungrounded model answers "250 psi". A grounded model that ranks by similarity alone answers
"250 psi". This system refuses, because rule 2 reads the retrieved text and notices the
incorporation by reference.
""")

code(r"""
# ===============================================================
# 5.7 WALKTHROUGH 2 - REFUSED, INCORPORATED BY REFERENCE
# ===============================================================
answers.walkthrough(pack, "E01")
""")

md(r"""
**Third:** a numeric question, where the chunk-level citation is coarser than the answer.

The sentence that answers this one is paragraph `(e)(6)`, but it was packed into a chunk whose
leading citation is `(e)(5)(ii)`. The citation is one paragraph coarse. That is a real
limitation of chunk-level citations, it is recorded in the model card, and the mitigation is
simple: **the service displays the whole passage, never only its label.** A reader who opens
the cited section finds the sentence a few lines below where the label points.
""")

code(r"""
# ===============================================================
# 5.8 WALKTHROUGH 3 - ANSWERED, WITH A COARSE CITATION
# ===============================================================
answers.walkthrough(pack, "C08")
""")

code(r"""
# ===============================================================
# 5.9 EVERY NUMBER IN EVERY PACKAGED ANSWER
# ===============================================================
claim_check = answers.claim_check(pack)
print(json.dumps({k: v for k, v in claim_check.items() if not k.endswith("detail")}, indent=2))
assert claim_check["unsupported_numerals"] == 0
assert claim_check["citations_not_retrieved"] == 0
print("\nEvery numeral asserted came from a retrieved passage, and every citation")
print("made was one the question actually retrieved.")
print("This is provenance. Section 4.8 showed what it does not cover.")
answers.pack_table(pack)
""")

md(r"""
## 5.10 The handoff: eight files, and two things deliberately absent

The service that consumes this does not re-run the notebook. It reads eight files:

| File | What the service does with it |
|---|---|
| `chunks.parquet` | Looks up passage text and citation for a retrieved row |
| `embeddings.npy` | Scores a question against every passage (float16) |
| `index.joblib` | The TF-IDF comparison retriever and keyword fallback |
| `model_card.json` | States what the system will not do |
| `evaluation.json` | Every number this notebook printed |
| `operating_policy.json` | tau and both refusal rules, read at startup |
| `corpus_manifest.json` | Proves every document may be redistributed |
| `cached_answers.json` | The 20 packaged answers |

**Not exported: the MiniLM weights.** The service loads `all-MiniLM-L6-v2` by name from its own
cache, so this repository never ships 90 MB of model.

**Not exported: any generative model.** There is none. The answers were written by a person from
retrieved passages.

The vectors are stored as **float16** - half the bytes of float32, and a genuine change to the
numbers. Section 5.12 is where we find out whether that change alters what comes back.
""")

code(r"""
# ===============================================================
# 5.10 ASSEMBLE THE EVIDENCE AND EXPORT
# ===============================================================
asked = handoff.reload_questions(questions, msha)
reload_baseline = {
    "questions": len(asked),
    "selection": "the evaluation set then the MSHA set, in file order, first 50",
    "baseline_top5": handoff.baseline_top5({"tfidf": tfidf, "minilm": minilm}, asked),
    "embedding_digest": handoff.vector_digest(minilm.vectors),
}
evidence = handoff.assemble_evidence(
    corpus_summary=summary,
    licence_scan=scan,
    chunk_sizes=sizes,
    truncation={mode: round(chunking.truncation_share(size_evidence, mode), 4)
                for mode in chunking.CONFIG_ORDER},
    citation_audit={
        "scope": config.CITATION_AUDIT_SCOPE,
        "scope_note": config.CITATION_AUDIT_NOTE,
        "labelled_paragraphs": structural["labelled_paragraphs"],
        "naive_citation_wrong": dict(zip(naive["Measure"], naive["Share"]))["Citation wrong"],
        "naive_citation_nonexistent": dict(zip(naive["Measure"], naive["Share"]))[
            "Citation names a paragraph that does not exist"],
        "stateful_structurally_invalid": structural["structurally_invalid"],
        "structural_check_is_a_self_check": structural["note"],
        "internal_cross_references": xref["cross_references"],
        "cross_references_resolved_stateful": xref["stateful_rate"],
        "cross_references_resolved_naive": xref["naive_rate"],
        "hand_audited": verification["citation_identical"],
    },
    leaderboard=leaderboard,
    per_bucket=retrieval.per_bucket(results),
    phrasing={
        "research_tfidf_hit1": measured["research_tfidf_hit1"],
        "technician_tfidf_hit1": measured["technician_tfidf_hit1"],
        "technician_minilm_hit1": measured["technician_minilm_hit1"],
        "note": "The first number was measured on questions generated from the "
                "passage text; the others on technician-phrased questions.",
    },
    gold_validation=validation,
    policy_sweep=sweep,
    policy_result=policy_result,
    duplicate={
        "similarity": similarity,
        "minilm": {
            "questions": 30,
            "cite_hit@1_before": duplicate_results[("Part 56 only", minilm.display)]["cite_hit@1"],
            "cite_hit@1_after": duplicate_results[("Part 56 + Part 57", minilm.display)]["cite_hit@1"],
            "text_hit@1_before": duplicate_results[("Part 56 only", minilm.display)]["text_hit@1"],
            "text_hit@1_after": duplicate_results[("Part 56 + Part 57", minilm.display)]["text_hit@1"],
            "right_text_wrong_rule@1_after": duplicate_results[
                ("Part 56 + Part 57", minilm.display)]["right_text_wrong_rule@1"],
        },
        "tfidf": {
            "questions": 30,
            "cite_hit@1_before": duplicate_results[("Part 56 only", tfidf.display)]["cite_hit@1"],
            "cite_hit@1_after": duplicate_results[("Part 56 + Part 57", tfidf.display)]["cite_hit@1"],
            "right_text_wrong_rule@1_after": duplicate_results[
                ("Part 56 + Part 57", tfidf.display)]["right_text_wrong_rule@1"],
        },
        "collateral": {"before": before, "after": after,
                       "corpus_growth": round(len(all_chunks) / len(chunks) - 1, 3)},
    },
    claim_check=claim_check,
    reload_check=reload_baseline,
)
model_card = handoff.build_model_card(evidence, chunks, manifest)
policy = handoff.build_policy(evidence)
exported = handoff.export(chunks, minilm.vectors, tfidf, evidence, model_card,
                          policy, handoff.build_manifest(manifest), pack)
exported
""")

md(r"""
## 5.11 Does the saved index still say the same thing?

An exported index is only useful if it behaves identically after being written to disk and read
back somewhere else. The check below **reloads from `artifacts/` and uses nothing from memory**:
the chunk table, the float16 vectors and the TF-IDF index all come off disk, the encoder is
loaded by name, and 50 questions are re-run through both retrievers.

The requirement is the **identical top-5 chunk ids**, plus a SHA-256 digest over the raw float16
bytes matching the one recorded at export. If a library version shifts and changes a similarity
in the fourth decimal place, this fails loudly instead of quietly shipping a different index.
""")

code(r"""
# ===============================================================
# 5.11 RELOAD IDENTITY
# ===============================================================
identity = handoff.verify(questions, msha)
print(json.dumps({k: v for k, v in identity.items() if k != "mismatches"}, indent=2))
assert identity["status"] == "identical"
""")

code(r"""
# ===============================================================
# 5.12 THE EXPORTED POLICY, AS THE SERVICE WILL READ IT
# ===============================================================
saved_policy = json.loads((config.ARTIFACT_DIR / "operating_policy.json").read_text())
print(json.dumps({key: saved_policy[key] for key in
                  ["refusal_threshold", "rules", "service_must", "boundary"]}, indent=2))
""")

code(r"""
# ===============================================================
# 5.13 WHAT THIS LAB ASKS A STUDENT TO CLONE
# ===============================================================
handoff.committed_size()
""")

md(r"""
### Stage 5 conclusion

Adding a near-identical regulation left the text retrieval almost untouched and destroyed the
citation - the one field a person cannot check by reading. The aggregate metric barely moved.
Three answers went end to end, one of them a refusal that a similarity score alone would never
have produced. Eight files were exported and every one of them reproduced its numbers after a
reload from disk.

### What this notebook did and did not build

**It built** a retrieval system over 13 vetted documents that finds the governing passage for
about eight questions in ten within its top five, carries a citation checked against the
regulation's own cross-references, and refuses 7 of 8 questions outside its corpus and 6 of 7
that point at a standard it does not hold - with 2 wrong refusals out of 45 answerable
questions.

**It did not build** anything that decides. The assistant retrieves and drafts. It never
authorizes work, never approves a lockout, never issues or releases a clearance, and never
answers from the model's own memory. Its worst realistic failure is the one stage 5 measured:
the right sentence carrying the wrong rule number, which reads as correct all the way to the
permit. That is why the citation audit, the refusal policy and the per-domain slice matter more
here than the next point of retrieval accuracy.
""")

notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

if __name__ == "__main__":
    nbf.validate(notebook)
    identifiers = [cell["metadata"]["id"] for cell in notebook["cells"]]
    assert len(identifiers) == len(set(identifiers)), "duplicate cell id"
    assert all(cell["metadata"].get("language") for cell in notebook["cells"]), \
        "missing language"
    with OUTPUT.open("w", encoding="utf-8") as handle:
        nbf.write(notebook, handle)
    markdown_cells = sum(1 for cell in notebook["cells"] if cell["cell_type"] == "markdown")
    code_cells = len(notebook["cells"]) - markdown_cells
    guides = sum(1 for cell in notebook["cells"]
                 if cell["cell_type"] == "markdown"
                 and cell["source"].startswith("### How to read this plot"))
    figures = sum(cell["source"].count(".show()") for cell in notebook["cells"]
                  if cell["cell_type"] == "code")
    print(f"Wrote {OUTPUT.name}: {len(notebook['cells'])} cells "
          f"({code_cells} code, {markdown_cells} markdown), "
          f"{figures} figures, {guides} reading guides")
