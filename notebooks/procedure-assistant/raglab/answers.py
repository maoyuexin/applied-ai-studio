"""The packaged answers, and the check that asks whether they are grounded.

Twenty questions are shipped with a written answer: sixteen answered and four
refused. Every answer here was drafted **from the retrieved passages only**.
That is the whole discipline of a grounded assistant, and it is worth being
precise about what it does and does not buy you.

**What it buys.** The reader can check the work. Each answer carries the
citations of the passages it was written from, and the service shows those
passages beside it. Nothing is asserted from a model's memory of what OSHA
probably says.

**What it does not buy.** The unsupported-claim check below verifies that every
numeral an answer asserts appears in the passages that were retrieved for it.
That catches **invention** - a torque figure the corpus never contained. It
cannot catch **misattribution** - a number copied accurately out of a passage
that was retrieved but does not govern the question. Section 4 of the notebook
demonstrates both cases on the same question, because "zero unsupported claims"
reads like "zero hallucinations" and is not the same statement.

The assistant retrieves and drafts. It never authorizes work, never approves a
lockout, and never answers from the model's own memory.
"""

from __future__ import annotations

import datetime
import re

import pandas as pd
import plotly.graph_objects as go

from . import config, evaluate

# ---------------------------------------------------------------------------
# The written answers
# ---------------------------------------------------------------------------

PACK_QIDS = [
    "A01", "A02", "A04", "A08", "A12", "A13", "A17", "A19", "A21", "A23",
    "B05", "C03", "C04", "C08", "C09", "C10", "E01", "E04", "D01", "D02",
]

ANSWERED = "answered"
REFUSED_LOW = "refused_low_confidence"
REFUSED_IBR = "refused_incorporated_by_reference"

WRITTEN: dict[str, dict] = {}


def _write(qid: str, status: str, answer: str, citations: list[str],
           reason: str | None = None, consult: str | None = None,
           note: str | None = None) -> None:
    WRITTEN[qid] = dict(status=status, answer=" ".join(answer.split()),
                        citations=citations, refusal_reason=reason,
                        consult=consult, teaching_note=note)


_write("A01", ANSWERED, """
    Each lockout or tagout device must be removed by the employee who applied it.
    Before removal, the work area is inspected so that machine components are
    operationally intact and nonessential items have been removed, and the area is
    checked to be sure all employees have been safely positioned or removed. After
    the devices come off and before the machine is started, affected employees must
    be notified that the devices have been removed. Where the employee who applied
    the device is not available, it may be removed under the direction of the
    employer only under a documented procedure that provides equivalent safety.
    """, ["OSHA 3120 p. 15", "29 CFR 1910.147(e)(2)(i)"])

_write("A02", ANSWERED, """
    The energy control procedure must be inspected at least once a year. The
    inspector has to be an authorized employee other than the ones using the
    procedure being inspected, and the inspection has to correct any deviations or
    inadequacies it finds. The employer must also certify that the inspection
    happened, recording the machine or equipment the procedure was used on, the date
    of the inspection, the employees included, and the person who performed it.
    """, ["OSHA 3120 p. 23", "29 CFR 1910.147(c)(5)(iii)"],
    note="The plain-language booklet was retrieved first and the regulation itself "
         "came back at rank 3. The friendlier passage is the weaker citation: a "
         "reader who has to prove compliance needs 29 CFR 1910.147(c)(6)(i), not "
         "an OSHA booklet page.")

_write("A04", ANSWERED, """
    The procedure must be documented, and it must give employees a statement of how
    to use it, the specific procedural steps for shutting down, isolating, blocking
    and securing machines to control hazardous energy, the specific steps for the
    safe placement, removal and transfer of lockout or tagout devices and who is
    responsible for them, and the specific requirements for testing machines to
    verify that those devices and other energy-control measures are effective.
    """, ["OSHA 3120 p. 13"],
    note="Every retrieved passage came from the plain-language booklet, so the "
         "answer is right and its citation is second-hand. The governing text is "
         "29 CFR 1910.147(c)(4)(ii), which did not come back in the top four. "
         "Scoring calls this a retrieval miss even though the reader is not "
         "misled.")

