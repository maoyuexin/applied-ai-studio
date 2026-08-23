"""fraudlab -- helpers for the ITAI 2372 fraud-detection build notebook.

The notebook stays readable because the work lives here. Each module has one job:

    config    paths, dates, and the business constants everything else quotes
    data      loading, joining, label maturity, and the time-ordered split
    features  feature engineering -- the one definition, shared with serving
    charts    every Plotly figure, returned rather than shown
    metrics   the confusion matrix and everything read off it
    models    the candidates, the balancing bake-off, and the sweep
    handoff   the three artefacts the scoring service consumes
"""

from . import charts, config, data, features, handoff, metrics, models

__all__ = ["charts", "config", "data", "features", "handoff", "metrics", "models"]
