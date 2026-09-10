"""From a range to an order: the newsvendor rule, priced.

A forecast does not tell you how many to buy. A cost ratio does.

    cu = what one unit SHORT costs you (a lost sale, a lost margin)
    co = what one unit LEFT OVER costs you (storage, markdown)
    critical ratio = cu / (cu + co)          -> order at that quantile

At 4:1 the critical ratio is 0.80, so you order the quantity you expect to be
enough in 80% of weeks. Every cost figure in this module is a labeled classroom
assumption: co = 0.10 x unit price per unit per week.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def critical_ratio(cu: float, co: float) -> float:
    """cu / (cu + co). The one line of arithmetic students do themselves."""
    return cu / (cu + co)


def unit_costs(forecaster, cohort, prices: pd.Series,
               fraction: float = config.CO_FRACTION) -> np.ndarray:
    """Overstock cost per unit per week for each product. CLASSROOM ASSUMPTION."""
    price = prices.reindex(cohort)
    return (fraction * price.fillna(price.median())).to_numpy()


class PolicyBoard:
    """Everything the newsvendor sweep needs, arranged once.

    Rows are held-out product-weeks in the same order as the scored frame, so
    every order quantity, cost and outcome below lines up with an actual.
    """

    def __init__(self, panel: pd.DataFrame, scored: pd.DataFrame, forecaster,
                 prices: pd.Series):
        self.cohort = list(forecaster.product_ids)
        self.index = {code: i for i, code in enumerate(self.cohort)}
        self.scored = scored
        self.actual = scored["actual"].to_numpy()
        self.point = np.maximum(scored["point"].to_numpy(), 0.0)
        self.rows = scored["StockCode"].map(self.index).to_numpy()
        self.weeks = scored["week"].to_numpy()
        self.residuals = [np.asarray(forecaster.residuals[code], dtype=float)
                          for code in self.cohort]
        self.co_unit = unit_costs(forecaster, self.cohort, prices)
        self.co = self.co_unit[self.rows]
        train_mean = panel.loc[self.cohort].iloc[:, :config.N_TRAIN].mean(axis=1)
        self.train_mean = np.maximum(train_mean.to_numpy()[self.rows], 0.0)

    # ── orders ──────────────────────────────────────────────────────────────
    def order_at(self, quantile: float) -> np.ndarray:
        """Order the band read at ``quantile``, clipped at zero."""
        offsets = np.array([np.quantile(r, quantile) for r in self.residuals])
        return np.maximum(self.point + offsets[self.rows], 0.0)

    # ── outcomes ────────────────────────────────────────────────────────────
    def evaluate(self, order: np.ndarray, ratio: float) -> dict:
        """What this order cost over the whole holdout, in classroom dollars."""
        cu = ratio * self.co
        short = np.maximum(self.actual - order, 0.0)
        excess = np.maximum(order - self.actual, 0.0)
        return {
            "units_ordered": float(order.sum()),
            "cost": float((cu * short + self.co * excess).sum()),
            "shortfall_units": float(short.sum()),
            "excess_units": float(excess.sum()),
            "fill_rate": float(1 - short.sum() / self.actual.sum()),
            "weeks_short": float((short > 0).mean()),
        }

    def sweep(self, ratios=config.RATIOS_SWEPT) -> pd.DataFrame:
        """The whole policy comparison: order the point, the mean, or the quantile."""
        rows = []
        for ratio in ratios:
            cr = critical_ratio(ratio, 1.0)
            point = self.evaluate(self.point, ratio)
            mean = self.evaluate(self.train_mean, ratio)
            quantile = self.evaluate(self.order_at(cr), ratio)
            rows.append({
                "ratio": f"{ratio}:1",
                "critical_ratio": round(cr, 3),
                "units_point": point["units_ordered"],
                "units_quantile": quantile["units_ordered"],
                "units_uplift_pct": 100 * (quantile["units_ordered"]
                                           - point["units_ordered"]) / point["units_ordered"],
                "cost_mean": mean["cost"],
                "cost_point": point["cost"],
                "cost_quantile": quantile["cost"],
                "vs_point_pct": 100 * (quantile["cost"] - point["cost"]) / point["cost"],
                "vs_mean_pct": 100 * (quantile["cost"] - mean["cost"]) / mean["cost"],
                "shortfall_point": point["shortfall_units"],
                "shortfall_quantile": quantile["shortfall_units"],
                "excess_point": point["excess_units"],
                "excess_quantile": quantile["excess_units"],
                "fill_point": point["fill_rate"],
                "fill_quantile": quantile["fill_rate"],
            })
        return pd.DataFrame(rows)

    def readable_sweep(self, sweep: pd.DataFrame) -> pd.DataFrame:
        """The sweep as it goes on a slide, in words a planner reads."""
        return pd.DataFrame({
            "Stockout : overstock": sweep["ratio"],
            "Critical ratio": sweep["critical_ratio"].map("{:.3f}".format),
            "Units ordered vs point": sweep["units_uplift_pct"].map("{:+.1f}%".format),
            "Cost, order the point": sweep["cost_point"].map("{:,.0f}".format),
            "Cost, order the quantile": sweep["cost_quantile"].map("{:,.0f}".format),
            "Change": sweep["vs_point_pct"].map("{:+.1f}%".format),
            "vs order-the-average": sweep["vs_mean_pct"].map("{:+.1f}%".format),
            "Units short": (sweep["shortfall_point"].map("{:,.0f}".format) + " -> "
                            + sweep["shortfall_quantile"].map("{:,.0f}".format)),
            "Units left over": (sweep["excess_point"].map("{:,.0f}".format) + " -> "
                                + sweep["excess_quantile"].map("{:,.0f}".format)),
            "Fill rate": (sweep["fill_point"].map("{:.3f}".format) + " -> "
                          + sweep["fill_quantile"].map("{:.3f}".format)),
        })

    def cost_curve(self, ratios=(4, 9),
                   quantiles=config.COST_CURVE_QUANTILES) -> pd.DataFrame:
        """Total cost at every order quantile, so the optimum is found, not claimed."""
        rows = []
        for ratio in ratios:
            for quantile in quantiles:
                rows.append({
                    "ratio": f"{ratio}:1",
                    "critical_ratio": critical_ratio(ratio, 1.0),
                    "order_quantile": quantile,
                    "cost": self.evaluate(self.order_at(quantile), ratio)["cost"],
                })
        curve = pd.DataFrame(rows)
        best = (curve.loc[curve.groupby("ratio")["cost"].idxmin()]
                .set_index("ratio")["order_quantile"])
        curve["is_minimum"] = [row.order_quantile == best[row.ratio]
                               for row in curve.itertuples()]
        return curve

    # ── per product ─────────────────────────────────────────────────────────
    def per_product(self, ratio: int = 4) -> pd.DataFrame:
        """Winners and losers, one row per product, over the whole holdout."""
        cr = critical_ratio(ratio, 1.0)
        order = self.order_at(cr)
        cu = ratio * self.co
        frame = pd.DataFrame({
            "StockCode": self.scored["StockCode"].to_numpy(),
            "actual": self.actual,
            "order_point": self.point,
            "order_quantile": order,
            "short_point": np.maximum(self.actual - self.point, 0.0),
            "short_quantile": np.maximum(self.actual - order, 0.0),
            "excess_point": np.maximum(self.point - self.actual, 0.0),
            "excess_quantile": np.maximum(order - self.actual, 0.0),
        })
        frame["cost_point"] = (cu * frame["short_point"]
                               + self.co * frame["excess_point"])
        frame["cost_quantile"] = (cu * frame["short_quantile"]
                                  + self.co * frame["excess_quantile"])
        grouped = frame.groupby("StockCode", as_index=False).sum(numeric_only=True)
        grouped["saving"] = grouped["cost_point"] - grouped["cost_quantile"]
        grouped["saving_pct"] = 100 * grouped["saving"] / grouped["cost_point"]
        grouped["ratio"] = f"{ratio}:1"
        return grouped.sort_values("saving", ascending=False).reset_index(drop=True)

    def outcome_split(self, ratios=(4, 9)) -> pd.DataFrame:
        """How often the policy is cheaper, and how often it is not."""
        rows = []
        for ratio in ratios:
            product = self.per_product(ratio)
            cheaper = product["saving"] > 0
            rows.append({
                "ratio": f"{ratio}:1",
                "products": int(len(product)),
                "cheaper": int(cheaper.sum()),
                "cheaper_share": float(cheaper.mean()),
                "more_expensive": int((~cheaper).sum()),
                # Two different "worst" products, reported separately on purpose.
                # per_product() is sorted by absolute dollars, so iloc[-1] is the
                # product that loses the most MONEY. The product that loses the
                # largest SHARE of its own cost is usually a different, much
                # smaller product. Reporting one product's code beside the other
                # one's percentage - which an earlier version of this function did
                # - pairs an identity with a ranking it did not win.
                "worst_by_dollars_product": product.iloc[-1]["StockCode"],
                "worst_by_dollars_change_pct": float(-product.iloc[-1]["saving_pct"]),
                "worst_by_dollars_extra_cost": float(-product.iloc[-1]["saving"]),
                "worst_by_percent_product": product.loc[product["saving_pct"].idxmin(), "StockCode"],
                "worst_by_percent_change_pct": float(-product["saving_pct"].min()),
            })
        return pd.DataFrame(rows)


def named(frame: pd.DataFrame, names: pd.Series, column: str = "StockCode",
          position: int = 1) -> pd.DataFrame:
    """Put the product's name beside its code, because codes teach nothing."""
    out = frame.copy()
    out.insert(position, "product", out[column].map(names).fillna(""))
    return out


