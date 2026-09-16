"""Build the undergraduate RAG walkthrough with genuine, replayable LLM answers."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import nbformat as nbf

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_DIR / "01_procedure_build.ipynb"
cells = []


def add(language: str, text: str) -> None:
    source = text.strip()
    identity = "rag-" + hashlib.sha256((language + source).encode()).hexdigest()[:12]
    constructor = nbf.v4.new_markdown_cell if language == "markdown" else nbf.v4.new_code_cell
    cells.append(constructor(source, id=identity, metadata={"id": identity, "language": language}))


def md(text: str) -> None:
    add("markdown", text)


def code(text: str) -> None:
    add("python", text)


md("""
# From a workplace question to an answer with a source
**ITAI 2372 | Module 5 | AI in Manufacturing and Industrial Operations**

A plant coordinator asks: **How long must we keep a canceled confined-space entry permit?**
The answer should come from the right document, not a chatbot's guess.

**Retrieval-augmented generation (RAG)** combines two jobs:
- **Retrieve:** find relevant passages in a document collection.
- **Generate:** give those passages and the question to an LLM to draft an answer.

| Stage | The data scientist's question |
|---|---|
| 1. Choose sources | Which documents can answer this kind of question? |
| 2. Prepare and index | How do we make the text searchable? |
| 3. Retrieve | Which passages match this question? |
| 4. Generate | What exactly does the LLM receive and return? |
| 5. Check | Is the answer supported, and can it say "not in these sources"? |

We use **three short public excerpts**, not the full library. They are a small classroom
example, not a complete compliance reference. The assistant never authorizes work or certifies safety.
""")
code("""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import json
import textwrap
import pandas as pd
import plotly.express as px
from IPython.display import display
from plotly.offline import init_notebook_mode
from transformers.utils.logging import disable_progress_bar
from raglab import config, index, teaching

disable_progress_bar()
init_notebook_mode(connected=False)
pd.set_option("display.max_colwidth", 100)
LIVE_GENERATION = False
print("Generation mode:", "LIVE" if LIVE_GENERATION else "captured real LLM responses; offline replay")
""")
md("""
**About running this notebook:** retrieval runs locally each time. By default, generation
replays actual recorded LLM responses for the exact question and retrieved passages.
These are **not hand-written answers**. New questions require `LIVE_GENERATION = True`, an
internet connection, and an existing GitHub Copilot sign-in. Live requests may consume your
Copilot allowance; they do not silently fall back to a saved answer.

# 1. Choose the sources
## 1.1 Start with a small, understandable library
We selected one paragraph from each of three US workplace-regulation sections, downloaded
as of **August 1, 2025**. The topics are permit records, inspection frequency, and operator
evaluation frequency. The wider project already extracted the text; no PDF parser is needed here.

This is a selected excerpt collection, not three complete regulations or a current legal opinion.
The source date and original section remain attached so a person can verify scope and current requirements.
""")
code("""
documents = teaching.load_sources()
display(documents[["source_title", "citation", "source_url"]].rename(columns={
    "source_title": "Source section", "citation": "Paragraph", "source_url": "Original source"}))
""")
md("""
## 1.2 Read the source before asking AI
A data scientist first checks that the answer really exists in the data.
Here is the full permit-retention excerpt. Read it before seeing the model's answer.
""")
code("""
permit_source = documents.iloc[0]
print(permit_source["citation"])
print(textwrap.fill(permit_source["text"], width=88))
""")
md("""
**Notice:** "at least 1 year" is a minimum, not exactly one year and not permission to destroy
every record after that time. The answer should preserve that qualifier and the type of permit.

# 2. Prepare and index the passages
## 2.1 Keep small pieces with their sources
A **chunk** is a passage we can retrieve separately. Large documents are usually divided
into chunks. These selected excerpts are already short, so **one paragraph becomes one chunk**.
We normalize whitespace but keep the wording and source citation.