_write("A08", ANSWERED, """
    Each canceled entry permit must be retained for at least one year, so that the
    permit-required confined space program review can be carried out. The review
    itself uses those retained permits and has to happen within a year after each
    entry, and any problems met during an entry are noted on the permit so the
    program can be revised.
    """, ["29 CFR 1910.146(e)(5)(ii)", "29 CFR 1910.146(d)(13)"],
    note="The sentence that answers the question is paragraph (e)(6), and it was "
         "packed into a chunk whose leading citation is (e)(5)(ii). A chunk-level "
         "citation can be one paragraph coarse, which is why the service must "
         "display the whole passage and not just its label.")

_write("A12", ANSWERED, """
    A fire watch is required whenever welding or cutting is done in a location where
    other than a minor fire might develop. The rule lists the conditions: appreciable
    combustible material in the building construction or contents closer than 35 feet
    to the point of operation; appreciable combustibles more than 35 feet away that
    are easily ignited by sparks; wall or floor openings within a 35-foot radius that
    expose combustible material in adjacent areas, including concealed spaces; and
    combustible materials on the opposite side of metal partitions, walls, ceilings
    or roofs that are likely to be ignited by conduction or radiation.
    """, ["29 CFR 1910.252(a)(2)(iii)(A)"])

_write("A13", ANSWERED, """
    Fire watchers must have fire extinguishing equipment readily available and be
    trained in its use, be familiar with the facilities for sounding an alarm, and
    watch for fires in all exposed areas. They are to try to extinguish a fire only
    when it is obviously within the capacity of the equipment available, and
    otherwise to sound the alarm. The fire watch must be maintained for at least a
    half hour after the welding or cutting is finished, to catch smouldering fires.
    """, ["29 CFR 1910.252(a)(2)(iii)(B)"])

_write("A17", ANSWERED, """
    When working near exposed energized conductors or circuit parts, each employee
    must use insulated tools or handling equipment if the tools or handling equipment
    might make contact with those conductors or parts. If the insulating capability
    could be damaged, the insulating material has to be protected. Fuse handling
    equipment insulated for the circuit voltage must be used to remove or install
    fuses when the fuse terminals are energized, and ropes and handlines used near
    exposed energized parts must be nonconductive.
    """, ["29 CFR 1910.335(a)(2)(i)"])

_write("A19", ANSWERED, """
    Yes. One or more methods of machine guarding must be provided to protect the
    operator and other employees in the machine area from hazards such as the point
    of operation, ingoing nip points, rotating parts, and flying chips and sparks.
    The examples the rule gives are barrier guards, two-hand tripping devices and
    electronic safety devices. Guards must be affixed to the machine where possible
    and secured elsewhere if attachment is not possible, and the guard must not
    itself create an accident hazard.
    """, ["29 CFR 1910.212(a)(1)"])

_write("A21", ANSWERED, """
    No. The facility program states that an employee must not work under the
    protection of another employee's personal lock or tag, and that personal lockout
    or tagout must not be used when the protection requires a clearance. Personal
    locks and tags must not be placed on the energy isolation devices that establish
    the limits of a clearance. For a clearance, an authorized employee affixes a
    personal lock to the clearance lockbox after obtaining permission from the
    appropriate job supervisor, before work begins.
    """, ["USBR FIST 1-1 p. 38", "USBR FIST 1-1 p. 70"])

_write("A23", ANSWERED, """
    The manual's troubleshooting entry for this symptom points at the starting
    circuit and the dc supply: replace a defective dc circuit breaker, and check the
    starting circuit wiring for a loose electrical connection or a break, replacing
    damaged wires and tightening loose connections. The operator checks that come
    before that are the batteries - inspect them for cracked or broken cases,
    corrosion on the terminal posts, damaged or frayed cables and loose connections,
    and check the electrolyte level.
    """, ["TM 9-6115-464-12 p. 111", "TM 9-6115-464-12 p. 76"],
    note="The manual gives symptom-based malfunction tables, not numeric fault "
         "codes. No public corpus contains OEM fault codes, which is exactly what "
         "question D01 asks for and is refused.")

