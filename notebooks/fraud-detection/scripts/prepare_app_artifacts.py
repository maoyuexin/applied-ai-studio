"""Train the notebook's selected workflow and export artifacts for the web app."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from fraudlab import config, data, features, handoff, models  # noqa: E402


def main() -> None:
    print("Loading and engineering the synthetic Sparkov transactions...")
    joined = data.join(data.load_transactions(), data.load_customers())
    featured = features.build_features(joined)
    parts = data.split_by_time(featured)
    x_train, y_train = features.feature_matrix(parts["train"])
    x_test, y_test = features.feature_matrix(parts["test"])
    x_test = features.align_columns(x_test, x_train)
    amounts_test = parts["test"]["amt"].to_numpy()

    forest = models.candidate_models()["Random forest"]["estimator"]
    print("Selecting the balancing treatment...")
    bakeoff = models.run_balancing_bakeoff(
        forest, x_train, y_train, x_test, y_test, amounts_test
    )
    best_treatment = str(bakeoff.iloc[0]["Treatment"])

    print(f"Comparing model families with {best_treatment}...")
    leaderboard, fitted = models.run_model_sweep(
        x_train,
        y_train,
        x_test,
        y_test,
        amounts_test,
        treatment_name=best_treatment,
    )
    winner_name = str(leaderboard.iloc[0]["Model"])
    winner = fitted[winner_name]
    result = winner["result"]
    rationale = (
        f"{winner_name} with {best_treatment} balancing. Chosen at a "
        f"{config.REVIEW_BUDGET:.0%} review budget on a held-out period "
        f"({config.TEST_START:%b %Y} to {config.TEST_END:%b %Y}). "
        f"Recall {result['recall']:.1%}, precision {result['precision']:.1%}."
    )
    sizes = handoff.export(
        model=winner["model"],
        model_name=winner_name,
        leaderboard=leaderboard,
        bakeoff=bakeoff,
        balancing_treatment=best_treatment,
        result=result,
        feature_columns=list(x_train.columns),
        test_frame=parts["test"],
        selection_rationale=rationale,
    )
    check = handoff.verify()
    assert all(abs(value) < 1e-6 for value in check["drift"].values())
    assert check["mlflow_max_probability_delta"] < 1e-12
    assert check["mlflow_decision_changes"] == 0

    for name, size in sizes.items():
        print(f"  {name:<24} {size}")
    print(
        f"Ready: recall {check['reproduced']['recall']:.1%}, "
        f"precision {check['reproduced']['precision']:.1%}, "
        "zero MLflow decision changes."
    )


if __name__ == "__main__":
    main()