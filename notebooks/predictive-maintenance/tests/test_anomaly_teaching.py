import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdmlab import config, teaching


def test_source_profile_shows_feature_sources_without_a_selection_detour():
    from pdmlab import data

    profile = teaching.source_profile(data.load_minutes()).set_index("Column")
    assert profile.columns.tolist() == ["What it measures", "Used to build features"]
    assert profile.loc["TP3", "Used to build features"].startswith("Yes:")
    assert profile.loc["Motor_current", "Used to build features"].startswith("Yes:")
    assert profile.loc["Reservoirs", "Used to build features"] == "No"


def test_model_comparison_cannot_read_test_period():
    scores = pd.Series([0.1, 0.4], index=pd.to_datetime(["2020-07-01", "2020-07-02"]))
    with pytest.raises(ValueError, match="validation-period"):
        teaching.compare_models({"Example": scores})


def test_cutoff_uses_validation_quantile_and_no_labels_for_fitting():
    scores = pd.Series(np.linspace(0, 1, 100), index=pd.date_range(config.DEV_START, periods=100, freq="h"))
    row = teaching.compare_models({"Example": scores}).iloc[0]
    assert row["Comparison cutoff"] == pytest.approx(0.98)
    assert row["Alert hours"] == 2
    assert row["Alert share (%)"] == 2


def test_score_cutoff_plot_makes_the_flag_rule_visible():
    scores = pd.Series(np.linspace(0.4, 0.8, 100),
                       index=pd.date_range("2020-04-01", periods=100, freq="h"))
    figure, summary = teaching.score_cutoff_plot(scores, 0.7)
    assert summary["Validation hours"].sum() == 100
    assert summary.set_index("Decision").loc["Flag for review", "Validation hours"] == 25
    assert len(figure.data) == 2
    assert np.all(np.asarray(figure.data[1].y) >= 0.7)
    assert any(shape.type == "line" and shape.y0 == shape.y1 == 0.7 for shape in figure.layout.shapes)
    assert figure.layout.title.text == "Scores over time: above the line = review"
    assert figure.layout.xaxis.type == "date"
    assert figure.layout.xaxis.title.text == "Date in the validation period"
    assert list(figure.data[0].x) == list(scores.index)


def test_feature_comparison_uses_real_units_and_plain_readings():
    columns = config.MODEL_FEATURES
    training = pd.DataFrame([[0.05, 2, 20, 55, 0.5, 0.04],
                             [0.10, 3, 30, 65, 0.6, 0.08]], columns=columns)
    example = pd.Series([0.50, 6, 5, 75, 1.2, 0.06], index=columns)
    comparison = teaching.feature_comparison(training, example)
    assert comparison.columns.tolist() == ["Measurement", "Typical range", "This hour", "Compared with typical"]
    assert comparison.iloc[0]["Measurement"] == "Compressor working"
    assert comparison.iloc[0]["This hour"] == "50.0%"
    assert comparison.iloc[0]["Compared with typical"] == "Higher than typical"
    assert comparison.iloc[2]["Compared with typical"] == "Lower than typical"
    assert comparison.iloc[-1]["Compared with typical"] == "Within typical range"
    assert "IQR" not in " ".join(comparison.astype(str).to_numpy().ravel())


def test_model_selection_prefers_detection_then_lower_workload():
    comparison = pd.DataFrame([
        {"Model": "Baseline", "Reported events found": 2, "False callouts": 0},
        {"Model": "Candidate", "Reported events found": 3, "False callouts": 7},
    ])
    assert teaching.choose_model(comparison) == "Candidate"
    comparison.loc[0, "Reported events found"] = 3
    assert teaching.choose_model(comparison) == "Baseline"


def test_hourly_report_counts_exclude_ambiguous_hours_and_preserve_gaps():
    stamps = pd.to_datetime(["2020-07-01 00:00", "2020-07-15 13:00", "2020-07-15 14:00", "2020-07-15 15:00", "2020-07-15 19:00"])
    scores = pd.Series([0.1, 0.2, 0.8, 0.2, 0.8], index=stamps)
    figure, excluded = teaching.hourly_agreement(scores, 0.5, (config.TEST_START, config.TEST_END))
    np.testing.assert_array_equal(figure.data[0].z, [[1, 1], [0, 1]])
    assert excluded == 2
    timeline = teaching.event_timeline(scores, 0.5)
    assert np.isnan(np.asarray(timeline.data[0].y, dtype=float)).any()
    assert timeline.data[0].connectgaps is False


def test_event_timing_accounts_for_aggregate_availability():
    scores = pd.Series([0.8, 0.2], index=pd.to_datetime(["2020-07-15 14:00", "2020-07-15 15:00"]))
    event = teaching.event_table(scores, 0.5, (config.TEST_START, config.TEST_END)).iloc[0]
    assert event["Recorded lead (h)"] == 0.5
    assert event["Lead after hour ends (h)"] == -0.5


