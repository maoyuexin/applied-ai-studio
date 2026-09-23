"""Small, classroom-facing API for the Module 6 regression lesson."""

from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config, data, features, metrics

VALIDATION_START = 60
MODEL_LABEL = "Gradient-boosted regression"
BASELINE_LABEL = "8-week average"
RIDGE_LABEL = "Ridge regression"
SQUARED_LABEL = "Gradient boosting, squared error"
MODEL_PARAMS = {
    "loss": "absolute_error",
    "max_iter": 300,
    "learning_rate": 0.06,
    "max_depth": 6,
    "min_samples_leaf": 40,
    "random_state": config.SEED,
}


@dataclass(frozen=True)
class LessonData:
    """The verified data objects shared by all five teaching stages."""

    weekly: pd.DataFrame
    panel: pd.DataFrame
    names: pd.Series
    cohort: pd.Index
    design: dict


def load_lesson() -> LessonData:
    """Load the committed file and build the training-only product cohort."""
    weekly = data.load_weekly()
    panel, names, _ = data.build_panel(weekly)
    cohort = features.select_cohort(panel)
    design = features.design_matrix(panel, cohort)
    return LessonData(weekly, panel, names, cohort, design)


def lesson_summary(lesson: LessonData) -> pd.DataFrame:
    """Only the dataset facts a beginner needs for this decision."""
    rows = [
        ("Committed product-week rows", f"{len(lesson.weekly):,}"),
        ("Complete weeks", f"{lesson.panel.shape[1]}"),
        ("Products in the source panel", f"{lesson.panel.shape[0]:,}"),
        ("Steady-selling products modeled", f"{len(lesson.cohort):,}"),
        ("Training examples", f"{len(lesson.design['y_train']):,}"),
        ("Final test examples", f"{len(lesson.design['y_test']):,}"),
        ("Target", "units sold for one product in the next week"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def feature_example(lesson: LessonData, code: str = "85099B",
                    target_position: int = config.N_TRAIN) -> pd.DataFrame:
    """Show how earlier weeks become one supervised-learning row."""
    values = lesson.panel.loc[code].to_numpy(dtype=float)
    week = lesson.panel.columns[target_position]
    rows = [(f"lag {lag}", values[target_position - lag]) for lag in (1, 2, 3, 4, 8)]
    rows.extend([
        ("previous 4-week average", values[target_position - 4:target_position].mean()),
        ("previous 8-week average", values[target_position - 8:target_position].mean()),
        ("target: next week's units", values[target_position]),
    ])
    frame = pd.DataFrame(rows, columns=["Input or target", "Units"])
    frame["Product"] = f"{lesson.names.get(code, code)} ({code})"
    frame["Target week"] = pd.Timestamp(week).date()
    return frame[["Product", "Target week", "Input or target", "Units"]]


def feature_dictionary() -> pd.DataFrame:
    """The complete model inputs, grouped by the question each group answers."""
    rows = [
        ("Recent sales", "lag1, lag2, lag3, lag4, lag8", "What sold in selected earlier weeks?"),
        ("Recent level", "ma4, ma8", "What is the short- and medium-term average?"),
        ("Recent variation", "std4", "How unstable were the last four weeks?"),
        ("Seasonality", "lag52, woy, woy_sin, woy_cos", "Where are we in the retail year?"),
    ]
    return pd.DataFrame(rows, columns=["Feature group", "Columns", "Question answered"])


def _feature_index(design: dict, name: str) -> int:
    return list(design["features"]).index(name)


def _score(actual: np.ndarray, forecast_values: np.ndarray) -> tuple[float, float]:
    clipped = np.maximum(np.asarray(forecast_values, dtype=float), 0.0)
    return metrics.mae(actual, clipped), metrics.rmse(actual, clipped)


def fit_validation_model(design: dict) -> HistGradientBoostingRegressor:
    """Fit on target weeks before week 60; weeks 60-75 remain validation."""
    mask = np.asarray(design["t_train"]) < VALIDATION_START
    model = HistGradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(design["x_train"][mask], design["y_train"][mask])
    return model


def model_selection_table(design: dict) -> pd.DataFrame:
    """Compare four deliberately small candidates on validation MAE only."""
    fit_mask = np.asarray(design["t_train"]) < VALIDATION_START
    validation_mask = ~fit_mask
    x_train = np.asarray(design["x_train"])
    y_train = np.asarray(design["y_train"])
    actual = y_train[validation_mask]
    candidates = [
        (BASELINE_LABEL, None, "No training; mean of the previous eight weeks"),
        (RIDGE_LABEL,
         make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge()),
         "One weighted linear equation with shrinkage"),
        (SQUARED_LABEL,
         HistGradientBoostingRegressor(**{**MODEL_PARAMS, "loss": "squared_error"}),
         "Small trees; large errors receive extra weight"),
        (MODEL_LABEL, HistGradientBoostingRegressor(**MODEL_PARAMS),
         "Small trees; minimize the typical absolute miss"),
    ]
    rows = []
    for label, model, description in candidates:
        started = time.perf_counter()
        if model is None:
            prediction = x_train[validation_mask, _feature_index(design, "ma8")]
        else:
            model.fit(x_train[fit_mask], y_train[fit_mask])
            prediction = model.predict(x_train[validation_mask])
        mae_value, rmse_value = _score(actual, prediction)
        rows.append((label, description, mae_value, rmse_value,
                     int((np.asarray(prediction) < 0).sum()),
                     time.perf_counter() - started, label == MODEL_LABEL))
    return pd.DataFrame(rows, columns=[
        "Candidate", "How it works", "Validation MAE", "Validation RMSE",
        "Negative predictions", "Fit seconds", "Selected",
    ])


def training_structure(design: dict) -> pd.DataFrame:
    """Explain that all product-week rows train one shared estimator."""
    products = len(design["cohort"])
    target_weeks = np.asarray(design["t_train"])
    fit_rows = int((target_weeks < VALIDATION_START).sum())
    validation_rows = int((target_weeks >= VALIDATION_START).sum())
    final_rows = len(design["y_train"])
    rows = [
        ("Models trained", "1 shared regression model"),
        ("Model-selection fit", f"{fit_rows:,} rows = {products} products x {fit_rows // products} target weeks"),
        ("Validation", f"{validation_rows:,} rows = {products} products x {validation_rows // products} target weeks"),
        ("Final refit", f"{final_rows:,} rows = {products} products x {final_rows // products} target weeks"),
        ("Product identifier feature", "No - StockCode and product name are not inputs"),
        ("One prediction uses", "one product's own lag, average, variation, and calendar features"),
    ]
    return pd.DataFrame(rows, columns=["Training fact", "Value"])


def validation_comparison(design: dict) -> pd.DataFrame:
    """Choose between one baseline and one regressor on the validation period."""
    mask = np.asarray(design["t_train"]) >= VALIDATION_START
    actual = np.asarray(design["y_train"])[mask]
    baseline = np.asarray(design["x_train"])[mask, _feature_index(design, "ma8")]
    model = fit_validation_model(design)
    regression = model.predict(np.asarray(design["x_train"])[mask])
    rows = []
    for label, values in ((BASELINE_LABEL, baseline), (MODEL_LABEL, regression)):
        mae_value, rmse_value = _score(actual, values)
        rows.append((label, mae_value, rmse_value, int(mask.sum())))
    return pd.DataFrame(rows, columns=["Model", "MAE", "RMSE", "Examples"])


def fit_final_model(design: dict) -> HistGradientBoostingRegressor:
    """Refit the selected regressor on all pre-test examples."""
    model = HistGradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(design["x_train"], design["y_train"])
    return model


def prediction_frame(design: dict, model: HistGradientBoostingRegressor) -> pd.DataFrame:
    """One row per product-week in the untouched 26-week test period."""
    product_rows = np.asarray(design["product_test"], dtype=int)
    target_rows = np.asarray(design["t_test"], dtype=int)
    codes = np.asarray(design["cohort"], dtype=object)[product_rows]
    weeks = pd.to_datetime(np.asarray(design["weeks"])[target_rows])
    baseline = design["x_test"][:, _feature_index(design, "ma8")]
    regression = np.maximum(model.predict(design["x_test"]), 0.0)
    return pd.DataFrame({
        "StockCode": codes,
        "week": weeks,
        "actual": design["y_test"],
        "8-week average": baseline,
        "regression": regression,
    })


def test_comparison(predictions: pd.DataFrame) -> pd.DataFrame:
    """Final MAE and RMSE on rows untouched by training and model selection."""
    actual = predictions["actual"].to_numpy()
    rows = []
    for label, column in ((BASELINE_LABEL, "8-week average"),
                          (MODEL_LABEL, "regression")):
        mae_value, rmse_value = _score(actual, predictions[column].to_numpy())
        rows.append((label, mae_value, rmse_value, len(predictions)))
    return pd.DataFrame(rows, columns=["Model", "MAE", "RMSE", "Examples"])


def worked_prediction_example(lesson: LessonData,
                              model: HistGradientBoostingRegressor,
                              code: str = "85099B",
                              week: str = "2011-11-21") -> pd.DataFrame:
    """Trace real inputs, two predictions, and the actual for one held-out week."""
    design = lesson.design
    target_week = pd.Timestamp(week)
    target_position = list(design["weeks"]).index(target_week)
    product_position = list(design["cohort"]).index(code)
    matches = np.where(
        (np.asarray(design["product_test"]) == product_position)
        & (np.asarray(design["t_test"]) == target_position)
    )[0]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {code} in {week}, found {len(matches)}")
    row = int(matches[0])
    values = dict(zip(design["features"], design["x_test"][row]))
    baseline = float(values["ma8"])
    regression = max(float(model.predict(design["x_test"][row:row + 1])[0]), 0.0)
    actual = float(design["y_test"][row])
    records = [
        ("Input", "Last week (lag1)", values["lag1"]),
        ("Input", "4-week average (ma4)", values["ma4"]),
        ("Input", "8-week average (ma8)", values["ma8"]),
        ("Input", "Recent variation (std4)", values["std4"]),
        ("Input", "Same week last year (lag52)", values["lag52"]),
        ("Input", "Week of year", values["woy"]),
        ("Prediction", BASELINE_LABEL, baseline),
        ("Prediction", MODEL_LABEL, regression),
        ("Outcome", "Actual units", actual),
        ("Absolute error", BASELINE_LABEL, abs(actual - baseline)),
        ("Absolute error", MODEL_LABEL, abs(actual - regression)),
    ]
    frame = pd.DataFrame(records, columns=["Role", "Quantity", "Value"])
    frame.attrs.update({"product": lesson.names.get(code, code), "code": code,
                        "week": target_week.date()})
    return frame


def _layout(figure: go.Figure, title: str, height: int = 440) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=70, r=35, t=85, b=65),
        font=dict(family="Arial", size=13, color=config.COLOR_ACTUAL),
        hoverlabel=dict(font_size=13),
    )
    return figure