_write("B05", ANSWERED, """
    The facility program says each personal lock or tag must be removed by the
    authorized employee who placed it, and each clearance released by the authorized
    employee who holds it. When that employee is not available, the removal is done
    by their supervisor in consultation with the operations supervisor, documented on
    the Release Under Abnormal Conditions form. The supervisor must verify that the
    employee who placed the lock is not at the facility, make reasonable efforts to
    inform them that it will be removed, take responsibility for the lock, authorize
    and direct its removal, and inform the employee on their return, before they
    resume work, that the lock or clearance has been removed.
    """, ["USBR FIST 1-1 p. 35"],
    note="This question asks for two things - the regulation and the site "
         "procedure - and all four retrieved passages came from the site procedure. "
         "The answer is correct and half the question is unanswered. Coverage, not "
         "hit rate, is the metric that sees this.")

_write("C03", ANSWERED, """
    35 feet. A fire watch is required when appreciable combustible material in the
    building construction or contents is closer than 35 feet to the point of
    operation. It is also required when appreciable combustibles more than 35 feet
    away are easily ignited by sparks, and when wall or floor openings within a
    35-foot radius expose combustible material in adjacent areas.
    """, ["29 CFR 1910.252(a)(2)(iii)(A)"])

_write("C04", ANSWERED, """
    A minimum of 20 feet. Oxygen cylinders in storage must be separated from
    fuel-gas cylinders or combustible materials, especially oil or grease, by a
    minimum distance of 20 feet, or by a noncombustible barrier at least 5 feet high
    having a fire-resistance rating of at least one-half hour. Inside buildings,
    cylinders must also be stored at least 20 feet from highly combustible materials
    such as oil or excelsior.
    """, ["29 CFR 1910.253(b)(4)(i)", "29 CFR 1910.253(b)(2)(ii)"])

_write("C08", ANSWERED, """
    At least 1 year. The employer must retain each canceled entry permit for at least
    1 year so that the permit-required confined space program can be reviewed.
    """, ["29 CFR 1910.146(e)(5)(ii)"])

_write("C09", ANSWERED, """
    35 lb-ft. The engine specification table lists the exhaust manifold mounting nuts
    at 35 lb-ft; the intake manifold mounting nuts are also 35 lb-ft. The installation
    procedure for the exhaust manifold gives the same figure.
    """, ["TM 9-6115-464-12 p. 28", "TM 9-6115-464-12 p. 182"])

_write("C10", ANSWERED, """
    The overspeed trip is set at 120 to 122.5 percent of continuous engine speed,
    which is 2400 to 2450 rpm. The trip is a centrifugal type with a manual reset.
    """, ["TM 9-6115-464-12 p. 28"])

_write("E01", REFUSED_IBR, """
    This corpus cannot give you a pressure rating for forging machine air piping. The
    rule does not contain one: air piping on air-lift hammers must conform to the
    specifications of ANSI B31.1.0-1967, Power Piping, which the regulation
    incorporates by reference rather than reproducing. You must consult ANSI
    B31.1.0-1967 itself. A qualified person should confirm which edition your
    facility is held to.
    """, ["29 CFR 1910.218(e)(1)(iii)"],
    reason="The governing paragraph names a consensus standard that is not in the corpus.",
    consult="ANSI B31.1.0-1967, Power Piping",
    note="DISCUSSION BEAT. The top-ranked passage, 29 CFR 1910.253(d)(1)(ii)(B), is "
         "subtly wrong: it is welding gas manifold piping, not forging machine air "
         "piping, and it carries a confident-looking number - a working pressure of "
         "250 psi. An ungrounded model answers '250 psi'. The passage that actually "
         "governs is at rank 3.")

_write("E04", REFUSED_IBR, """
    This corpus cannot give you the guard design specifications. The rule states that
    abrasive wheel machinery guards must meet the design specifications of the
    American National Standard Safety Code for the Use, Care, and Protection of
    Abrasive Wheels, ANSI B7.1-1970, which is incorporated by reference and is not
    reproduced in the regulation. You must consult ANSI B7.1-1970. The requirement
    does not apply to natural sandstone wheels, or to metal, wooden, cloth or paper
    discs having a layer of abrasive on the surface.
    """, ["29 CFR 1910.215(b)(12)", "29 CFR 1910.215(a)(5)"],
    reason="The governing paragraph names a consensus standard that is not in the corpus.",
    consult="ANSI B7.1-1970")