We are not comparing chunking algorithms. The important decision is to keep enough context
to understand the answer and a source label to check it.
""")
code("""
chunks = teaching.prepare_chunks(documents)
display(chunks[["chunk_id", "citation", "text"]].rename(columns={
    "chunk_id": "Passage", "citation": "Source", "text": "Text preview"}))
print(f"{len(documents)} source excerpts -> {len(chunks)} searchable passages")
""")
md("""
## 2.2 Build the search index
An **embedding** is a numerical representation of text, designed to put related meanings
near each other. A pretrained embedding model turns each passage into numbers once.
Later, it turns the question into the same kind of numbers and compares them.

**We build an index; we do not train a new language model.** The embedding model finds text;
the separate generative LLM writes the answer. Those are different jobs.
""")
code("""
retriever = index.EmbedRetriever(chunks)
encoded_lengths = [len(retriever.model.tokenizer.encode(text)) for text in index.indexed_texts(chunks)]
assert max(encoded_lengths) <= retriever.model.max_seq_length
print(f"Index ready: {len(chunks)} passages encoded with {config.EMBEDDER_SHORT}.")
print("All three passages fit the model's input limit. No passage text was silently cut off.")
""")
md("""
# 3. Retrieve passages for the question
## 3.1 Search with the same question we started with
The index ranks passages by similarity to the question. Keep the best two for the LLM.
Similarity is **not** the probability that a passage contains the correct answer.
""")
code("""
question = teaching.CASES[0]["question"]
passages = teaching.retrieve(retriever, question)
print("QUESTION:", question)
ranked = pd.DataFrame(passages)
display(ranked[["citation", "similarity"]].rename(columns={"citation": "Retrieved source", "similarity": "Match score"}))
ranked["Topic"] = ranked["citation"].map(dict(zip(teaching.SOURCE_CITATIONS,
    ["Permit records", "Inspections", "Operator checks"])))
figure = px.bar(ranked.iloc[::-1], x="similarity", y="Topic", orientation="h", text_auto=".2f",
                title="Passage match scores", color_discrete_sequence=["#167D9A"])
figure.update_layout(template="plotly_white", height=300, xaxis_title="Similarity (not accuracy)",
                     yaxis_title=None, font_size=14, title_font_size=15)
figure.update_xaxes(range=[0, 1])
figure.show()
""")
md("""
**Read the chart:** a longer bar means a closer match in the embedding model's representation.
The permit passage should rank above the unrelated one. The score helps find candidates;
it does not prove the rule applies to the question.

## 3.2 Inspect exactly what was retrieved
Read the actual passages, not just their titles or scores. A wrong passage with a convincing
number can still produce a convincing wrong answer.
""")
code(r"""
for rank, passage in enumerate(passages, start=1):
    print(f"\nPASSAGE {rank}: {passage['citation']}")
    print(textwrap.fill(passage["text"], width=88))
""")
md("""
# 4. Generate an answer from those passages
## 4.1 Build the prompt
**Augment** means add useful context. We add the retrieved passages to the question and tell
the LLM to answer only from them, preserve qualifiers, cite its evidence, or say the answer
is missing. The document text is data, not permission to change those instructions.

Below is the exact instruction and message sent to the LLM. The JSON labels keep the question
and sources separate. No answer key or expected answer is sent.
""")
code(r"""
prompt = teaching.make_prompt(question, passages)
print("INSTRUCTION TO THE LLM:\n")
print(textwrap.fill(teaching.SYSTEM_PROMPT, width=88))
print("\nQUESTION AND RETRIEVED PASSAGES:\n")
print(prompt)
""")
md("""
## 4.2 Generate, then check the supporting quote
This is the **generation** part of RAG. The LLM writes an answer using the message above.
Our helper checks its response format and that its quotation appears in the cited retrieved
passage. That check catches invented quotes, but **does not prove the answer is correct**.
""")
code(r"""
generated = await teaching.answer(prompt, live=LIVE_GENERATION)
response = generated["response"]
print(generated["mode"], "| Model:", generated["model"])
if "captured_at" in generated:
    print("Recorded:", generated["captured_at"])
