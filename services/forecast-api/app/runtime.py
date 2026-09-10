from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import REPOSITORY_ROOT
from .schemas import (
    CohortOutcome,
    DatasetInfo,
    EvaluationSummary,
    HistoryWeek,
    LatestWeek,
    LosingProduct,
    ModelInfo,
    OrderOutcome,
    PlanRequest,
    PlanResponse,
    PlanWeek,
    PolicyInfo,
    PolicySweepResponse,
    ProductSummary,
    SeasonalCoverage,
)

# forecaster.joblib pickles a *reference* to fclab.forecast.WeeklyQuantileForecaster,
# so the notebook package has to be importable before joblib.load runs. Serving then
# rebuilds the weekly panel with the notebook's own data code, re-scores the held-out
# weeks with the notebook's own forecaster, and prices every order through the
# notebook's own PolicyBoard, rather than a second copy of that arithmetic that could
# quietly drift away from the evidence the model card reports.
NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "demand-forecasting"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from fclab import config as fc  # noqa: E402
from fclab import data, forecast  # noqa: E402
from fclab import policy as fc_policy  # noqa: E402

ARTIFACT_FILES = (
    "forecaster.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)

RECOVERY = (
    "Run notebooks/demand-forecasting/01_forecast_build.ipynb or npm run prepare:forecast"
)

# The ratio the notebook froze as the headline: a unit not on the shelf costs four
# times what a unit left in the box costs.
POLICY_RATIO = 4.0

# How many training weeks of plain history the plan hands back for context. The
# forecast itself never looks further back than the last 8.
HISTORY_WEEKS = 12

BOUNDARY_SHORT = (
    "The forecast is not a promise, the interval is not a guarantee, and a planner "
    "approves every order - the system never places one."
)

FORECAST_NOTE = (
    "One number for one product and one coming week: the mean of this product's last "
    "eight observed weeks. It is a starting point for a buyer, not a commitment that "
    "this many units will sell."
)

INTERVAL_NOTE = (
    "The 80% band is this product's own past errors laid over the forecast. On the "
    "held-out weeks it contained what actually happened 84.06% of the time against a "
    "promised 80%. It is a range that has held, not a range that will hold."
)

POINT_RULE = "Order the point forecast"
POINT_PLAIN = (
    "Buy exactly what the model expects to sell. Cheap to explain, and short in every "
    "week that runs above the forecast - which is about half of them."
)
QUANTILE_PLAIN_TEMPLATE = (
    "Buy the quantity that would have been enough in {share:.0f}% of weeks, read off "
    "this product's own band. Counting a unit not on the shelf as {ratio:g} times as "
    "costly as a unit left in the box is what moves the order to that point."
)
MEAN_RULE = "Order the average"
MEAN_PLAIN = (
    "Buy this product's average training week, every week. The business grew and the "
    "held-out window is the autumn ramp, so the average is short almost everywhere."
)


def _clean(value: object) -> object:
    """Make a notebook record safe for JSON: no NaN, no numpy scalars."""
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(rows: list[dict]) -> list[dict]:
    return [{key: _clean(item) for key, item in row.items()} for row in rows]


def _percent(text: object) -> float:
    """'66.2%' -> 66.2. The seasonal slices arrive formatted for a slide."""
    try:
        return float(str(text).strip().rstrip("%"))
    except ValueError:
        return float("nan")


def _ratio_label(ratio: float) -> str:
    """4.0 -> '4:1', 4.5 -> '4.5:1'. A planner says the whole number out loud."""
    return f"{ratio:g}:1"


class ForecastRuntime:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = Path(artifact_dir)
        missing = [name for name in ARTIFACT_FILES if not (self.artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing demand-forecasting artifacts in {self.artifact_dir}: "
                f"{', '.join(missing)}. {RECOVERY}."
            )
        if not fc.WEEKLY_CSV.exists():
            raise FileNotFoundError(
                f"The committed weekly demand file is missing at {fc.WEEKLY_CSV}. {RECOVERY}."
            )

        self.card = json.loads((self.artifact_dir / "model_card.json").read_text())
        self.evaluation = json.loads((self.artifact_dir / "evaluation.json").read_text())
        self.policy = json.loads((self.artifact_dir / "operating_policy.json").read_text())
        self.forecaster = joblib.load(self.artifact_dir / "forecaster.joblib")
        self.manifest = pd.read_parquet(self.artifact_dir / "sample_manifest.parquet")

        # The same four lines the notebook and prepare_app_artifacts.py run, in the
        # same order, so a week planned here is the week the evidence describes.
        weekly = data.load_weekly()
        self.panel, self.names, self.prices = data.build_panel(weekly)
        self.scored = forecast.score_holdout(self.panel, self.forecaster)
        self.board = fc_policy.PolicyBoard(
            self.panel, self.scored, self.forecaster, self.prices
        )

        self.train_weeks = list(self.panel.columns[: fc.N_TRAIN])
        self.test_weeks = list(self.panel.columns[fc.N_TRAIN :])
        self.codes = [str(code) for code in self.forecaster.product_ids]
        # Where each product's held-out weeks sit in the scored frame, so a plan
        # slices the same rows the cohort arithmetic already lines up.
        self.positions = {
            str(code): np.flatnonzero(self.scored["StockCode"].to_numpy() == code)
            for code in self.codes
        }
        self.manifest_codes = [str(code) for code in self.manifest["StockCode"]]

    # ── readiness ───────────────────────────────────────────────────────────

    def artifact_readiness(self) -> dict[str, bool]:
        readiness = {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
        readiness[fc.WEEKLY_CSV.name] = fc.WEEKLY_CSV.exists()
        return readiness

    @property
    def model_version(self) -> str:
        return str(self.card["version"])

    @property
    def policy_version(self) -> str:
        return str(self.policy["policy_version"])

    # ── shared cost arithmetic ──────────────────────────────────────────────

    def _ratio_note(self, ratio: float) -> str:
        if ratio == POLICY_RATIO:
            return (
                "The frozen operating policy: a unit not on the shelf is counted as "
                f"{POLICY_RATIO:g} times as costly as a unit left in the box, so the order "
                "is read at the 80% mark of this product's band."
            )
        return (
            f"A what-if at {_ratio_label(ratio)}, not the policy. The frozen operating "
            f"policy is {_ratio_label(POLICY_RATIO)}. Only a buyer's own operations and "
            "finance teams can say what these two costs really are."
        )

    def _cost_note(self, ratio: float) -> str:
        return (
            "CLASSROOM ASSUMPTION, not any real retailer's economics. A leftover unit "
            f"costs {fc.CO_FRACTION:.2f} x its price for a week of storage and markdown "
            f"risk; a unit not on the shelf costs {ratio:g} times that. Every dollar "
            "figure on this page is made of those two numbers."
        )

    # ── /api/forecast/products ──────────────────────────────────────────────

    def products(self, limit: int) -> list[ProductSummary]:
        rows = self.manifest.head(limit)
        return [self._product_summary(row) for _, row in rows.iterrows()]

    def _product_summary(self, row: pd.Series) -> ProductSummary:
        mean_units = float(row["test_mean_units"])
        band = float(row["band_high_mean"]) - float(row["band_low_mean"])
        change = float(row["cost_change_pct"])
        cheaper = bool(row["policy_is_cheaper"])
        return ProductSummary(
            product_id=str(row["StockCode"]),
            product=str(row["product"]),
            why_this_product=str(row["why_this_product"]),
            unit_price=float(row["unit_price"]),
            test_weeks=int(row["test_weeks"]),
            train_nonzero_share=float(row["train_nonzero_share"]),
            mean_units_per_week=mean_units,
            point_mean=float(row["point_mean"]),
            band_low_mean=float(row["band_low_mean"]),
            band_high_mean=float(row["band_high_mean"]),
            band_over_demand=float(row["band_over_demand"]),
            coverage=float(row["coverage"]),
            misses=int(row["misses"]),
            misses_above_band=int(row["misses_above_band"]),
            cost_point=float(row["cost_point"]),
            cost_quantile=float(row["cost_quantile"]),
            cost_change_pct=change,
            policy_is_cheaper=cheaper,
            demand_summary=(
                f"About {mean_units:,.0f} units a week over the {int(row['test_weeks'])} "
                f"held-out weeks, with a band about {band:,.0f} units wide - "
                f"{float(row['band_over_demand']):.2f} times a normal week."
            ),
            policy_outcome=(
                f"Ordering at the band instead of the forecast cost {abs(change):.1f}% "
                f"{'less' if cheaper else 'MORE'} over those weeks at the "
                f"{_ratio_label(POLICY_RATIO)} classroom ratio."
            ),
        )

    # ── /api/forecast/plan ──────────────────────────────────────────────────

    def plan(self, request: PlanRequest) -> PlanResponse:
        code = request.product_id
        if code not in self.manifest_codes:
            known = ", ".join(self.manifest_codes)
            raise ValueError(
                f"Unknown packaged product '{code}'. Known products: {known}."
            )
        row = self.manifest[self.manifest["StockCode"].astype(str) == code].iloc[0]

        ratio = POLICY_RATIO if request.cost_ratio is None else float(request.cost_ratio)
        critical = fc_policy.critical_ratio(ratio, 1.0)

        # Every array below is a slice of the same cohort-wide board the sweep
        # prices, so one product's plan and the 469-product total cannot disagree.
        where = self.positions[code]
        frame = self.scored.iloc[where]
        actual = self.board.actual[where]
        point = self.board.point[where]
        low = frame["low"].to_numpy(dtype=float)
        high = frame["high"].to_numpy(dtype=float)
        overstock = self.board.co[where]
        understock = ratio * overstock
        order_quantile = self.board.order_at(critical)[where]

        short_point = np.maximum(actual - point, 0.0)
        short_quantile = np.maximum(actual - order_quantile, 0.0)
        excess_point = np.maximum(point - actual, 0.0)
        excess_quantile = np.maximum(order_quantile - actual, 0.0)

        # The 26-week totals come back from fclab's own per-product roll-up rather
        # than being re-summed here. Adding the same 26 numbers in a different order
        # lands a floating-point hair away, which is enough to move a value sitting
        # exactly on a rounding boundary and make the published total disagree with
        # the manifest by 0.1 units.
        totals = self.board.per_product(ratio).set_index("StockCode").loc[code]
        cost_point = float(totals["cost_point"])
        cost_quantile = float(totals["cost_quantile"])
        change_pct = 100 * (cost_quantile - cost_point) / cost_point if cost_point else 0.0

        covered = (actual >= low) & (actual <= high)
        weeks = [str(pd.Timestamp(week).date()) for week in frame["week"]]

        history_weeks = self.train_weeks[-HISTORY_WEEKS:]
        history = [
            HistoryWeek(
                week=str(pd.Timestamp(week).date()),
                actual=round(float(self.panel.loc[code, week]), 1),
            )
            for week in history_weeks
        ]

        weekly = [
            PlanWeek(
                week=weeks[index],
                actual=round(float(actual[index]), 1),
                point=round(float(point[index]), 1),
                low=round(float(low[index]), 1),
                high=round(float(high[index]), 1),
                covered=bool(covered[index]),
                order_point=round(float(point[index]), 1),
                order_quantile=round(float(order_quantile[index]), 1),
                short_point=round(float(short_point[index]), 1),
                short_quantile=round(float(short_quantile[index]), 1),
                excess_point=round(float(excess_point[index]), 1),
                excess_quantile=round(float(excess_quantile[index]), 1),
            )
            for index in range(len(weeks))
        ]

        last = len(weeks) - 1
        latest = LatestWeek(
            week=weeks[last],
            actual=round(float(actual[last]), 1),
            point=round(float(point[last]), 1),
            low=round(float(low[last]), 1),
            high=round(float(high[last]), 1),
            band_width=round(float(high[last] - low[last]), 1),
            covered=bool(covered[last]),
            order_point=round(float(point[last]), 1),
            order_quantile=round(float(order_quantile[last]), 1),
            extra_units=round(float(order_quantile[last] - point[last]), 1),
        )

        return PlanResponse(
            product_id=code,
            product=str(row["product"]),
            why_this_product=str(row["why_this_product"]),
            unit_price=float(row["unit_price"]),
            weeks_planned=len(weeks),
            week_start=weeks[0],
            week_end=weeks[last],
            cost_ratio=ratio,
            critical_ratio=round(critical, 4),
            is_policy_ratio=ratio == POLICY_RATIO,
            ratio_note=self._ratio_note(ratio),
            overstock_cost_per_unit_week=round(float(overstock[0]), 4),
            understock_cost_per_unit=round(float(understock[0]), 4),
            cost_note=self._cost_note(ratio),
            history=history,
            weekly=weekly,
            latest=latest,
            point_plan=OrderOutcome(
                rule=POINT_RULE,
                plain_rule=POINT_PLAIN,
                quantile=None,
                units_ordered=round(float(totals["order_point"]), 1),
                units_short=round(float(totals["short_point"]), 1),
                units_excess=round(float(totals["excess_point"]), 1),
                cost=round(cost_point, 2),
                fill_rate=round(
                    float(1 - totals["short_point"] / totals["actual"])
                    if totals["actual"]
                    else 1.0,
                    4,
                ),
                weeks_short=int((short_point > 0).sum()),
                weeks_left_over=int((excess_point > 0).sum()),
            ),
            quantile_plan=OrderOutcome(
                rule=f"Order the band at the {critical:.0%} mark",
                plain_rule=QUANTILE_PLAIN_TEMPLATE.format(
                    share=critical * 100, ratio=ratio
                ),
                quantile=round(critical, 4),
                units_ordered=round(float(totals["order_quantile"]), 1),
                units_short=round(float(totals["short_quantile"]), 1),
                units_excess=round(float(totals["excess_quantile"]), 1),
                cost=round(cost_quantile, 2),
                fill_rate=round(
                    float(1 - totals["short_quantile"] / totals["actual"])
                    if totals["actual"]
                    else 1.0,
                    4,
                ),
                weeks_short=int((short_quantile > 0).sum()),
                weeks_left_over=int((excess_quantile > 0).sum()),
            ),
            cost_change_pct=round(change_pct, 2),
            policy_is_cheaper=cost_quantile < cost_point,
            saving=round(cost_point - cost_quantile, 2),
            coverage=round(float(covered.mean()), 4),
            misses=int((~covered).sum()),
            misses_above_band=int((actual > high).sum()),
            band_over_demand=round(
                float((high - low).mean() / max(float(actual.mean()), 1e-9)), 2
            ),
            mean_units_per_week=round(float(actual.mean()), 1),
            boundary=BOUNDARY_SHORT,
            forecast_note=FORECAST_NOTE,
            interval_note=INTERVAL_NOTE,
            model_version=self.model_version,
            policy_version=self.policy_version,
        )

    # ── /api/forecast/policy-sweep ──────────────────────────────────────────

    def policy_sweep(self, ratio: float | None, worst: int = 8) -> PolicySweepResponse:
        chosen = POLICY_RATIO if ratio is None else float(ratio)
        critical = fc_policy.critical_ratio(chosen, 1.0)

        # Recomputed through the notebook's own PolicyBoard every time, never read
        # from a stored table: the same three orders, priced over the same 12,194
        # held-out product-weeks, at whatever ratio was asked for.
        order = self.board.order_at(critical)
        quantile = self.board.evaluate(order, chosen)
        point = self.board.evaluate(self.board.point, chosen)
        mean = self.board.evaluate(self.board.train_mean, chosen)
        per_product = self.board.per_product(chosen)

        cheaper = per_product["saving"] > 0
        losers = per_product[~cheaper].sort_values("saving")
        winners = per_product[cheaper].sort_values("saving", ascending=False)

        weeks = [str(pd.Timestamp(week).date()) for week in self.test_weeks]
        return PolicySweepResponse(
            cost_ratio=chosen,
            critical_ratio=round(critical, 4),
            is_policy_ratio=chosen == POLICY_RATIO,
            ratio_note=self._ratio_note(chosen),
            products=int(len(per_product)),
            product_weeks=int(len(self.scored)),
            test_weeks=len(weeks),
            week_start=weeks[0],
            week_end=weeks[-1],
            quantile_plan=self._cohort_outcome(
                quantile,
                rule=f"Order the band at the {critical:.0%} mark",
                plain=QUANTILE_PLAIN_TEMPLATE.format(
                    share=critical * 100, ratio=chosen
                ),
            ),
            point_plan=self._cohort_outcome(point, rule=POINT_RULE, plain=POINT_PLAIN),
            mean_plan=self._cohort_outcome(mean, rule=MEAN_RULE, plain=MEAN_PLAIN),
            units_uplift_pct=round(
                100
                * (quantile["units_ordered"] - point["units_ordered"])
                / point["units_ordered"],
                2,
            ),
            vs_point_pct=round(100 * (quantile["cost"] - point["cost"]) / point["cost"], 2),
            vs_mean_pct=round(100 * (quantile["cost"] - mean["cost"]) / mean["cost"], 2),
            cheaper_than_point=quantile["cost"] < point["cost"],
            cheaper_than_mean=quantile["cost"] < mean["cost"],
            products_cheaper=int(cheaper.sum()),
            products_worse=int((~cheaper).sum()),
            products_worse_share=round(float((~cheaper).mean()), 4),
            extra_cost_on_losers=round(float(-losers["saving"].sum()), 2),
            worst_products=[self._losing_product(row) for _, row in losers.head(worst).iterrows()],
            best_products=[self._losing_product(row) for _, row in winners.head(5).iterrows()],
            cost_note=self._cost_note(chosen),
            boundary=BOUNDARY_SHORT,
            note=str(self.evaluation["policy"]["note"]),
        )

    def _cohort_outcome(self, outcome: dict, rule: str, plain: str) -> CohortOutcome:
        return CohortOutcome(
            rule=rule,
            plain_rule=plain,
            units_ordered=round(float(outcome["units_ordered"]), 1),
            units_short=round(float(outcome["shortfall_units"]), 1),
            units_excess=round(float(outcome["excess_units"]), 1),
            cost=round(float(outcome["cost"]), 2),
            fill_rate=round(float(outcome["fill_rate"]), 4),
            share_of_weeks_short=round(float(outcome["weeks_short"]), 4),
        )

    def _losing_product(self, row: pd.Series) -> LosingProduct:
        code = str(row["StockCode"])
        cost_point = float(row["cost_point"])
        cost_quantile = float(row["cost_quantile"])
        change = 100 * (cost_quantile - cost_point) / cost_point if cost_point else 0.0
        return LosingProduct(
            product_id=code,
            product=str(self.names.get(code, "")),
            cost_point=round(cost_point, 2),
            cost_quantile=round(cost_quantile, 2),
            extra_cost=round(cost_quantile - cost_point, 2),
            change_pct=round(change, 2),
            actual_units=round(float(row["actual"]), 1),
            ordered_units=round(float(row["order_quantile"]), 1),
            units_left_over=round(float(row["excess_quantile"]), 1),
        )

    # ── /api/forecast/model ─────────────────────────────────────────────────

    def model_info(self) -> ModelInfo:
        card, evaluation = self.card, self.evaluation
        held_out = evaluation["holdout_frozen"]
        mape = evaluation["mape_is_a_failure"]
        seasonal = evaluation["where_the_average_hides_a_failure"]
        dataset = card["training_data"]
        fitted = card["fitted_state"]
        policy = self.policy

        slices = _records(seasonal["seasonal_slices"])
        coverage_key = "Coverage (promised 80%)"
        worst = min(slices, key=lambda row: _percent(row.get(coverage_key)))

        return ModelInfo(
            model_name=card["model_name"],
            model_version=self.model_version,
            course=card["course"],
            model_type=card["model_type"],
            how_it_works=card["how_it_works"],
            intended_use=card["intended_use"],
            not_for=list(card["not_for"]),
            authority_boundary=card["authority_boundary"],
            boundary_short=BOUNDARY_SHORT,
            forecast_note=FORECAST_NOTE,
            interval_note=INTERVAL_NOTE,
            prohibited_claims=list(card["prohibited_claims"]),
            packaged_products=len(self.manifest),
            cohort_products=len(self.codes),
            residuals_per_product=int(fitted["residuals_per_product"]),
            median_unit_price=float(fitted["median_unit_price"]),
            dataset=DatasetInfo(
                dataset=dataset["dataset"],
                uci_id=int(dataset["uci_id"]),
                license=dataset["license"],
                doi=dataset["doi"],
                url=dataset["url"],
                citation=dataset["citation"],
                grain=dataset["grain"],
                training_window=list(dataset["training_window"]),
                cohort_rule=dataset["cohort_rule"],
                population=dataset["population"],
            ),
            evaluation=EvaluationSummary(
                held_out_window=list(card["evaluation"]["held_out_window"]),
                scored_once=bool(held_out["scored_once"]),
                rows=int(held_out["rows"]),
                products=int(held_out["products"]),
                test_weeks=int(held_out["test_weeks"]),
                mae_units=float(held_out["MAE"]),
                rmse_units=float(held_out["RMSE"]),
                mae_of_flat_zero=float(held_out["MAE_of_flat_zero"]),
                coverage_delivered=float(held_out["coverage_at_nominal_80"]),
                coverage_promised=float(policy["forecast_rule"]["nominal_coverage"]),
                median_band_units=float(held_out["median_band_units"]),
                band_over_median_demand=float(held_out["band_over_median_demand"]),
                pinball_10=float(held_out["pinball_10"]),
                pinball_50=float(held_out["pinball_50"]),
                pinball_90=float(held_out["pinball_90"]),
                metric_not_reported=card["evaluation"]["metric_not_reported"],
                mape_of_the_point_forecast=float(mape["MAPE_of_the_point_forecast"]),
                mape_of_a_flat_zero_forecast=float(mape["MAPE_of_a_flat_zero_forecast"]),
                mape_note=mape["note"],
            ),
            policy=PolicyInfo(
                policy_version=self.policy_version,
                decision=policy["decision"],
                plain_rule=(
                    "Decide what a stockout costs against what an overstock costs, turn "
                    "that into a percentage, and order the quantity at that point on this "
                    f"product's own band. At {_ratio_label(POLICY_RATIO)} the percentage "
                    "is 80%, so the order is the quantity that would have been enough in "
                    "80% of weeks. A planner approves it; the system never places it."
                ),
                critical_ratios={
                    str(key): float(value) for key, value in policy["critical_ratios"].items()
                },
                ratios_swept=[int(value) for value in policy["ratios_swept"]],
                overstock_formula=policy["overstock_cost_co"]["formula"],
                understock_formula=policy["understock_cost_cu"]["formula"],
                cost_assumption_note=policy["cost_assumption_note"],
                costs_are_classroom_assumptions=bool(policy["costs_are_classroom_assumptions"]),
                cohort_rule=(
                    f"A product is forecast only if it sold in at least "
                    f"{float(policy['cohort_rule']['min_nonzero_share']):.0%} of "
                    f"{policy['cohort_rule']['measured_on']}."
                ),
                cohort_size=int(policy["cohort_rule"]["size"]),
                products_refused=int(policy["cohort_rule"]["products_refused"]),
                window_weeks=int(policy["forecast_rule"]["window_weeks"]),
                nominal_low=float(policy["forecast_rule"]["nominal_low"]),
                nominal_high=float(policy["forecast_rule"]["nominal_high"]),
                nominal_coverage=float(policy["forecast_rule"]["nominal_coverage"]),
                horizon_weeks=int(policy["forecast_rule"]["horizon_weeks"]),
                train_window=list(policy["split"]["train"]),
                test_window=list(policy["split"]["test"]),
                human_authority=policy["human_authority"],
                prohibited_claims=list(policy["prohibited_claims"]),
                fallback=policy["fallback"],
                recalibration=policy["recalibration"],
            ),
            newsvendor_sweep=_records(evaluation["policy"]["newsvendor_sweep"]),
            interval_methods=_records(evaluation["interval_method_comparison"]),
            point_baselines=_records(evaluation["point_forecast_baselines"]),
            seasonal_coverage=SeasonalCoverage(
                slices=slices,
                ramp_months="October and November, the run-up to Christmas",
                worst_slice_coverage=_percent(worst.get(coverage_key)),
                worst_slice_label=str(worst.get("Slice", "")),
                misses_above_band_share=str(worst.get("Misses that were ABOVE the band", "")),
                note=seasonal["note"],
            ),
            per_product_outcomes=_records(evaluation["policy"]["per_product_outcomes"]),
            limitations=list(card["known_limitations"]),
            monitoring=card["monitoring"],
            environment={
                key: str(value) for key, value in evaluation.get("environment", {}).items()
            },
        )