def demo_table(product: pd.DataFrame, names: pd.Series, codes,
               prices: pd.Series) -> pd.DataFrame:
    """The named end-to-end walk: what each policy ordered and what it cost."""
    subset = product[product["StockCode"].isin(list(codes))].copy()
    subset["product"] = subset["StockCode"].map(names)
    subset["price"] = subset["StockCode"].map(prices)
    return pd.DataFrame({
        "Product": subset["product"],
        "Price": subset["price"].map("{:.2f}".format),
        "Actual units": subset["actual"].map("{:,.0f}".format),
        "Ordered (point)": subset["order_point"].map("{:,.0f}".format),
        "Ordered (80th pct)": subset["order_quantile"].map("{:,.0f}".format),
        "Units short": (subset["short_point"].map("{:,.0f}".format) + " -> "
                        + subset["short_quantile"].map("{:,.0f}".format)),
        "Units left over": (subset["excess_point"].map("{:,.0f}".format) + " -> "
                            + subset["excess_quantile"].map("{:,.0f}".format)),
        "Cost": (subset["cost_point"].map("{:,.0f}".format) + " -> "
                 + subset["cost_quantile"].map("{:,.0f}".format)),
        "Change": subset["saving_pct"].map("{:+.1f}%".format).str.replace("+", "-", 1)
        if False else (-subset["saving_pct"]).map("{:+.1f}%".format),
    })


