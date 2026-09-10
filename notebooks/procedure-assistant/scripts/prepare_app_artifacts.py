"""Run the whole procedure-assistant workflow headlessly and export the artifacts.

Same corpus, same frozen decisions and same order as the notebook - committed
chunks -> both retrievers -> the 60-question evaluation -> the two-rule refusal
policy at tau = 0.48 -> the duplicate-corpus experiment -> the packaged answers
-> export -> reload verification - so ``npm run prepare:procedures`` reproduces
exactly the files the notebook commits evidence for.

Nothing here downloads anything. The corpus is committed, the chunk table is
committed, and the sentence encoder is read from the local model cache.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from raglab import (answers, chunking, citations, config, corpus,  # noqa: E402
                    evaluate, handoff, index, retrieval)


def main() -> None:
    started = time.perf_counter()

    print("Loading the committed corpus tables...")
    manifest = corpus.load_manifest()
    paragraphs = pd.read_parquet(config.PARAGRAPHS_PARQUET)
    open_paths = citations.load_open_paths()
    size_evidence = pd.read_parquet(config.CHUNK_SIZE_PARQUET)
    all_chunks = chunking.load_chunks(include_duplicate=True)
    chunks = all_chunks[all_chunks["in_base_corpus"]].reset_index(drop=True)
    questions = evaluate.load_eval()
    msha = evaluate.load_msha_eval()
    print(f"  {len(manifest)} documents, {len(paragraphs):,} paragraphs, "
          f"{len(chunks):,} chunks in the base corpus "
          f"({len(all_chunks) - len(chunks):,} more in the opt-in duplicate)")

    print("Verifying the licence gate on the equipment manual...")
    licence_scan = corpus.distribution_statement_scan(
        corpus.raw_text("TM 9-6115-464-12"))
    print(f"  {licence_scan['verdict']}")
    if not licence_scan["statement_a_present"] or licence_scan["restrictive_statement_present"]:
        raise SystemExit("The equipment manual no longer passes the licence gate.")

    print("Auditing citations against the regulation's own cross-references...")
    hierarchy = citations.hierarchical(paragraphs)
    naive = citations.naive_versus_stateful(hierarchy, open_paths)
    structural = citations.structural_check(hierarchy, open_paths)
    xref = citations.cross_reference_check(hierarchy, open_paths)
    audit = citations.audit_sample()
    print(f"  naive citations wrong "
          f"{naive.loc[naive['Measure'] == 'Citation wrong', 'Share'].iloc[0]}; "
          f"stateful structurally invalid {structural['structurally_invalid']}; "
          f"cross-references resolve {xref['stateful_rate']:.1%} vs "
          f"{xref['naive_rate']:.1%} naive")

    print("Building both retrievers on the base corpus...")
    minilm = index.EmbedRetriever(chunks)
    tfidf = index.TfidfRetriever(chunks)
    print(f"  MiniLM {minilm.build_seconds:.1f}s, TF-IDF {tfidf.build_seconds:.1f}s")

    print("Scoring the 60-question evaluation set...")
    results = {retriever.display: retrieval.evaluate(retriever, questions)
               for retriever in (tfidf, minilm)}
    leaderboard = retrieval.leaderboard(results)
    per_bucket = retrieval.per_bucket(results)
    gold_validation = evaluate.validate_gold(questions, chunks)
    for row in leaderboard.to_dict("records"):
        print(f"  {row['Retriever']:<28} hit@1 {row['hit@1']:.3f}  "
              f"hit@5 {row['hit@5']:.3f}  sec@1 {row['sec@1']:.3f}")
    if gold_validation["missing_from_the_chunk_table"]:
        raise SystemExit("A gold citation does not name a chunk that exists.")

    print(f"Applying the refusal policy at tau = {config.REFUSAL_TAU}...")
    signals = evaluate.policy_signals(minilm, questions)
    sweep = evaluate.policy_sweep(signals)
    policy_result = evaluate.policy_result(signals)
    print(f"  correct refusal D {policy_result['correct_refusal_D']:.1%}, "
          f"E {policy_result['correct_refusal_E']:.1%}, "
          f"false refusal {policy_result['false_refusal_rate']:.1%}")

    print("Adding 30 CFR 57 beside 30 CFR 56 and re-measuring...")
    similarity = evaluate.duplicate_similarity(paragraphs)
    duplicate_minilm = minilm.extend(
        all_chunks[~all_chunks["in_base_corpus"]].reset_index(drop=True))
    duplicate_tfidf = index.TfidfRetriever(all_chunks)
    duplicate = {
        "similarity": similarity,
        "minilm": _pair(evaluate.duplicate_measure(minilm, msha),
                        evaluate.duplicate_measure(duplicate_minilm, msha)),
        "tfidf": _pair(evaluate.duplicate_measure(tfidf, msha),
                       evaluate.duplicate_measure(duplicate_tfidf, msha)),
        "collateral": {
            "main_hit@5_before": retrieval.overall(results[minilm.display])["hit@5"],
            "main_hit@5_after": retrieval.overall(
                retrieval.evaluate(duplicate_minilm, questions))["hit@5"],
            "corpus_growth": round(len(all_chunks) / len(chunks) - 1, 3),
        },
    }
    print(f"  {similarity['shared_section_numbers']} shared section numbers, "
          f"{similarity['byte_identical']} byte-identical, mean similarity "
          f"{similarity['mean_similarity']}")
    print(f"  MiniLM citation hit@1 {duplicate['minilm']['cite_hit@1_before']} -> "
          f"{duplicate['minilm']['cite_hit@1_after']}; TF-IDF "
          f"{duplicate['tfidf']['cite_hit@1_before']} -> "
          f"{duplicate['tfidf']['cite_hit@1_after']}")

    print("Assembling the packaged answers and checking every number in them...")
    pack = answers.build_pack(minilm, questions)
    claim_check = answers.claim_check(pack)
    print(f"  {claim_check['answers_checked']} answers "
          f"({claim_check['refusals']} refusals), "
          f"{claim_check['numerals_checked']} numerals asserted, "
          f"{claim_check['unsupported_numerals']} unsupported, "
          f"{claim_check['citations_not_retrieved']} citations not retrieved")
    if claim_check["unsupported_numerals"] or claim_check["citations_not_retrieved"]:
        raise SystemExit("A packaged answer is not grounded in what it retrieved.")

    print("Exporting...")
    asked = handoff.reload_questions(questions, msha)
    baseline = handoff.baseline_top5({"tfidf": tfidf, "minilm": minilm}, asked)
    reload_check = {
        "questions": len(asked),
        "selection": "the evaluation set then the MSHA set, in file order, first 50",
        "baseline_top5": baseline,
        "embedding_digest": handoff.vector_digest(minilm.vectors),
    }
    evidence = handoff.assemble_evidence(
        corpus_summary=corpus.summary(manifest),
        licence_scan=licence_scan,
        chunk_sizes=chunking.size_table(size_evidence),
        truncation={mode: round(chunking.truncation_share(size_evidence, mode), 4)
                    for mode in chunking.CONFIG_ORDER},
        citation_audit=_citation_audit(naive, structural, xref, audit),
        leaderboard=leaderboard, per_bucket=per_bucket,
        phrasing=_phrasing(results),
        gold_validation=gold_validation,
        policy_sweep=sweep, policy_result=policy_result,
        duplicate=duplicate, claim_check=claim_check,
        reload_check=reload_check,
    )
    model_card = handoff.build_model_card(evidence, chunks, manifest)
    policy = handoff.build_policy(evidence)
    exported = handoff.export(
        chunks, minilm.vectors, tfidf, evidence, model_card, policy,
        handoff.build_manifest(manifest), pack)
    for row in exported.to_dict("records"):
        print(f"  {row['Artifact']:<22} {row['Size']:>10}")

    print("Reloading the artifacts in this process and re-running 50 questions...")
    identity = handoff.verify(questions, msha)
    print(f"  {identity['status']}: TF-IDF {identity['identical_top5_tfidf']}, "
          f"MiniLM {identity['identical_top5_minilm']}")

    print(handoff.committed_size().to_string(index=False))
    print(f"\nReady in {time.perf_counter() - started:.1f}s.")


def _pair(before: dict, after: dict) -> dict:
    keys = ["text_hit@1", "cite_hit@1", "text_hit@5", "cite_hit@5",
            "right_text_wrong_rule@1"]
    payload = {"questions": before["questions"]}
    for key in keys:
        payload[f"{key}_before"] = before[key]
        payload[f"{key}_after"] = after[key]
    return payload


def _citation_audit(naive: pd.DataFrame, structural: dict, xref: dict,
                    audit: pd.DataFrame) -> dict:
    share = dict(zip(naive["Measure"], naive["Share"]))
    return {
        "scope": config.CITATION_AUDIT_SCOPE,
        "scope_note": config.CITATION_AUDIT_NOTE,
        "labelled_paragraphs": structural["labelled_paragraphs"],
        "naive_citation_wrong": share["Citation wrong"],
        "naive_citation_nonexistent":
            share["Citation names a paragraph that does not exist"],
        "stateful_structurally_invalid": structural["structurally_invalid"],
        "structural_check_is_a_self_check": structural["note"],
        "internal_cross_references": xref["cross_references"],
        "cross_references_resolved_stateful": xref["stateful_rate"],
        "cross_references_resolved_naive": xref["naive_rate"],
        "hand_audited": f"{len(audit)}/{len(audit)}",
    }


def _phrasing(results: dict) -> dict:
    tfidf = retrieval.overall(results["TF-IDF word counts"])
    minilm = retrieval.overall(results["MiniLM sentence embeddings"])
    return {
        "research_tfidf_hit1": config.SPIKE["research_tfidf_hit1_claim"],
        "research_note": (
            "Measured earlier on questions generated from the passage text. A "
            "question built by paraphrasing the passage hands a keyword matcher "
            "the words it needs, so this number measures the questions, not the "
            "retriever."),
        "technician_tfidf_hit1": tfidf["hit@1"],
        "technician_minilm_hit1": minilm["hit@1"],
        "technician_note": (
            "The same corpus and the same retriever, scored on questions phrased "
            "the way a technician asks. The ranking of the two retrievers "
            "reverses."),
    }


if __name__ == "__main__":
    main()
