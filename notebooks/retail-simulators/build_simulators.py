"""Package the classroom models into two self-contained, offline simulators."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "notebooks/demand-forecasting"),
                str(ROOT / "notebooks/product-recommendations")]

from fclab import teaching as forecast_teaching
from reclab import models as recommendation_models
from reclab import teaching as recommendation_teaching


def json_safe(value):
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


CUSTOMER_BANDS = [(5, 8), (9, 14), (15, 24), (25, 40), (41, 80), (81, 200)]
CUSTOMER_PER_BAND = 2
DECK_CUSTOMER = 12349


def classroom_customers(split, photo_codes):
    """Pick a fixed, reproducible set of real customers spanning history sizes.

    Within each history-size band the customers with the most photographed
    products come first, ties broken by customer id, so the classroom list is
    deterministic and demonstrable. Selection never looks at whether the model
    ranks that customer well, so the set's hit rate is not stacked.

    Ground truth is the discovery set: products the customer bought after the
    cut and had never bought before it. The simulator hides a customer's own
    purchases from their ranking, so that is the only truth its ten slots can
    hit, and it is the protocol the 41.6% classroom figure comes from.
    """
    photographed = [code in photo_codes for code in split.items]
    chosen = []
    for low, high in CUSTOMER_BANDS:
        band = [user for user in split.truth_discovery if low <= len(split.seen[user]) <= high]
        band.sort(key=lambda user: (-sum(photographed[item] for item in split.seen[user]),
                                    int(split.users[user])))
        chosen.extend(band[:CUSTOMER_PER_BAND])
    chosen.append(split.user_index[DECK_CUSTOMER])
    chosen = sorted(set(chosen), key=lambda user: (len(split.seen[user]), int(split.users[user])))
    return [{"id": int(split.users[user]),
             "history": sorted(int(item) for item in split.seen[user]),
             "truth": sorted(int(item) for item in split.truth_discovery[user])}
            for user in chosen]


def recommendation_payload():
    lesson = recommendation_teaching.load_lesson()
    split = lesson.split
    model = recommendation_models.fit_item_item(split, neighbours=15)
    links = model.payload.tocsr()
    catalog = [[code, str(lesson.descriptions.get(code, code)), int(split.popularity[index])]
               for index, code in enumerate(split.items)]
    edges = [[[int(target), float(weight)] for target, weight in zip(
        links.indices[links.indptr[index]:links.indptr[index + 1]],
        links.data[links.indptr[index]:links.indptr[index + 1]])]
        for index in range(split.n_items)]
    fallback = [split.item_index[code] for code in recommendation_models.fallback_items(split)
                if code in split.item_index]
    starter_codes = ["85099B", "22112", "82494L", "84879", "22197"]
    starter = [split.item_index[code] for code in starter_codes]
    customer = split.user_index[12349]
    fixtures = []
    for history in [[], starter[:1], starter, sorted(split.seen[customer])]:
        scores = (split.R[customer] @ links).toarray().ravel() if history == sorted(split.seen[customer]) else np.asarray(links[history].sum(axis=0)).ravel()
        fixtures.append({"history": history, "scores": scores.tolist()})
    photo_codes = set(json.loads((HERE / "product-images.json").read_text())["products"])
    customers = classroom_customers(split, photo_codes)
    return {
        "kind": "recommendations", "catalog": catalog, "edges": edges,
        "fallback": fallback, "starter": starter, "customer": sorted(split.seen[customer]),
        "customers": customers, "defaultCustomer": DECK_CUSTOMER,
        "minHistory": 5, "cut": str(split.cut.date()), "fixtures": fixtures,
        "model": "Item-item cosine / 15 neighbors", "slots": 10,
        "hitRate": 0.4156, "baselineHitRate": 0.2947,
        "nTestCustomers": len(split.truth_discovery),
    }


def forecast_payload():
    lesson = forecast_teaching.load_lesson()
    design = lesson.design
    model = forecast_teaching.fit_final_model(design)
    trees = []
    for predictors in model._predictors:
        nodes = predictors[0].nodes
        if nodes["is_categorical"].any():
            raise ValueError("Browser export supports numeric splits only")
        trees.append([[int(node["feature_idx"]), float(node["num_threshold"]),
                       int(node["left"]), int(node["right"]),
                       int(node["missing_go_to_left"]), int(node["is_leaf"]), float(node["value"])]
                      for node in nodes])
    codes = ["85099B", "82494L", "35961", "84029E", "22112", "21484", "22197", "84879", "22084", "85099C"]
    products = [{"code": code, "name": str(lesson.names[code]),
                 "units": lesson.panel.loc[code].astype(float).tolist()}
                for code in codes]
    background = design["x_train"][np.random.default_rng(42).choice(len(design["x_train"]), 16, replace=False)]
    fixtures = np.asarray(design["x_test"])[np.linspace(0, len(design["x_test"]) - 1, 80, dtype=int)]
    fixtures = np.vstack([fixtures, design["x_train"][:8]])
    return json_safe({
        "kind": "forecast", "trees": trees, "bias": float(model._baseline_prediction[0, 0]),
        "features": design["features"], "products": products,
        "weeks": [str(week.date()) for week in design["weeks"]],
        "weekNumbers": [int(week.isocalendar().week) for week in design["weeks"]],
        "firstTest": 76, "background": background,
        "groups": [[0, 1, 2, 3, 4], [5, 6], [7], [8, 9, 10, 11]],
        "groupNames": ["Recent sales", "Recent averages", "Recent variation", "Seasonality"],
        "fixtures": [{"features": row, "prediction": float(max(0, prediction))}
                     for row, prediction in zip(fixtures, model.predict(fixtures))],
        "model": "Pooled histogram gradient boosting / absolute error",
        "nProducts": 469, "nFitRows": 31892, "nTrees": model.n_iter_,
    })


def product_photographs(payload):
    manifest = json.loads((HERE / "product-images.json").read_text())
    codes = {row[0] for row in payload["catalog"]} if "catalog" in payload else {
        product["code"] for product in payload["products"]}
    images = {}
    for code, record in manifest["products"].items():
        if code not in codes:
            continue
        photo = HERE / record["file"]
        with Image.open(photo) as image:
            image.verify()
        images[code] = {**record, "src": "data:image/webp;base64," +
                       base64.b64encode(photo.read_bytes()).decode()}
    return images, manifest["notice"]


def render(kind, payload, include_product_photos=False):
    payload["productImages"], payload["imageRights"] = product_photographs(payload) if include_product_photos else (
        {}, "Public build: merchant photographs are not distributed. Product names and stock codes identify the items; model calculations are unchanged.")
    serialized = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    template = (HERE / f"{kind}.html").read_text()
    icons = subprocess.check_output([
        "node", "--input-type=module", "-e",
        "import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; "
        "import * as icons from 'lucide-react'; const names=['ShoppingBag','ShoppingCart','Plus','Minus',"
        "'Undo2','RotateCcw','Search','ArrowLeft','ArrowRight','ChevronDown','X','BarChart3','Info',"
        "'Ban','Download','Check','SlidersHorizontal','ExternalLink','Maximize2','Play','Pause',"
        "'ChevronRight','Users','Sparkles','Target']; "
        "console.log(JSON.stringify(Object.fromEntries(names.map(name=>[name,"
        "renderToStaticMarkup(React.createElement(icons[name],{size:18,'aria-hidden':true}))]))));",
    ], cwd=ROOT, text=True)
    replacements = {"__STYLE__": (HERE / "style.css").read_text(),
                    "__ENGINE__": (HERE / "engine.js").read_text(),
                    "__COMMON__": (HERE / "common.js").read_text(),
                    "__PLOTLY__": get_plotlyjs(), "__DATA__": serialized,
                    "__ICONS__": icons.strip()}
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-only", type=Path)
    parser.add_argument("--only", choices=["forecast", "recommendations"])
    parser.add_argument("--include-product-photos", action="store_true",
                        help="Embed locally cached photos only when you have permission to distribute them")
    parser.add_argument("--reuse-export", action="store_true",
                        help="Repackage existing exported model data without fitting models again")
    args = parser.parse_args()
    for kind, loader, folder, name in [
        ("recommendations", recommendation_payload, "product-recommendations", "02_recommendation_simulator.html"),
        ("forecast", forecast_payload, "demand-forecasting", "02_forecast_simulator.html"),
    ]:
        if args.only and args.only != kind:
            continue
        destination = ROOT / "notebooks" / folder / "backup" / name
        if args.reuse_export:
            from bs4 import BeautifulSoup
            document = BeautifulSoup(destination.read_text(), "html.parser")
            payload = json.loads(document.find("script", id="model-data").string)
            if payload["kind"] != kind:
                raise ValueError("Saved model kind does not match its export")
        else:
            payload = loader()
        if args.payload_only:
            args.payload_only.mkdir(parents=True, exist_ok=True)
            destination = args.payload_only / f"{kind}.json"
            destination.write_text(json.dumps(payload, allow_nan=False))
        else:
            destination.write_text(render(kind, payload, args.include_product_photos))
        print(f"Built {destination} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()