def cost_assumptions(prices: pd.Series, cohort) -> pd.DataFrame:
    """The classroom assumptions, spelled out so nobody mistakes them for facts."""
    median_price = float(prices.reindex(cohort).median())
    rows = [
        ("Median unit price in the cohort", f"{median_price:.2f}",
         "Measured from the data."),
        ("Overstock cost co", f"{config.CO_FRACTION:.2f} x unit price "
                              f"= {config.CO_FRACTION * median_price:.3f} per unit per week",
         "CLASSROOM ASSUMPTION: one week of storage plus markdown risk."),
        ("Understock cost cu at 4:1", f"{4 * config.CO_FRACTION:.2f} x unit price "
                                      f"= {4 * config.CO_FRACTION * median_price:.3f} per unit",
         "A 40% gross margin lost on every unit not on the shelf. This is why "
         "4:1 is the headline ratio: a student can derive it."),
        ("Understock cost cu at 9:1", f"{9 * config.CO_FRACTION:.2f} x unit price "
                                      f"= {9 * config.CO_FRACTION * median_price:.3f} per unit",
         "90% of the selling price. Beyond about 10:1 the implied cost of a "
         "stockout exceeds the price of the item, which only makes sense if "
         "losing the customer costs more than losing the sale."),
    ]
    return pd.DataFrame(rows, columns=["Parameter", "Value", "Where it comes from"])