def history_figure(lesson: LessonData,
                   codes: tuple[str, ...] = config.DEMO_PRODUCTS) -> go.Figure:
    """Three real products show trend, noise, and seasonal spikes."""
    titles = [str(lesson.names.get(code, code)) for code in codes]
    figure = make_subplots(rows=len(codes), cols=1, shared_xaxes=True,
                           vertical_spacing=0.08, subplot_titles=titles)
    for row, code in enumerate(codes, start=1):
        series = lesson.panel.loc[code]
        figure.add_scatter(x=series.index, y=series.values, mode="lines",
                           line=dict(color=config.COLOR_FORECAST, width=1.8),
                           name=code, showlegend=False, row=row, col=1)
        figure.update_yaxes(title="Units", rangemode="tozero", row=row, col=1)
    figure.update_xaxes(title="Week beginning", row=len(codes), col=1)
    return _layout(figure, "Weekly sales do not follow one tidy shape", height=640)


def feature_window_figure(lesson: LessonData, code: str = "85099B",
                          target_position: int = config.N_TRAIN) -> go.Figure:
    """The eight historical bars are inputs; the ninth bar is the target."""
    series = lesson.panel.loc[code]
    window = series.iloc[target_position - 8:target_position + 1]
    colors = [config.COLOR_FORECAST] * 8 + [config.COLOR_MISS]
    labels = ["input"] * 8 + ["target"]
    figure = go.Figure(go.Bar(
        x=window.index,
        y=window.values,
        marker_color=colors,
        customdata=np.asarray(labels)[:, None],
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:,.0f} units<br>%{customdata[0]}<extra></extra>",
    ))
    figure.add_hline(y=float(window.iloc[:8].mean()), line_dash="dash",
                     line_color=config.COLOR_WARN,
                     annotation_text=f"8-week baseline = {window.iloc[:8].mean():.1f}")
    figure.update_xaxes(title="Week",
                        tickformat="%b %d", tickangle=-35)
    figure.update_yaxes(title="Units sold", rangemode="tozero")
    return _layout(figure, "Eight inputs, one target")


