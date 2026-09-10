"""Choosing which products to model, and the one design matrix we only compare with.

The deployed path has no engineered feature matrix at all: an 8-week moving
average reads the panel directly. The matrix built here exists so the gradient
booster in ``intervals.py`` has something to learn from, and so the comparison
is fair.

The important function in this file is ``select_cohort``. It takes the training
weeks only. ``leaky_cohort`` takes all 102 weeks and is here to be shown as a
mistake, not used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

LAGS = (1, 2, 3, 4, 8)
FEATURE_NAMES = ([f"lag{lag}" for lag in LAGS]
                 + ["ma4", "ma8", "std4", "lag52", "woy_sin", "woy_cos", "woy"])


def nonzero_share(panel: pd.DataFrame, columns: pd.Index | None = None) -> pd.Series:
    """Share of weeks in which this product sold at least one unit.

    Numerator: weeks with units > 0. Denominator: the weeks passed in.
    """
    block = panel if columns is None else panel[columns]
    return (block > 0).mean(axis=1)


def select_cohort(panel: pd.DataFrame,
                  min_nonzero: float = config.COHORT_MIN_NONZERO) -> pd.Index:
    """Products that sold in at least ``min_nonzero`` of the TRAINING weeks.

    Training weeks only. This is the whole point: a cohort chosen with the test
    weeks in view has already read the answer sheet.
    """
    train = panel.columns[: config.N_TRAIN]
    share = nonzero_share(panel, train)
    return share[share >= min_nonzero].index


def leaky_cohort(panel: pd.DataFrame,
                 min_nonzero: float = config.COHORT_MIN_NONZERO) -> pd.Index:
    """The same rule applied to all 102 weeks. Shown as a mistake, never used."""
    share = nonzero_share(panel)
    return share[share >= min_nonzero].index


def cohort_rule_comparison(panel: pd.DataFrame) -> pd.DataFrame:
    """Four candidate rules side by side, so the leak is visible as a count."""
    train = panel.columns[: config.N_TRAIN]
    honest = select_cohort(panel)
    leaky = leaky_cohort(panel)
    wider = select_cohort(panel, 0.80)
    rows = [
        (">= 90% non-zero over all 102 weeks", "all 102 weeks",
         len(leaky), "LEAKY - do not use"),
        (">= 90% non-zero over the 76 train weeks", "76 train weeks",
         len(honest), "adopted"),
        (">= 80% non-zero over the 76 train weeks", "76 train weeks",
         len(wider), "considered, wider and noisier"),
        ("no rule - model the whole catalog", "-",
         panel.shape[0], "rejected: 69% of products are mostly zeros"),
    ]
    frame = pd.DataFrame(rows, columns=["Cohort rule", "Weeks the rule reads",
                                        "Products", "Verdict"])
    frame["Share of catalog units"] = [
        f"{panel.loc[idx].values.sum() / panel.values.sum():.1%}"
        for idx in (leaky, honest, wider, panel.index)
    ]
    return frame


def leakage_evidence(panel: pd.DataFrame) -> dict:
    """What the leaky rule actually bought itself, in products and in weeks."""
    honest = set(select_cohort(panel))
    leaky = set(leaky_cohort(panel))
    only_leaky = leaky - honest
    only_honest = honest - leaky
    test = panel.columns[config.N_TRAIN:]
    return {
        "honest_size": len(honest),
        "leaky_size": len(leaky),
        "in_both": len(honest & leaky),
        "only_in_leaky": len(only_leaky),
        "only_in_honest": len(only_honest),
        "leaky_test_nonzero_share": float(
            nonzero_share(panel.loc[sorted(leaky)], test).mean()),
        "honest_test_nonzero_share": float(
            nonzero_share(panel.loc[sorted(honest)], test).mean()),
        "only_leaky_test_nonzero_share": float(
            nonzero_share(panel.loc[sorted(only_leaky)], test).mean())
        if only_leaky else float("nan"),
        "only_honest_test_nonzero_share": float(
            nonzero_share(panel.loc[sorted(only_honest)], test).mean())
        if only_honest else float("nan"),
    }


def cohort_stats(panel: pd.DataFrame, cohort: pd.Index) -> pd.DataFrame:
    """What the cohort is, and what choosing it costs us."""
    block = panel.loc[cohort]
    test = panel.columns[config.N_TRAIN:]
    values = block.values.ravel()
    catalog_zero = float(1 - nonzero_share(panel).median())
    rows = [
        ("Products in the cohort", f"{len(cohort):,} of {panel.shape[0]:,} "
                                   f"({len(cohort) / panel.shape[0]:.1%} of the catalog)"),
        ("Product-weeks the cohort contributes", f"{values.size:,}"),
        ("Share of all catalog units", f"{block.values.sum() / panel.values.sum():.1%}"),
        ("Mean units per product-week", f"{values.mean():.1f}"),
        ("Median / 25th / 75th percentile", f"{np.median(values):.0f} / "
                                            f"{np.percentile(values, 25):.0f} / "
                                            f"{np.percentile(values, 75):.0f}"),
        ("Largest single product-week", f"{values.max():,.0f} units"),
        ("The median product's median week", f"{block.median(axis=1).median():.1f} units"),
        ("Weeks with a sale, TEST window", f"{nonzero_share(block, test).mean():.1%}"),
        ("Zero-week share of the median CATALOG product", f"{catalog_zero:.1%}"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def intermittent_set(panel: pd.DataFrame,
                     band: tuple[float, float] = config.INTERMITTENT_BAND) -> pd.Index:
    """Products selling in 35-50% of training weeks. Never deployed.

    This set exists to show what the method cannot do, and to carry the MAPE
    demonstration in Stage 4.
    """
    share = nonzero_share(panel, panel.columns[: config.N_TRAIN])
    return share[(share >= band[0]) & (share <= band[1])].index


def zero_week_histogram(panel: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Distribution of each product's zero-week share across the whole catalog."""
    zero_share = 1 - nonzero_share(panel)
    edges = np.linspace(0, 1, bins + 1)
    counts, _ = np.histogram(zero_share, bins=edges)
    return pd.DataFrame({
        "zero_share_low": edges[:-1],
        "zero_share_high": edges[1:],
        "products": counts,
        "share_of_catalog": counts / len(zero_share),
    })