_write("D01", REFUSED_LOW, """
    I cannot answer this from the corpus. Nothing in the loaded documents defines
    manufacturer fault or error codes. The corpus holds federal safety regulation, a
    facility hazardous energy control program, a government generator set manual, and
    OSHA plain-language booklets. Consult the controller vendor's documentation or
    your site's PLC program documentation.
    """, [],
    reason="Best retrieval score below the refusal threshold and no passage on topic.",
    consult="PLC vendor documentation")

_write("D02", REFUSED_LOW, """
    I cannot answer this from the corpus. It contains no Caterpillar service
    literature. Consult the Caterpillar service manual for that engine.
    """, [],
    reason="Best retrieval score below the refusal threshold and no passage on topic.",
    consult="Caterpillar 3512B service manual")


# ---------------------------------------------------------------------------
# Building the pack against the live index
# ---------------------------------------------------------------------------

def build_pack(retriever, questions: pd.DataFrame,
               top_k: int = config.TOP_K_SHOWN) -> dict:
    """Assemble the answer pack from the index that is loaded right now.

    The written prose is fixed; the retrieved context is not. It is recomputed
    against the current index every time, and the refusal decision is taken by
    the deployed policy rather than copied from the file. If a rebuild changed
    what comes back, or moved a question across the threshold, this raises
    instead of shipping an answer pack that quietly disagrees with the model
    the service will load.
    """
    indexed = questions.set_index("qid")
    signals = evaluate.policy_signals(
        retriever, questions[questions["qid"].isin(PACK_QIDS)])
    decision = dict(zip(signals["qid"], evaluate.refusal_reason(signals)))

    records = []
    for qid in PACK_QIDS:
        row = indexed.loc[qid]
        written = WRITTEN[qid]
        hits = retriever.search(row["question"], top_k)
        retrieved = []
        for rank, (position, score) in enumerate(hits, 1):
            chunk = retriever.chunks.iloc[position]
            retrieved.append(dict(
                rank=rank, citation=chunk["citation"],
                citations=list(chunk["citations"]), score=round(float(score), 4),
                source=chunk["source"], text=chunk["text"]))

        policy = decision[qid]
        refused = written["status"] != ANSWERED
        if refused != (policy != "answered"):
            raise ValueError(
                f"{qid}: the written status is {written['status']!r} but the "
                f"deployed policy says {policy!r}. Re-draft the answer or "
                "re-examine the policy; do not ship both.")

        records.append(dict(
            qid=qid, bucket=row["bucket"], question=row["question"],
            gold_citations=[g for g in str(row["gold_citations"]).split("|") if g],
            top_score=round(float(hits[0][1]), 4),
            status=written["status"], answer=written["answer"],
            citations=written["citations"],
            refusal_reason=written["refusal_reason"],
            consult=written["consult"], teaching_note=written["teaching_note"],
            retrieved=retrieved))

    return dict(
        schema_version="1.0",
        generated=datetime.date.today().isoformat(),
        corpus=config.CORPUS_ID,
        index=dict(
            corpus=config.CORPUS_ID,
            chunking=f"token-budget {config.TOKEN_BUDGET} "
                     f"(MiniLM {config.MODEL_TOKEN_WINDOW} window)",
            embedder=config.EMBEDDER, top_k=top_k,
            refusal_threshold=config.REFUSAL_TAU,
            refusal_rules=list(config.REFUSAL_RULES)),
        boundary=config.BOUNDARY,
        answers=records)


# ---------------------------------------------------------------------------
# The unsupported-claim check
# ---------------------------------------------------------------------------