def split_figure(lesson: LessonData) -> go.Figure:
    """The validation and test periods remain later than model fitting."""
    totals = lesson.panel.loc[lesson.cohort].sum(axis=0)
    weeks = list(totals.index)
    figure = go.Figure(go.Scatter(
        x=weeks, y=totals.values, mode="lines",
        line=dict(color=config.COLOR_ACTUAL, width=1.8),
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:,.0f} units<extra></extra>",
    ))
    spans = [
        (8, VALIDATION_START - 1, "Fit", config.COLOR_FORECAST),
        (VALIDATION_START, config.N_TRAIN - 1, "Validation", config.COLOR_WARN),
        (config.N_TRAIN, len(weeks) - 1, "Final test", config.COLOR_ACCENT),
    ]
    for start, end, label, color in spans:
        figure.add_vrect(x0=weeks[start], x1=weeks[end], fillcolor=color,
                         opacity=0.13, line_width=0, annotation_text=label,
                         annotation_position="top left")
    figure.update_xaxes(title="Week beginning")
    figure.update_yaxes(title="Units across the modeled products", rangemode="tozero")
    return _layout(figure, "Time stays in order: fit, choose, then test once")


def metric_figure(table: pd.DataFrame, title: str) -> go.Figure:
    """MAE and RMSE are separated so their different questions stay visible."""
    colors = [config.COLOR_WARN, config.COLOR_ACCENT]
    figure = make_subplots(rows=1, cols=2, subplot_titles=("MAE", "RMSE"))
    for column, metric_name in enumerate(("MAE", "RMSE"), start=1):
        figure.add_bar(x=table["Model"], y=table[metric_name], marker_color=colors,
                       text=table[metric_name].map("{:.1f}".format),
                       textposition="outside", showlegend=False,
                       row=1, col=column)
        figure.update_yaxes(title="Error in units (lower is better)", row=1, col=column)
    figure.update_xaxes(tickangle=-12)
    return _layout(figure, title, height=460)


