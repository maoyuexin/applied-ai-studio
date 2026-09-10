"""Export and verify the narrow artifact contract the storefront service consumes.

Six files leave the notebook, and nothing else:

- ``item_similarity.npz``    the deployed ranking model: item-item cosine
                             truncated to 15 neighbours, scipy CSR, float32
- ``item_catalog.parquet``   one row per product: matrix column, stock code,
                             description, training customers, popularity rank
- ``model_card.json``        intended use, provenance, both leaderboards, limits
- ``evaluation.json``        every number the notebook printed, under BOTH protocols
- ``operating_policy.json``  ten slots, eligibility, the fallback list, the
                             boundary statement and the prohibited claims
- ``sample_manifest.parquet`` the packaged demo customers, including the two the
                             model serves badly and the two it cannot serve at all

Three things are deliberately **not** exported.

The customer x product matrix is not. It is 390,571 cells of one retailer's
purchase history; it is stale the day after it is written, and a service that
recommends from a frozen copy of last quarter's baskets is lying about what it
knows. The service owns its own customer history and multiplies it against the
similarity matrix at request time - which is exactly what ``verify`` does, by
rebuilding the matrix from the committed interaction log rather than from
anything this module wrote.

The full dense similarity matrix is not. At 4,443 x 4,443 float32 it is 79.0 MB,
and truncating it to 15 neighbours per product costs 0.26 MB, shrinks it 310x
and *raises* discovery HR@10 from 0.3644 to 0.4156. The small artifact is also
the accurate one here. That is unusual and it is measured, not assumed.

And the SVD model is not exported at all. It scores 0.0281 higher on discovery
HR@10 and it cannot answer "why am I seeing this?" with the name of a product
the customer bought. It stays in the leaderboard, where the comparison is the
point, and out of the service.

``verify`` reloads the artifacts from disk, rebuilds the matrix from the
committed log, and re-ranks 200 customers, requiring the ten stock codes in
every slot to be identical to the ones recorded at export.
"""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy
import scipy.sparse as sp
import sklearn

from . import config, data, evaluate, matrix, models

SIMILARITY = "item_similarity.npz"
CATALOG = "item_catalog.parquet"
MODEL_CARD = "model_card.json"
EVALUATION = "evaluation.json"
POLICY = "operating_policy.json"
SAMPLES = "sample_manifest.parquet"

ARTIFACT_ORDER = [SIMILARITY, CATALOG, MODEL_CARD, EVALUATION, POLICY, SAMPLES]

_PURPOSE = {
    SIMILARITY: "Ranks products for one shopper: history row @ similarity matrix",
    CATALOG: "Turns a matrix column back into a stock code and a product name",
    MODEL_CARD: "Shown to reviewers; states what the system will not do",
    EVALUATION: "Every measured number under both protocols, for governance",
    POLICY: "Slots, eligibility, fallback list and labels, read at startup",
    SAMPLES: "The packaged demo customers served in the classroom app",
}


# ── The reload baseline ─────────────────────────────────────────────────────

def reload_users(split: matrix.Split,
                 count: int = config.RELOAD_CHECK_USERS) -> list[int]:
    """The fixed customers the reload check re-ranks.

    The discovery-protocol population, sorted by customer id and truncated, so
    a fresh process picks exactly the same 200 customers from the committed
    parquet without being told which ones.
    """
    ordered = sorted(split.users[row] for row in split.truth_discovery)
    return ordered[:count]


def baseline_top10(split: matrix.Split, fitted: models.Fitted,
                   customers: list[int]) -> dict[str, list[str]]:
    """Ten stock codes per customer, recorded before export.

    Stock codes, not column indices: an index is only meaningful against the
    catalog it was built with, and the whole point of the check is that the
    reloaded artifacts stand on their own.
    """
    rows = [split.user_index[customer] for customer in customers]
    top = evaluate.ranked_lists(split, fitted, config.PROTOCOL_DISCOVERY, rows)
    return {str(customer): [split.items[int(i)] for i in top[split.user_index[customer]]]
            for customer in customers}


def similarity_digest(similarity: sp.csr_matrix) -> str:
    """SHA-256 over the stored CSR arrays: any changed link changes the digest."""
    digest = hashlib.sha256()
    for array in (np.asarray(similarity.data, np.float32),
                  np.asarray(similarity.indices, np.int32),
                  np.asarray(similarity.indptr, np.int32)):
        digest.update(array.tobytes())
    return digest.hexdigest()