def q4_skew(panel: pd.DataFrame, cohort: pd.Index) -> pd.Series:
    """Oct-Dec mean weekly units divided by Jan-Sep mean, per product.

    A product-level seasonality measure. The aggregate figure hides it: the
    catalog runs about 1.6x in the autumn while single products run 9x.
    """
    months = np.array([week.month for week in panel.columns])
    block = panel.loc[cohort]
    high = block.loc[:, months >= 10].mean(axis=1)
    low = block.loc[:, months < 10].mean(axis=1).replace(0, np.nan)
    return (high / low).dropna().sort_values(ascending=False)


def seasonality_summary(panel: pd.DataFrame, cohort: pd.Index) -> pd.DataFrame:
    """The aggregate seasonal story and the product-level one, in one table."""
    totals = panel.sum(axis=0)
    months = np.array([week.month for week in totals.index])
    autumn = totals[np.isin(months, (9, 10, 11))]
    rest = totals[np.isin(months, range(1, 9))]
    skew = q4_skew(panel, cohort)
    rows = [
        ("Median catalog week", f"{totals.median():,.0f} units"),
        ("Largest complete week", f"{totals.idxmax().date()} = "
                                  f"{totals.max():,.0f} units "
                                  f"({totals.max() / totals.median():.2f}x median)"),
        ("Sep-Nov mean vs Jan-Aug mean", f"{autumn.mean():,.0f} vs {rest.mean():,.0f} "
                                         f"= {autumn.mean() / rest.mean():.2f}x"),
        ("Most Q4-skewed cohort product", f"{skew.index[0]}: {skew.iloc[0]:.2f}x"),
        ("Median cohort product's Q4 skew", f"{skew.median():.2f}x"),
    ]
    return pd.DataFrame(rows, columns=["Measure", "Value"])


# ── The comparison-only design matrix ───────────────────────────────────────

def design_matrix(panel: pd.DataFrame, cohort: pd.Index) -> dict:
    """One row per (product, target week) with lag and calendar features.

    Used only by the gradient-boosting and conformal comparisons in Stage 4.
    The deployed forecaster never sees this matrix.
    """
    block = panel.loc[cohort]
    weeks = list(block.columns)
    values = block.values.astype(float)
    n_products, n_weeks = values.shape

    def build(targets: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        blocks, actuals, week_index = [], [], []
        for t in targets:
            columns = {f"lag{lag}": values[:, t - lag] for lag in LAGS}
            columns["ma4"] = values[:, t - 4:t].mean(axis=1)
            columns["ma8"] = values[:, max(0, t - config.WINDOW):t].mean(axis=1)
            columns["std4"] = values[:, t - 4:t].std(axis=1)
            columns["lag52"] = (values[:, t - 52] if t >= 52
                                else np.full(n_products, np.nan))
            week_of_year = weeks[t].isocalendar()[1]
            columns["woy_sin"] = np.full(n_products, np.sin(2 * np.pi * week_of_year / 52))
            columns["woy_cos"] = np.full(n_products, np.cos(2 * np.pi * week_of_year / 52))
            columns["woy"] = np.full(n_products, float(week_of_year))
            blocks.append(np.column_stack([columns[name] for name in FEATURE_NAMES]))
            actuals.append(values[:, t])
            week_index.append(np.full(n_products, t))
        return (np.vstack(blocks), np.concatenate(actuals), np.concatenate(week_index))

    train_targets = list(range(config.WINDOW, config.N_TRAIN))
    test_targets = list(range(config.N_TRAIN, n_weeks))
    x_train, y_train, t_train = build(train_targets)
    x_test, y_test, t_test = build(test_targets)
    return {
        "features": FEATURE_NAMES,
        "x_train": x_train, "y_train": y_train, "t_train": t_train,
        "x_test": x_test, "y_test": y_test, "t_test": t_test,
        "product_train": np.tile(np.arange(n_products), len(train_targets)),
        "product_test": np.tile(np.arange(n_products), len(test_targets)),
        "weeks": weeks, "cohort": list(cohort),
    }
