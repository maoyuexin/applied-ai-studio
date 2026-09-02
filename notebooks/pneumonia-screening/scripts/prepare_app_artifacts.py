"""Train the notebook workflow and export verified artifacts for the web app."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pneumonialab import config, data, handoff, metrics, models  # noqa: E402


def main() -> None:
    print("Loading checksum-verified PneumoniaMNIST data...")
    splits = data.load_splits()
    print("Training the compact CNN on CPU...")
    training = models.fit_small_cnn(splits)
    validation_scores = models.predict_scores(training.model, splits["validation"].images)
    policy = metrics.select_threshold(
        splits["validation"].labels,
        validation_scores,
        config.TARGET_VALIDATION_SENSITIVITY,
    )
    test_scores = models.predict_scores(training.model, splits["test"].images)
    test_result = metrics.evaluate(
        splits["test"].labels, test_scores, float(policy["threshold"])
    )
    sizes = handoff.export(
        training,
        splits,
        validation_scores,
        test_scores,
        policy,
        test_result,
    )
    identity = handoff.verify(splits)
    for name, size in sizes.items():
        print(f"  {name:<28} {size}")
    print(
        f"Ready in {training.runtime_seconds:.1f}s: "
        f"sensitivity {test_result['sensitivity']:.1%}, "
        f"specificity {test_result['specificity']:.1%}, "
        f"{identity['decision_changes']} reload decision changes."
    )


if __name__ == "__main__":
    main()