# ── The exported tables ─────────────────────────────────────────────────────

def build_catalog(split: matrix.Split, descriptions: pd.Series) -> pd.DataFrame:
    """One row per matrix column, so a column index becomes a product again."""
    return pd.DataFrame({
        "item_index": np.arange(split.n_items, dtype=np.int32),
        "stock_code": split.items,
        "description": [str(descriptions.get(code, "")) for code in split.items],
        "training_customers": split.popularity.astype(np.int32),
        "popularity_rank": split.popularity_rank.astype(np.int32),
    })


def select_samples(split: matrix.Split, fitted: dict[str, models.Fitted],
                   count: int = config.SAMPLE_COUNT) -> list[tuple[str, int]]:
    """Choose the demo customers by measurement, not by taste.

    Every persona below is a rule someone else can re-run: the longest history,
    the best discovery result, the median, the thinnest servable history. The
    one hand-picked entry is the discussion customer named in ``config``, and it
    is named there precisely so it is visible rather than buried in a notebook.
    """
    servable = sorted(split.truth_discovery)
    history = np.asarray(split.R.sum(1)).ravel()
    deployed = fitted[config.DEPLOYED_MODEL_LABEL]
    top = evaluate.ranked_lists(split, deployed, config.PROTOCOL_DISCOVERY, servable)
    hits = {row: len(set(top[row].tolist()) & split.truth_discovery[row])
            for row in servable}

    chosen: list[tuple[str, int]] = []
    seen: set[int] = set()

    def take(label: str, row: int | None) -> None:
        if row is None or row in seen or len(chosen) >= count:
            return
        seen.add(row)
        chosen.append((label, int(row)))

    discussion = split.user_index.get(config.DISCUSSION_CUSTOMER)
    take("Discussion case: a wholesaler restocking, not a shopper browsing",
         discussion if discussion in split.truth_discovery else None)
    take("Longest training history in the matrix",
         max(servable, key=lambda row: history[row]))
    take("Best discovery result in the test window",
         max(servable, key=lambda row: (hits[row], -history[row])))
    take("Long history, no discovery hits at all",
         max((row for row in servable if hits[row] == 0),
             key=lambda row: history[row], default=None))
    take("Thinnest history that still clears the five-product threshold",
         min(servable, key=lambda row: (history[row], row)))
    take("Bought the most products new to them after the cut",
         max(servable, key=lambda row: len(split.truth_discovery[row])))
    ordered = sorted(servable, key=lambda row: (history[row], row))
    take("Typical customer: the median training history",
         ordered[len(ordered) // 2])
    for share in (0.25, 0.75, 0.10, 0.90, 0.40, 0.60):
        take(f"History at the {share:.0%} percentile of servable customers",
             ordered[int(share * (len(ordered) - 1))])
    return chosen[:count]


def build_samples(split: matrix.Split, descriptions: pd.Series,
                  fitted: dict[str, models.Fitted],
                  count: int = config.SAMPLE_COUNT) -> pd.DataFrame:
    """The packaged demo customers, with what each model would actually show them.

    Each row carries the ten slots the deployed model fills under the discovery
    policy, the ten the reorder baseline fills under the standard protocol, and
    the hit counts for both - so the app can show the same customer winning one
    table and losing the other without recomputing anything.
    """
    picks = select_samples(split, fitted, count)
    rows = [row for _, row in picks]
    deployed = evaluate.ranked_lists(split, fitted[config.DEPLOYED_MODEL_LABEL],
                                     config.PROTOCOL_DISCOVERY, rows)
    reorder = evaluate.ranked_lists(split, fitted[config.REORDER_LABEL],
                                    config.PROTOCOL_STANDARD, rows)
    counted = split.train_rows.assign(
        u=split.train_rows["customer_id"].map(split.user_index)).dropna(subset=["u"])
    baskets = counted.astype({"u": int}).groupby("u")["invoice"].nunique().to_dict()

    records = []
    for label, row in picks:
        slots = [split.items[int(i)] for i in deployed[row]]
        again = [split.items[int(i)] for i in reorder[row]]
        records.append({
            "persona": label,
            "customer_id": int(split.users[row]),
            "training_products": int(split.R[row].nnz),
            "training_baskets": int(baskets.get(row, 0)),
            "bought_after_the_cut": int(len(split.truth_standard.get(row, ()))),
            "new_to_them_after_the_cut": int(len(split.truth_discovery.get(row, ()))),
            "recommended_for_you": slots,
            "recommended_descriptions": [str(descriptions.get(code, "")) for code in slots],
            "discovery_hits_out_of_10":
                int(len(set(deployed[row].tolist()) & split.truth_discovery.get(row, set()))),
            "buy_it_again": again,
            "reorder_hits_out_of_10_standard":
                int(len(set(reorder[row].tolist()) & split.truth_standard.get(row, set()))),
        })
    return pd.DataFrame(records)


# ── evaluation.json ─────────────────────────────────────────────────────────

def _clean(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _round(records, places: int = 4):
    """A DataFrame or list of dicts, as JSON-safe records with floats rounded."""
    if isinstance(records, pd.DataFrame):
        records = records.to_dict("records")
    output = []
    for record in records:
        row = {}
        for key, value in record.items():
            value = _clean(value)
            row[str(key)] = round(value, places) if isinstance(value, float) else value
        output.append(row)
    return output


def _dict(payload: dict) -> dict:
    return {key: _clean(value) for key, value in payload.items()}


def assemble_evidence(
    split: matrix.Split,
    ledger: dict,
    repeat_profile: dict,
    concentration: dict,
    standard: pd.DataFrame,
    discovery: pd.DataFrame,
    comparison: pd.DataFrame,
    zero_diagnosis: dict,
    revenue: pd.DataFrame,
    cold: dict,
    outcomes: dict,
    reload_check: dict,
    incoherent: pd.DataFrame | None = None,
    exposure: pd.DataFrame | None = None,
    loop: pd.DataFrame | None = None,
    inflation: pd.DataFrame | None = None,
    truncation: pd.DataFrame | None = None,
    damping: pd.DataFrame | None = None,
    fallback_sweep: pd.DataFrame | None = None,
) -> dict:
    """The complete ``evaluation.json`` payload, in one place.

    Everything the notebook prints is here, so a reader who never opens the
    notebook can still audit the claim, and so a printed number that drifts
    from the exported one is a visible contradiction rather than a private one.
    Both leaderboards are always present. There is no argument that makes one
    of them optional.
    """
    payload = {
        "dataset": {
            "name": config.DATASET_NAME,
            "uci_id": config.DATASET_UCI_ID,
            "license": config.DATASET_LICENSE,
            "citation": config.DATASET_CITATION,
            "population": config.DATASET_POPULATION,
            "raw_rows": ledger["raw_rows"],
            "clean_rows": ledger["clean_rows"],
            "committed_rows": ledger["committed_rows"],
            "committed_grain": ledger["committed_grain"],
            "sibling_lab": {"path": config.SIBLING_LAB,
                            "its_question": config.SIBLING_QUESTION,
                            "our_question": config.OUR_QUESTION},
        },
        "split": {
            "type": "global time split - never random",
            "cut": str(config.SPLIT_CUT.date()),
            "min_training_products_per_customer": config.MIN_TRAIN_ITEMS_PER_USER,
            "users": split.n_users,
            "items": split.n_items,
            "training_pairs": int(split.R.nnz),
            "sparsity": round(1 - split.R.nnz / (split.n_users * split.n_items), 5),
            "customers_scored_standard": len(split.truth_standard),
            "customers_scored_discovery": len(split.truth_discovery),
            "why_not_random": (
                "A random split puts December's baskets in training and "
                "September's in test. No one can ask that question in "
                "production, and the model has seen the future it is graded on."),
        },
        "repeat_purchasing": _dict(repeat_profile),
        "concentration": _dict(concentration),
        "protocols": config.PROTOCOL_DEFINITIONS,
        "leaderboards": {
            "standard": _round(standard),
            "discovery": _round(discovery),
            "side_by_side": _round(comparison),
            "reorder_zero_score_diagnosis": _dict(zero_diagnosis),
            "rule": ("Coverage and novelty are printed beside every accuracy "
                     "number, always. Neither leaderboard is optional."),
        },
        "incremental_revenue": {
            "available_new_product_revenue":
                round(float(revenue.attrs.get("available_revenue", float("nan"))), 2),
            "customers": int(revenue.attrs.get("customers", 0)),
            "by_model": _round(revenue),
            "boundary": config.CLAIM_BOUNDARY,
        },
        "cold_start": _dict(cold),
        "policy": {
            "slots": config.SLOTS,
            "eligibility": config.ELIGIBILITY,
            "fallback_rule": config.FALLBACK_RULE,
            "outcomes": _dict(outcomes),
        },
        "reload_check": reload_check,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "seed": config.SEED,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }
    if incoherent is not None:
        payload["leaderboards"]["incoherent_middle"] = _round(incoherent)
    if exposure is not None or loop is not None:
        payload["popularity_bias"] = {}
        if exposure is not None:
            payload["popularity_bias"]["what_each_model_shows"] = _round(exposure)
        if loop is not None:
            payload["popularity_bias"]["exposure_loop"] = {
                "rounds": config.FEEDBACK_ROUNDS,
                "assumed_conversion": config.FEEDBACK_CONVERSION,
                "assumption_note": config.FEEDBACK_ASSUMPTION_NOTE,
                "history": _round(loop, 5),
            }
    if inflation is not None:
        payload["leave_one_out"] = {
            "design": ("Targets fixed at one product per customer. Only the "
                       "training data changes, so the gap is the leak."),
            "by_model": _round(inflation),
        }
    if truncation is not None or damping is not None:
        payload["engineering"] = {}
        if truncation is not None:
            payload["engineering"]["truncation_trade"] = _round(truncation)
        if damping is not None:
            payload["engineering"]["popularity_damping_is_a_no_op"] = _round(damping, 6)
    if fallback_sweep is not None:
        payload["policy"]["fallback_sweep"] = _round(fallback_sweep)
    return payload


def build_model_card(evidence: dict, catalog: pd.DataFrame) -> dict:
    """What this thing is for, what it was measured at, and where it fails."""
    standard = {row["Model"]: row for row in evidence["leaderboards"]["standard"]}
    discovery = {row["Model"]: row for row in evidence["leaderboards"]["discovery"]}
    revenue = {row["Model"]: row for row in
               evidence["incremental_revenue"]["by_model"]}
    deployed = config.DEPLOYED_MODEL_LABEL
    return {
        "name": "Product recommendation - discovery ranking for one storefront slot",
        "version": f"{config.DATASET_NAME} split {config.SPLIT_CUT.date()}",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "deployed_model": {
            "id": config.DEPLOYED_MODEL,
            "label": deployed,
            "how_it_works": config.MODEL_ONE_LINERS[deployed],
            "neighbours_kept": config.ITEM_NEIGHBOURS,
            "scoring": "one sparse matrix multiply: the customer's history row @ S",
            "why_not_the_most_accurate_model": (
                f"{config.SVD_LABEL} scores "
                f"{discovery[config.SVD_LABEL]['HR@10'] - discovery[deployed]['HR@10']:.4f} "
                "higher on discovery HR@10 and cannot say why a product is in the "
                "list. Item-item can name the product the customer already bought. "
                "It also covers more of the catalog and ships in 0.26 MB."),
        },
        "what_it_does": (
            "Given a customer who has bought at least "
            f"{config.MIN_TRAIN_ITEMS_PER_USER} distinct products, it ranks "
            "products that customer has NEVER bought and fills "
            f"{config.SLOTS} slots under the heading "
            f'"{config.MODULE_TITLE}".'),
        "what_it_does_not_do": [
            "It does not decide what a shopper needs.",
            "It does not measure revenue. Its scores are offline ranking scores.",
            "It does not choose placement or exclusions - merchandisers do.",
            'It does not fill the "Buy it again" strip, and reorders are never '
            "counted as personalization.",
            "It does not serve customers with no history. They get a labeled "
            "generic list instead, and the label says so.",
        ],
        "boundary": config.CLAIM_BOUNDARY_LONG,
        "prohibited_claims": config.PROHIBITED_CLAIMS,
        "intended_users": (
            "Merchandising and analytics staff who own the storefront module and "
            "the exclusion list. Every list it produces is shown inside rules a "
            "person set."),
        "data": {
            "source": config.DATASET_NAME,
            "license": config.DATASET_LICENSE,
            "citation": config.DATASET_CITATION,
            "population": config.DATASET_POPULATION,
            "products_in_the_catalog": int(len(catalog)),
            "customers_in_the_matrix": evidence["split"]["users"],
            "split": evidence["split"]["cut"],
            "sparsity": evidence["split"]["sparsity"],
        },
        "measured": {
            "protocols_reported": ["standard next-purchase", "discovery"],
            "standard_next_purchase": {name: row["HR@10"] for name, row in standard.items()},
            "discovery": {name: row["HR@10"] for name, row in discovery.items()},
            "deployed_discovery_HR@10": discovery[deployed]["HR@10"],
            "deployed_discovery_coverage": discovery[deployed]["Coverage"],
            "deployed_share_of_new_product_revenue":
                revenue[deployed]["Share of available new-product revenue"],
            "no_personalization_share_of_new_product_revenue":
                revenue[config.FALLBACK_LABEL]["Share of available new-product revenue"],
            "customers_who_cannot_be_personalized":
                evidence["cold_start"]["unservable_share"],
        },
        "known_limits": [
            "The reorder baseline wins every accuracy metric on the standard "
            f"protocol ({standard[config.REORDER_LABEL]['HR@10']:.4f} against "
            f"{standard[deployed]['HR@10']:.4f}) and finishes below ten random "
            f"products on discovery ({discovery[config.REORDER_LABEL]['HR@10']:.4f} "
            "against 0.0604). Both numbers are real. They encode two different "
            "definitions of success, and a leaderboard without its protocol "
            "written on it is not a result.",
            "The measured gain over a list with no personalization in it is "
            f"{revenue[deployed]['Share of available new-product revenue']:.4f} "
            f"against {revenue[config.FALLBACK_LABEL]['Share of available new-product revenue']:.4f} "
            "of available new-product revenue - and that is an upper bound, "
            "because it credits the model for purchases the customer may have "
            "made anyway.",
            "Popularity reaches a respectable hit rate while recommending from "
            "a tiny slice of the catalog. Coverage and novelty must print beside "
            "every accuracy number or that is invisible.",
            "Handed an empty history the model returns the zero vector, and the "
            "ten products that come back are an arbitrary tie-break. The policy "
            "sends those customers to the labeled fallback instead.",
            "Guest checkouts carry no customer id at all. They are a different "
            "population from cold registered customers and the two shares must "
            "never be added together.",
            "Everything here is measured on one 13-week test window of one "
            "UK giftware wholesaler's history in 2011. It is not a statement "
            "about any real retailer's current operations.",
        ],
        "evaluation": {
            "standard_customers_scored": evidence["split"]["customers_scored_standard"],
            "discovery_customers_scored": evidence["split"]["customers_scored_discovery"],
            "metrics": ["HR@10", "Precision@10", "Recall@10", "NDCG@10",
                        "Coverage", "Novelty", "Mean pop rank"],
            "reload_check": evidence["reload_check"].get("status"),
        },
    }


def build_policy(evidence: dict, fallback: pd.DataFrame) -> dict:
    """The written rule, exactly as the service reads it at startup."""
    from . import policy as policy_module

    return {
        "slots": config.SLOTS,
        "module_title": config.MODULE_TITLE,
        "ranking_model": config.DEPLOYED_MODEL,
        "eligibility": config.ELIGIBILITY,
        "personalize_if": config.PERSONALIZE_IF,
        "statement": policy_module.policy_statement(),
        "fallback": {
            "rule": config.FALLBACK_RULE,
            "window_days": config.FALLBACK_WINDOW_DAYS,
            "refresh": config.FALLBACK_REFRESH,
            "label": config.FALLBACK_TITLE,
            "never_label_it": config.MODULE_TITLE,
            "items": [{"slot": int(row["Slot"]), "stock_code": row["Stock code"],
                       "description": row["Product"],
                       "revenue_in_window": round(float(
                           row["Revenue in the last 28 training days"]), 2)}
                      for row in fallback.to_dict("records")],
        },
        "reorder_surface": {
            "title": config.REORDER_TITLE,
            "rule": "products the shopper has already bought, most-ordered first",
            "never": ("counted, measured or reported as personalization, and "
                      "never mixed into the recommendation slots"),
        },
        "human_authority": config.HUMAN_AUTHORITY,
        "service_must": [
            f'Label the fallback list "{config.FALLBACK_TITLE}" and never '
            f'"{config.MODULE_TITLE}".',
            "Apply the merchandiser exclusion list before filling any slot.",
            "Never place an already-bought product in a recommendation slot.",
            "Re-label any slot backfilled from the fallback list.",
            "Show nothing at all rather than a ranking built from a zero score "
            "vector.",
        ],
        "measured_at_this_policy": evidence["policy"]["outcomes"],
        "boundary": config.CLAIM_BOUNDARY_LONG,
        "prohibited_claims": config.PROHIBITED_CLAIMS,
    }


# ── Export ──────────────────────────────────────────────────────────────────

def export(similarity: sp.csr_matrix, catalog: pd.DataFrame, evidence: dict,
           model_card: dict, policy: dict, samples: pd.DataFrame) -> pd.DataFrame:
    """Write the six-file contract and report what each one costs."""
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    stored = sp.csr_matrix(similarity, dtype=np.float32)
    stored.eliminate_zeros()
    sp.save_npz(config.ARTIFACT_DIR / SIMILARITY, stored, compressed=True)

    catalog.to_parquet(config.ARTIFACT_DIR / CATALOG, index=False, compression="zstd")
    samples.to_parquet(config.ARTIFACT_DIR / SAMPLES, index=False, compression="zstd")

    for name, payload in ((MODEL_CARD, model_card), (EVALUATION, evidence),
                          (POLICY, policy)):
        (config.ARTIFACT_DIR / name).write_text(
            json.dumps(payload, indent=1, default=_encode), encoding="utf-8")

    rows = []
    for name in ARTIFACT_ORDER:
        path = config.ARTIFACT_DIR / name
        rows.append({"Artifact": name,
                     "Size": f"{path.stat().st_size / 1e6:.3f} MB",
                     "What the service does with it": _PURPOSE[name]})
    return pd.DataFrame(rows)


def _encode(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return str(value)
    if value is pd.NA or value is pd.NaT:
        return None
    raise TypeError(f"cannot serialise {type(value)!r}")


# ── Verify ──────────────────────────────────────────────────────────────────

def verify(count: int = config.RELOAD_CHECK_USERS) -> dict:
    """Reload the artifacts from disk and reproduce the recorded ten slots.

    Nothing in memory is reused. The similarity matrix and the catalog are read
    back from ``artifacts/``, the customer matrix is rebuilt from the committed
    interaction log the way the service would rebuild it from its own history
    store, and 200 customers are re-ranked under the discovery policy.
    Identical stock codes in all ten slots for all 200, or this raises.
    """
    evidence = json.loads((config.ARTIFACT_DIR / EVALUATION).read_text())
    recorded = evidence["reload_check"]["baseline_top10"]

    stored = sp.load_npz(config.ARTIFACT_DIR / SIMILARITY).tocsr()
    catalog = pd.read_parquet(config.ARTIFACT_DIR / CATALOG)
    codes = catalog["stock_code"].astype(str).tolist()

    split = matrix.build_split(data.load_interactions())
    if codes != list(split.items):
        raise AssertionError("The exported catalog is not the matrix column order.")

    fitted = models.Fitted(config.DEPLOYED_MODEL_LABEL, "item_item", stored, 0.0)
    customers = [int(customer) for customer in recorded]
    rows = [split.user_index[customer] for customer in customers]
    top = evaluate.ranked_lists(split, fitted, config.PROTOCOL_DISCOVERY, rows)

    identical = 0
    mismatches = []
    for customer, row in zip(customers, rows):
        reloaded = [codes[int(i)] for i in top[row]]
        if reloaded == recorded[str(customer)]:
            identical += 1
        else:
            mismatches.append({"customer_id": customer,
                               "recorded": recorded[str(customer)],
                               "reloaded": reloaded})

    result = {
        "customers": len(customers),
        "identical_top10": f"{identical}/{len(customers)}",
        "products_reloaded": int(len(catalog)),
        "stored_links": int(stored.nnz),
        "neighbours_kept": config.ITEM_NEIGHBOURS,
        "similarity_digest": similarity_digest(stored),
        "digest_recorded_at_export": evidence["reload_check"]["similarity_digest"],
        "customer_matrix": ("rebuilt from data/interactions.parquet, not exported - "
                            "the service owns its own customer history"),
        "mismatches": mismatches,
    }
    result["status"] = (
        "identical" if not mismatches
        and result["similarity_digest"] == result["digest_recorded_at_export"]
        else "MISMATCH")
    if result["status"] != "identical":
        raise AssertionError(f"Reload is not identical: {result}")
    return result


def committed_size() -> pd.DataFrame:
    """What this lab asks a student to clone, by directory."""
    rows = []
    for label, directory in (("Committed data", config.DATA_DIR),
                             ("Exported artifacts", config.ARTIFACT_DIR)):
        total = sum(path.stat().st_size for path in directory.glob("*")
                    if path.is_file()) if directory.exists() else 0
        rows.append({"What": label, "Megabytes": round(total / 1e6, 3)})
    rows.append({"What": "Total committed",
                 "Megabytes": round(sum(row["Megabytes"] for row in rows), 3)})
    return pd.DataFrame(rows)