CITATION = re.compile(
    r"(?:\d+\s+CFR\s+\d+\.\d+[A-Za-z]?(?:\s+App\.\s+[A-Z])?(?:\([A-Za-z0-9]{1,6}\))*"
    r"|TM\s+9-6115-464-12(?:\s+p\.\s*\d+)?"
    r"|USBR\s+FIST\s+\d+-\d+(?:\s+p\.\s*\d+)?"
    r"|OSHA\s+\d{4}(?:\s+p\.\s*\d+)?"
    r"|ANSI\s+[A-Z]?\d[\dA-Za-z\.\-]*"
    r"|NFPA\s+(?:No\.\s*)?\d[\dA-Za-z\.\-]*"
    r"|§\s*\d+\.\d+(?:\([A-Za-z0-9]{1,6}\))*)")
NUMERAL = re.compile(r"\d+(?:\.\d+)?")

# Numbers a document may spell out rather than print. "at least once a year"
# supports "1 year"; nothing here lets a number in that the passage does not
# express one way or the other.
SPELLED = {"1": ["one", "a year", "annual", "once a year"], "2": ["two"],
           "3": ["three"], "0.5": ["half"]}


def numerals(text: str) -> list[str]:
    return [n.lstrip("0") or "0" for n in NUMERAL.findall(text)]


def check_answer(answer: dict) -> list[dict]:
    """Every numeral the answer asserts must appear in what it retrieved.

    Citation strings are removed first - ``1910.147(e)(3)`` is metadata, not a
    claim about the world - and numerals the question itself supplied are
    allowed through.
    """
    body = CITATION.sub(" ", answer["answer"])
    context = " ".join(passage["text"] for passage in answer["retrieved"])
    supported = set(numerals(context)) | set(numerals(answer["question"]))
    violations = []
    for numeral in numerals(body):
        if numeral in supported:
            continue
        if any(word in context.lower() for word in SPELLED.get(numeral, [])):
            continue
        position = body.find(numeral)
        violations.append(dict(
            qid=answer["qid"], numeral=numeral,
            snippet="..." + body[max(0, position - 70):position + 45].strip() + "..."))
    return violations


def check_citations(answer: dict) -> list[dict]:
    """Every citation an answer makes must be one it actually retrieved."""
    retrieved: set[str] = set()
    for passage in answer["retrieved"]:
        retrieved.update(passage.get("citations", [passage["citation"]]))
    return [dict(qid=answer["qid"], citation=citation)
            for citation in answer["citations"] if citation not in retrieved]


def claim_check(pack: dict) -> dict:
    """Run both checks over the whole pack."""
    unsupported, uncited = [], []
    for answer in pack["answers"]:
        unsupported += check_answer(answer)
        uncited += check_citations(answer)
    return {
        "answers_checked": len(pack["answers"]),
        "refusals": sum(1 for a in pack["answers"] if a["status"] != ANSWERED),
        "numerals_checked": sum(
            len(numerals(CITATION.sub(" ", a["answer"]))) for a in pack["answers"]),
        "unsupported_numerals": len(unsupported),
        "unsupported_detail": unsupported,
        "citations_not_retrieved": len(uncited),
        "citation_detail": uncited,
    }


# ---------------------------------------------------------------------------
# What the check cannot see
# ---------------------------------------------------------------------------

INVENTED = (
    "The air piping on a forging machine must be rated for a working pressure "
    "of 42 lb-ft and inspected annually.")
MISATTRIBUTED = (
    "The air piping on a forging machine must be rated for a working pressure "
    "of 250 psi.")