def weekly_predictions_figure(predictions: pd.DataFrame) -> go.Figure:
    """Aggregate the product-level rows only to make the 26 test weeks readable."""
    weekly = predictions.groupby("week")[["actual", "8-week average", "regression"]].sum()
    figure = go.Figure()
    styles = [
        ("actual", "Actual units", config.COLOR_ACTUAL, "solid"),
        ("8-week average", BASELINE_LABEL, config.COLOR_WARN, "dot"),
        ("regression", MODEL_LABEL, config.COLOR_ACCENT, "dash"),
    ]
    for column, label, color, dash in styles:
        figure.add_scatter(x=weekly.index, y=weekly[column], mode="lines+markers",
                           name=label, line=dict(color=color, width=2, dash=dash))
    figure.update_xaxes(title="Held-out week beginning")
    figure.update_yaxes(title="Units across 469 products", rangemode="tozero")
    figure.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    return _layout(figure, "The model follows most weeks but still misses the autumn surge",
                   height=470)


def product_prediction_figure(predictions: pd.DataFrame, names: pd.Series,
                              code: str = config.CHRISTMAS_PRODUCT) -> go.Figure:
    """One product makes the model output and its seasonal limit concrete."""
    frame = predictions[predictions["StockCode"] == code].sort_values("week")
    figure = go.Figure()
    for column, label, color, dash in (
        ("actual", "Actual units", config.COLOR_ACTUAL, "solid"),
        ("8-week average", BASELINE_LABEL, config.COLOR_WARN, "dot"),
        ("regression", MODEL_LABEL, config.COLOR_ACCENT, "dash"),
    ):
        figure.add_scatter(x=frame["week"], y=frame[column], mode="lines+markers",
                           name=label, line=dict(color=color, width=2, dash=dash))
    figure.update_xaxes(title="Held-out week beginning")
    figure.update_yaxes(title="Units sold", rangemode="tozero")
    figure.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    return _layout(figure, f"One prediction story: {names.get(code, code)}", height=470)