print("\nQUESTION:", question)
print("ANSWER:", response["answer"])
print("SOURCE:", response["citation"])
print("SUPPORTING QUOTE:", textwrap.fill(response["quote"], width=88))
""")
md("""
**Human check:** does the quote discuss the same kind of permit? Does the answer preserve
"at least"? Does the cited original source contain the quote? A valid citation is evidence
to inspect, not a guarantee of correctness.

Retrieval and generation solve different problems: retrieval finds candidate evidence;
generation turns it into a readable answer. Either step can fail.

# 5. Check the workflow
## 5.1 Try five small checks
Try the original question, a paraphrase, questions from the other excerpts, and one whose
answer is absent. These are **teaching examples selected by topic**, not a held-out benchmark
or a production accuracy estimate. The original question reuses the answer we just saw.

The automatic check looks for the expected source and time period, or a refusal. A person
must still check wording, relevance, qualifiers, and current applicability.
""")
code("""
example_results = [generated]
checks = []
for position, case in enumerate(teaching.CASES):
    if position == 0:
        result = generated
    else:
        retrieved = teaching.retrieve(retriever, case["question"])
        result = await teaching.answer(teaching.make_prompt(case["question"], retrieved), live=LIVE_GENERATION)
        example_results.append(result)
    answer = result["response"]
    if case["citation"] is None:
        passed = not answer["answerable"]
    else:
        passed = (answer["answerable"] and answer["citation"] == case["citation"]
                  and any(term in answer["answer"].lower() for term in case["terms"]))
    checks.append({"Example": case["name"], "Expected": case["expected"],
                   "LLM answer": answer["answer"], "Basic check": "Pass" if passed else "Review"})
display(pd.DataFrame(checks))
print(f"{sum(row['Basic check'] == 'Pass' for row in checks)} of {len(checks)} example checks passed.")
print("This is not an accuracy estimate. All answers still need source review.")
""")
md("""
## 5.2 When the answer is not there
The sources contain several time periods, but none is a rule about parts invoices.
The right behavior is to say the excerpts do not answer the question, not borrow a number
from an unrelated recordkeeping rule. A high similarity score alone cannot make that decision.
""")
code("""
missing = teaching.CASES[-1]
print("QUESTION:", missing["question"])
print("ANSWER:", example_results[-1]["response"]["answer"])
print("NEXT STEP: obtain the applicable records policy and ask a qualified person to check it.")
""")
md("""
## 5.3 What would we hand to an application team?
- The approved document collection, source dates, and citations.
- The chunking rule, embedding model, and retrieval settings.
- The instruction given to the LLM and a clear human-review boundary.
- Test questions with expected answers, including missing-answer cases.
- A visible distinction between live generation and recorded responses.

The current app still uses the **larger corpus and older hand-written answer pack**.
This teaching notebook is a separate, smaller RAG path; it does not replace the app's artifacts.
The app demo will be reviewed after the notebook.

## The complete workflow
**Choose sources -> prepare passages -> build an index -> retrieve -> generate -> check.**

RAG is not teaching the LLM new facts by retraining it. It is supplying relevant evidence
at answer time. A data scientist must still check what was retrieved, what was written,
and what happens when the evidence is missing.
""")


def build() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    })
    if OUTPUT.exists():
        previous = nbf.read(OUTPUT, as_version=4)
        saved = {(cell.cell_type, cell.source): cell for cell in previous.cells}
        for position, cell in enumerate(notebook.cells):
            if (cell.cell_type, cell.source) in saved:
                notebook.cells[position] = saved[(cell.cell_type, cell.source)]
    nbf.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, "notebook cell", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    return notebook


if __name__ == "__main__":
    notebook = build()
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT.name}: {len(notebook.cells)} cells; "
          f"{sum(cell.cell_type == 'code' for cell in notebook.cells)} code cells")