def test_prediction_timeline_aligns_cutoff_reports_and_missing_hours():
    scores = pd.Series([0.5, 0.49, 0.8], index=pd.to_datetime([
        "2020-07-15 13:00", "2020-07-15 14:00", "2020-07-15 19:00"]))
    figure, table = teaching.prediction_timeline(scores, 0.5,
        (pd.Timestamp("2020-07-15 13:00"), pd.Timestamp("2020-07-15 20:00")))
    assert len(table) == 7
    assert table.iloc[0]["Model flag"] == 1
    assert table.iloc[1]["Model flag"] == 0
    assert table.iloc[1]["Reported event"] == 1
    assert table.loc["2020-07-15 15:00", "Reported event"] == 1
    assert pd.isna(table.loc["2020-07-15 15:00", "Model flag"])
    assert table.iloc[-1]["Reported event"] == 0
    assert table["Cutoff"].eq(0.5).all()
    assert figure.data[0].connectgaps is False
    assert figure.data[2].connectgaps is False
    assert list(figure.data[0].x) == list(figure.data[2].x) == list(figure.data[3].x)
    assert [figure.layout[axis].type for axis in ["xaxis", "xaxis2", "xaxis3"]] == ["date"] * 3
    assert len(figure.layout.updatemenus[0].buttons) == 2
    assert all(trace.type == "scatter" for trace in figure.data)


def test_real_reference_comparison_and_test_evidence():
    from sklearn.ensemble import IsolationForest
    from pdmlab import data, detect, features, metrics

    matrix = features.model_matrix(features.hourly_features(data.load_minutes()))
    training = detect.training_slice(matrix)
    validation = matrix.loc[(matrix.index >= config.DEV_START) & (matrix.index < config.DEV_END)]
    test = matrix.loc[(matrix.index >= config.TEST_START) & (matrix.index < config.TEST_END)]
    baseline = detect.RobustZDetector().fit(training)
    forest = IsolationForest(n_estimators=300, max_samples=256, random_state=42, contamination="auto").fit(training)
    comparison = teaching.compare_models({"Robust-score baseline": baseline.score(validation),
        "Isolation Forest": pd.Series(-forest.score_samples(validation), index=validation.index)})
    assert teaching.choose_model(comparison) == "Isolation Forest"
    assert comparison["Reported events found"].tolist() == [2, 3]
    assert comparison["False callouts"].tolist() == [0, 7]
    assert comparison["Alert hours"].tolist() == [36, 36]
    cutoff = float(comparison.iloc[1]["Comparison cutoff"])
    test_scores = pd.Series(-forest.score_samples(test), index=test.index)
    result = metrics.evaluate(test_scores, cutoff, (config.TEST_START, config.TEST_END))
    assert result["failures_detected"] == 1
    assert result["false_callouts"] == 4
    feature_figure, summary = teaching.feature_example(data.load_minutes(), matrix)
    assert summary["Working minutes"].tolist() == [4, 60]
    assert len(feature_figure.data) == 2
    for figure in [teaching.feature_cloud(training, validation), teaching.alert_map(test, test_scores, cutoff)]:
        assert all(trace.type == "scatter" for trace in figure.data)
    feature_review = teaching.feature_comparison(training, test.loc[test_scores.idxmax()])
    assert feature_review["Compared with typical"].tolist().count("Within typical range") == 1

def test_period_timeline_marks_three_periods_and_four_leaks():
    figure = teaching.period_timeline()
    rects = [shape for shape in figure.layout.shapes if shape.type == "rect"]
    assert len(rects) == 3
    assert len(figure.data) == 1 and len(figure.data[0].x) == 4
    assert list(figure.data[0].text) == ["F1", "F2", "F3", "F4"]
    assert figure.layout.xaxis.type == "date"


def test_day_comparison_shows_three_signals_for_two_days():
    from pdmlab import data

    figure = teaching.day_comparison(data.load_minutes())
    assert len(figure.data) == 6
    assert all(trace.type == "scatter" and trace.connectgaps is False for trace in figure.data)
    assert all(0 <= min(trace.x) and max(trace.x) < 24 for trace in figure.data)
    assert figure.layout.yaxis.title.text == "Motor current (A)"


def test_scorecard_adds_practice_and_final_check_results():
    from sklearn.ensemble import IsolationForest
    from pdmlab import data, detect, features

    matrix = features.model_matrix(features.hourly_features(data.load_minutes()))
    training = detect.training_slice(matrix)
    validation = matrix.loc[(matrix.index >= config.DEV_START) & (matrix.index < config.DEV_END)]
    test = matrix.loc[(matrix.index >= config.TEST_START) & (matrix.index < config.TEST_END)]
    forest = IsolationForest(n_estimators=300, max_samples=256, random_state=42, contamination="auto").fit(training)
    validation_scores = pd.Series(-forest.score_samples(validation), index=validation.index)
    test_scores = pd.Series(-forest.score_samples(test), index=test.index)
    cutoff = float(teaching.compare_models({"Isolation Forest": validation_scores}).iloc[0]["Comparison cutoff"])
    card = teaching.scorecard(validation_scores, test_scores, cutoff).set_index("What the evidence shows")["Result"]
    assert card["Leaks flagged while they were happening"].startswith("4 of 4")
    assert card["Leaks flagged before they were reported"].startswith("1 of 4 (F4)")
    assert card["Hours flagged in the final check"].startswith("27 of 1,224")
    assert card["Extra callouts in the final check"].startswith("4 groups")
    assert card["Warning time for F4"].startswith("13.5 hours")