def claim_check_demonstration(pack: dict, qid: str = "E01") -> pd.DataFrame:
    """Two wrong answers to one question: one caught, one not.

    Both are drafted against the *same* retrieved context. The first asserts a
    number that is nowhere in it, and the check catches it. The second copies a
    number accurately out of the top-ranked passage - which is welding gas
    manifold piping, not forging machine air piping - and the check passes it,
    because the number really is in the context. A numeral check tests
    provenance, not relevance.
    """
    answer = next(a for a in pack["answers"] if a["qid"] == qid)
    rows = []
    for label, draft, verdict in (
        ("Refusal (what the system ships)", answer["answer"],
         "correct - names the standard the reader must obtain"),
        ("Invented number", INVENTED,
         "wrong - 42 lb-ft appears nowhere in the corpus"),
        ("Misattributed number", MISATTRIBUTED,
         "wrong - 250 psi is real, but it governs welding gas manifold piping"),
    ):
        probe = dict(answer, answer=draft)
        violations = check_answer(probe)
        rows.append({
            "Draft answer": label,
            "What it says": draft if label != "Refusal (what the system ships)"
                            else answer["answer"][:96] + "...",
            "Unsupported numerals found": len(violations),
            "Check verdict": "FLAGGED" if violations else "passes",
            "Actually": verdict,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def walkthrough(pack: dict, qid: str, width: int = 420) -> None:
    """Print one packaged question the way the service presents it."""
    answer = next(a for a in pack["answers"] if a["qid"] == qid)
    bar = "=" * 96
    print(bar)
    print(f"{answer['qid']}  [bucket {answer['bucket']}]  {answer['question']}")
    print(f"top-1 similarity {answer['top_score']:.4f}   "
          f"refusal threshold tau = {config.REFUSAL_TAU}")
    print(bar)
    print("RETRIEVED PASSAGES (what a person is shown, and must read)")
    for passage in answer["retrieved"]:
        text = passage["text"]
        text = text if len(text) <= width else text[:width].rstrip() + "..."
        print(f"\n  rank {passage['rank']}  score {passage['score']:.4f}  "
              f"[{passage['citation']}]  {passage['source']}")
        for line in _wrap(text, 88):
            print(f"      {line}")
    print(f"\n{'-' * 96}")
    print(f"STATUS: {answer['status']}")
    if answer["refusal_reason"]:
        print(f"REASON: {answer['refusal_reason']}")
    if answer["consult"]:
        print(f"CONSULT: {answer['consult']}")
    print("\nDRAFTED ANSWER")
    for line in _wrap(answer["answer"], 88):
        print(f"  {line}")
    print(f"\nCITATIONS THE READER MUST VERIFY: {', '.join(answer['citations']) or 'none'}")
    print(f"GOLD (evaluation set): {', '.join(answer['gold_citations']) or 'none - refusal expected'}")
    if answer["teaching_note"]:
        print("\nNOTE")
        for line in _wrap(answer["teaching_note"], 88):
            print(f"  {line}")
    print(f"\n{config.BOUNDARY}")
    print(bar)


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(text, width) or [""]


def pack_table(pack: dict) -> pd.DataFrame:
    return pd.DataFrame([{
        "qid": a["qid"], "Bucket": a["bucket"], "Question": a["question"],
        "Top-1 score": a["top_score"], "Status": a["status"],
        "Citations": len(a["citations"]),
        "Words in the answer": len(a["answer"].split()),
    } for a in pack["answers"]])


def claim_check_figure(pack: dict) -> go.Figure:
    """Numerals asserted, numerals supported, and the one class of error left."""
    answered = [a for a in pack["answers"] if a["status"] == ANSWERED]
    asserted = [len(numerals(CITATION.sub(" ", a["answer"]))) for a in answered]
    flagged = [len(check_answer(a)) for a in answered]
    labels = [a["qid"] for a in answered]
    figure = go.Figure()
    figure.add_bar(x=labels, y=asserted, name="Numerals asserted and supported",
                   marker_color=config.COLOR_PRIMARY,
                   hovertemplate="%{x}<br>%{y} numerals, all present in the "
                                 "retrieved passages<extra></extra>")
    figure.add_bar(x=labels, y=flagged, name="Numerals not found in the context",
                   marker_color=config.COLOR_ALERT,
                   hovertemplate="%{x}<br>%{y} unsupported<extra></extra>")
    figure.update_layout(barmode="overlay", legend=dict(orientation="h", y=-0.22))
    figure.update_yaxes(title="Numerals in the drafted answer", rangemode="tozero")
    figure.update_xaxes(title="Packaged question")
    figure.add_annotation(
        x=0.5, xref="paper", y=0.92, yref="paper", showarrow=False,
        text="Zero unsupported numerals. That is provenance, not correctness - "
             "see the misattribution case in section 4.",
        font=dict(size=12, color=config.COLOR_DARK))
    return config.layout(
        figure, "Every number in every drafted answer came from a retrieved passage",
        height=440)
