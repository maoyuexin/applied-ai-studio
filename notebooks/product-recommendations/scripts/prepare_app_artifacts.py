"""Run the whole product-recommendation workflow headlessly and export the artifacts.

Same committed data, same frozen decisions and the same order as the notebook -
committed interactions -> the global time split at 2011-09-09 -> all seven
scorers -> BOTH leaderboards -> the popularity-bias and leave-one-out evidence
-> the operating policy -> export -> reload verification in this process - so
``npm run prepare:recommendations`` reproduces exactly the files the notebook
commits evidence for.

Nothing here downloads anything and nothing here fits a model twice. The
interaction log is committed, the split is deterministic, and the seed is 42.

    node scripts/venv-python.mjs notebooks/product-recommendations/scripts/prepare_app_artifacts.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from reclab import (config, data, evaluate, handoff, matrix,  # noqa: E402
                    models, policy)

NEIGHBOUR_SWEEP = [3, 5, 10, 15, 20, 30, 40]
DAMPING_ALPHAS = [0.0, 0.25, 0.5]


def main() -> None:
    started = time.perf_counter()

    print("Loading the committed interaction log...")
    frame = data.load_interactions()
    descriptions = data.load_descriptions()
    ledger = data.load_ledger()
    checks = data.verify_cleaning(frame)
    print(f"  {len(frame):,} rows, {frame['invoice'].nunique():,} baskets, "
          f"{frame['stock_code'].nunique():,} products, "
          f"{frame['customer_id'].nunique():,} registered customers")
    print(f"  cleaning guarantees re-tested: {int(checks['Holds'].sum())}/{len(checks)} hold")
    if not bool(checks["Holds"].all()):
        raise SystemExit("The committed file no longer satisfies its own cleaning rules.")

    print(f"Building the matrix and splitting in time at {config.SPLIT_CUT.date()}...")
    split = matrix.build_split(frame)
    density = split.R.nnz / (split.n_users * split.n_items)
    print(f"  {split.n_users:,} customers x {split.n_items:,} products, "
          f"{split.R.nnz:,} filled cells, {1 - density:.3%} sparse")
    print(f"  scorable customers: {len(split.truth_standard):,} standard, "
          f"{len(split.truth_discovery):,} discovery")
    if (split.n_users, split.n_items) != config.EXPECTED_MATRIX_SHAPE:
        raise SystemExit(
            f"Matrix is {(split.n_users, split.n_items)}, expected "
            f"{config.EXPECTED_MATRIX_SHAPE}. The frozen numbers will not reproduce.")

    repeat = matrix.repeat_purchase_profile(split)
    concentration = matrix.concentration(split)
    print(f"  {repeat['repeat_share']:.1%} of the test truth and "
          f"{repeat['repeat_revenue_share']:.1%} of test revenue is a product the "
          "customer already owned")

    print(f"Fitting every scorer (deployed: item-item cosine, top "
          f"{config.ITEM_NEIGHBOURS} neighbours)...")
    fitted = models.fit_all(split)
    deployed = fitted[config.DEPLOYED_MODEL_LABEL]
    print(f"  {len(fitted)} scorers; {deployed.label} fitted in "
          f"{deployed.fit_seconds:.2f}s, {deployed.payload.nnz:,} stored links")

    print("\nLeaderboard A - standard next-purchase "
          "(truth: everything bought after the cut, repeats included)")
    standard = evaluate.leaderboard(split, fitted, config.PROTOCOL_STANDARD)
    _print_board(standard)

    print("\nLeaderboard B - discovery "
          "(truth: only products never bought before; history masked out)")
    discovery = evaluate.leaderboard(split, fitted, config.PROTOCOL_DISCOVERY)
    _print_board(discovery)

    comparison = evaluate.two_table_comparison(standard, discovery)
    incoherent = evaluate.leaderboard(split, fitted, config.PROTOCOL_INCOHERENT)
    zero = evaluate.zero_score_diagnosis(split, fitted[config.REORDER_LABEL])
    print(f"\n  The inversion: {config.REORDER_LABEL} is rank "
          f"{int(comparison.loc[comparison['Model'] == config.REORDER_LABEL, 'Standard rank'].iloc[0])} "
          "on the standard protocol and rank "
          f"{int(comparison.loc[comparison['Model'] == config.REORDER_LABEL, 'Discovery rank'].iloc[0])} "
          "on discovery - below ten products drawn at random.")
    print(f"  Why: {zero['share_with_all_zero_scores']:.1%} of scored customers get "
          "an all-zero score vector once their history is masked.")

    print("\nMeasuring what each model actually puts in front of people...")
    exposure = evaluate.exposure_profile(split, fitted)
    loop = evaluate.exposure_loop(split)
    print(f"  {config.POPULARITY_LABEL} coverage "
          f"{float(exposure.loc[exposure['Model'] == config.POPULARITY_LABEL, 'Coverage'].iloc[0]):.2%}; "
          f"ten exposure rounds move the top-10 share "
          f"{float(loop['Top-10 share'].iloc[0]):.2%} -> {float(loop['Top-10 share'].iloc[-1]):.2%} "
          "(assumption, not a measurement)")

    print("Measuring how much a leave-one-out split flatters each model...")
    inflation = evaluate.loo_inflation(frame, split)
    for row in inflation.to_dict("records"):
        print(f"  {row['Model']:<22} inflation +{row['Inflation']:.1%}")

    print("Measuring the truncation trade and the damping knob...")
    truncation = evaluate.truncation_trade(split, NEIGHBOUR_SWEEP)
    damping = evaluate.damping_no_op_table(split, DAMPING_ALPHAS)
    chosen = truncation[truncation["Neighbours kept"] == str(config.ITEM_NEIGHBOURS)]
    print(f"  top-{config.ITEM_NEIGHBOURS}: discovery HR@10 "
          f"{float(chosen['Discovery HR@10'].iloc[0]):.4f}, coverage "
          f"{float(chosen['Coverage'].iloc[0]):.2%}, "
          f"{float(chosen['Stored megabytes'].iloc[0]):.2f} MB "
          f"({float(chosen['Shrink vs the full matrix'].iloc[0]):.0f}x smaller than the full matrix)")
    print(f"  popularity damping: {damping['Discovery HR@10'].nunique()} distinct HR@10 "
          f"across {len(damping)} alphas - the knob is wired to nothing")

    print("Pricing the upper bound on incremental revenue...")
    revenue = evaluate.incremental_revenue(split, fitted)
    for row in revenue.to_dict("records"):
        print(f"  {row['Model']:<28} "
              f"{row['Share of available new-product revenue']:.2%} of available "
              f"new-product revenue")

    print("Counting who the policy cannot serve, and choosing the fallback...")
    cold = policy.cold_start_census(frame, split)
    sweep = policy.fallback_sweep(split)
    fallback = policy.fallback_list(split, descriptions)
    outcomes = policy.policy_outcomes(frame, split, deployed)
    print(f"  {cold['cold_registered_share']:.1%} of registered test customers are "
          f"cold and {cold['thin_history_share']:.1%} are thin - "
          f"{outcomes['fallback_share']:.1%} get the fallback list")
    print(f"  guest checkouts are a DIFFERENT population: "
          f"{cold['guest_row_share']:.1%} of test rows, "
          f"{cold['guest_revenue_share']:.1%} of test revenue")
    print(f"  chosen fallback: {sweep['Fallback rule'].iloc[0]} "
          f"(HR@10 {float(sweep['HR@10'].iloc[0]):.4f} on "
          f"{int(sweep['Cold customers scored'].iloc[0]):,} cold customers)")

    print("Exporting...")
    customers = handoff.reload_users(split)
    reload_check = {
        "customers": len(customers),
        "selection": (f"the discovery-protocol population sorted by customer id, "
                      f"first {config.RELOAD_CHECK_USERS}"),
        "protocol": config.PROTOCOL_DISCOVERY,
        "baseline_top10": handoff.baseline_top10(split, deployed, customers),
        "similarity_digest": handoff.similarity_digest(deployed.payload),
    }
    catalog = handoff.build_catalog(split, descriptions)
    samples = handoff.build_samples(split, descriptions, fitted)
    evidence = handoff.assemble_evidence(
        split=split, ledger=ledger, repeat_profile=repeat,
        concentration=concentration, standard=standard, discovery=discovery,
        comparison=comparison, zero_diagnosis=zero, revenue=revenue, cold=cold,
        outcomes=outcomes, reload_check=reload_check, incoherent=incoherent,
        exposure=exposure, loop=loop, inflation=inflation, truncation=truncation,
        damping=damping, fallback_sweep=sweep,
    )
    model_card = handoff.build_model_card(evidence, catalog)
    operating_policy = handoff.build_policy(evidence, fallback)
    exported = handoff.export(deployed.payload, catalog, evidence, model_card,
                              operating_policy, samples)
    for row in exported.to_dict("records"):
        print(f"  {row['Artifact']:<24} {row['Size']:>10}   "
              f"{row['What the service does with it']}")

    print(f"Reloading the artifacts in this process and re-ranking "
          f"{config.RELOAD_CHECK_USERS} customers...")
    identity = handoff.verify()
    print(f"  {identity['status']}: identical top-10 for "
          f"{identity['identical_top10']} customers, "
          f"{identity['stored_links']:,} stored links")

    print()
    print(handoff.committed_size().to_string(index=False))
    print(f"\nReady in {time.perf_counter() - started:.1f}s.")


def _print_board(board) -> None:
    print(f"  {'Model':<28}{'HR@10':>9}{'NDCG@10':>10}{'Coverage':>11}"
          f"{'Novelty':>10}{'Pop rank':>10}")
    for row in board.to_dict("records"):
        print(f"  {row['Model']:<28}{row['HR@10']:>9.4f}{row['NDCG@10']:>10.4f}"
              f"{row['Coverage']:>10.2%}{row['Novelty']:>10.2f}"
              f"{row['Mean pop rank']:>10.0f}")
    print(f"  n = {int(board['Customers scored'].iloc[0]):,} customers")


if __name__ == "__main__":
    main()
