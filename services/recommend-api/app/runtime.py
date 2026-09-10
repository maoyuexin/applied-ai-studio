from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .config import NOTEBOOK_DIR
from .schemas import (
    BecauseYouBought,
    ColdStart,
    ColdStartKind,
    CompareRanking,
    CompareResponse,
    CompareSlot,
    Concentration,
    DampingRow,
    DatasetInfo,
    DeployedModel,
    Engineering,
    ExposureLoop,
    ExposureLoopRow,
    ExposureRow,
    FallbackItem,
    FallbackPolicy,
    FallbackSweepRow,
    HistoryProduct,
    HistorySummary,
    IncrementalRevenue,
    InflationRow,
    Leaderboards,
    LeaderboardRow,
    LeaveOneOut,
    ModelComparison,
    ModelInfo,
    PackagedCustomer,
    PolicyInfo,
    PolicyOutcomes,
    PopularityBias,
    Protocol,
    ProtocolInfo,
    RepeatPurchasing,
    ReorderItem,
    ReorderStrip,
    ReorderSurface,
    RevenueRow,
    SideBySideRow,
    Slot,
    SlotsResponse,
    SplitInfo,
    TruncationRow,
    ZeroScoreDiagnosis,
)

# Serving reuses the notebook's own code rather than a second copy that could
# drift from it. reclab.matrix.build_split is the function that decided the
# 2011-09-09 cut and the five-product threshold; reclab.models.top_k is the
# function whose mask_seen flag *is* the protocol switch; and
# reclab.evaluate.ranked_lists is what wrote sample_manifest.parquet. Ranking a
# customer here therefore runs the same lines the notebook ran, which is why the
# contract test can compare stock code against stock code rather than roughly.
# All of it needs the notebook package importable, so its directory goes on
# sys.path before anything loads.
NOTEBOOK_ROOT = NOTEBOOK_DIR
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from reclab import config as lab, data, evaluate, matrix, models  # noqa: E402

ARTIFACT_FILES = (
    "item_similarity.npz",
    "item_catalog.parquet",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)

# The customer history is deliberately NOT an artifact. The notebook exports the
# similarity matrix and the catalog; the service owns its own purchase history
# and rebuilds the customer x product matrix from the committed interaction log
# at start-up, exactly as reclab.handoff.verify does. A service that recommended
# from a frozen copy of last quarter's baskets would be lying about what it knows.
INTERACTIONS = lab.INTERACTIONS_PARQUET

SCORE_NOTE = (
    "A score is how strongly this product is linked to what this customer already "
    "bought. It is an offline ranking score. It is not a prediction of revenue, and "
    "it is not a statement about what this shopper needs."
)

SCORE_BASIS_PERSONALIZED = (
    "The customer's purchase history multiplied by the item-item similarity matrix. "
    "A higher number means more of the products they already own point at this one."
)

SCORE_BASIS_FALLBACK = (
    "Revenue in the last 28 days of the training window. No customer input goes into "
    "this list at all - everybody with no history sees the same ten products."
)

DISCOVERY_REASON = (
    "This customer has enough history to rank against, so the ten slots are personalized "
    "and every product in them is one they have never bought."
)

STANDARD_REASON = (
    "The standard next-purchase protocol was asked for. Nothing is masked, so products "
    "the customer already owns can and do come back. This is an evaluation view: the "
    "storefront never ships these slots."
)

COLD_REASON_NO_HISTORY = (
    "This customer bought nothing before the cut, so there is no history row to rank "
    "against. Handed an empty history the model returns the zero vector and its ten "
    "slots would be an arbitrary tie-break, so the policy shows the fallback list "
    'labeled "Popular right now" instead.'
)

COLD_REASON_THIN = (
    "This customer bought something before the cut but fewer than five distinct "
    "products, which is below the threshold for entering the training matrix. There is "
    'not enough to learn from, so they get the fallback list labeled "Popular right now".'
)

POLICY_NOTE_DISCOVERY = (
    "These are the slots the storefront would show. Already-bought products were "
    "removed before ranking, the merchandiser's exclusion list is applied first, and "
    "any slot backfilled from the fallback list is relabeled."
)

POLICY_NOTE_STANDARD = (
    "This is the standard next-purchase protocol, not the shipping policy. Products the "
    "customer already owns are left in the candidate pool, which is why some slots are "
    "things they have bought before. The storefront would never show this list; the "
    'products they already own belong in "Buy it again".'
)

REORDER_NOTE = (
    'The "Buy it again" strip is a replenishment reminder built from what this customer '
    "already buys. It is never counted, measured or reported as personalization, and it "
    "never shares a slot with the recommendations above."
)

REORDER_UNAVAILABLE = (
    "This customer has no purchase history before the cut, so there is nothing to "
    "remind them to buy again."
)

COMPARE_LESSON = (
    "Read the two columns for the reorder baseline. On the standard protocol it fills "
    "ten slots with things this customer buys constantly and scores near the top. On "
    "discovery, every one of those products is masked out, every score falls to zero, "
    "and its ten slots are a tie-break in the least-bought tail of the catalog. The "
    "model did not change. The question did."
)

COMPARE_COLD = (
    "This customer has no row in the training matrix, so no personalized model can rank "
    "for them at all. There is nothing to compare. They see the fallback list."
)

LOO_PLAIN = (
    "Leave-one-out hides one purchase per customer and trains on everything else - "
    "including that customer's later baskets and every other customer's future. The gap "
    "between column A and column B is what that leak is worth in hit rate."
)

DAMPING_NOTE = (
    "Scaling a product column by 1/popularity^alpha multiplies a row of R.T by a "
    "constant, and the L2 normalization inside cosine divides that constant straight "
    "back out. The knob is connected to nothing, and the largest difference in the "
    "similarity matrix is exactly 0.000000 at every alpha."
)

REPEAT_NOTE = (
    "38.4% of the correct answers in the test window - and 43.5% of the revenue - are "
    "products the customer already owned. That one measurement is why a model that "
    "lists what a customer already buys tops the standard leaderboard without learning "
    "anything."
)

UPPER_BOUND_NOTE = (
    "3.53% against 2.81% is a 0.7 percentage-point gap, and it is an upper bound: it "
    "credits the model for every purchase a customer might have made anyway. Nothing "
    "here measures revenue caused by a recommendation."
)

COLD_START_EXAMPLE_RULE = (
    "Not from the manifest. Chosen by rule from the registered customers who bought "
    "after the cut but never entered the training matrix: the one with the most "
    "distinct products bought after the cut, ties broken by customer id."
)

MANIFEST_RULE = (
    "Packaged in sample_manifest.parquet by the notebook. Every persona is a rule "
    "someone else can re-run - the longest history, the best discovery result, the "
    "median - not a hand-picked favorite."
)


class RecommendRuntime:
    """Everything the routes need, loaded once at start-up.

    Start-up does four things: read the six artifacts, rebuild the customer x
    product matrix from the committed interaction log, wrap the frozen similarity
    matrix as the deployed scorer, and fit the cheap baselines the comparison
    needs. The one expensive model - the full 79 MB dense similarity matrix - is
    fitted the first time /compare asks for it and then kept, so a service that
    is only serving slots never pays for it.
    """

    def __init__(self, artifact_dir: Path | str) -> None:
        self.artifact_dir = Path(artifact_dir)
        missing = [name for name in ARTIFACT_FILES
                   if not (self.artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing artifact files in {self.artifact_dir}: {', '.join(missing)}."
            )
        if not INTERACTIONS.exists():
            raise FileNotFoundError(
                f"Missing the committed interaction log at {INTERACTIONS}. The service "
                "rebuilds the customer matrix from it rather than from an exported copy."
            )

        self.card: dict = json.loads((self.artifact_dir / "model_card.json").read_text())
        self.evidence: dict = json.loads((self.artifact_dir / "evaluation.json").read_text())
        self.policy: dict = json.loads((self.artifact_dir / "operating_policy.json").read_text())
        self.catalog = pd.read_parquet(self.artifact_dir / "item_catalog.parquet")
        self.catalog["stock_code"] = self.catalog["stock_code"].astype(str)
        self.manifest = pd.read_parquet(self.artifact_dir / "sample_manifest.parquet")
        self.similarity = sp.load_npz(self.artifact_dir / "item_similarity.npz").tocsr()

        self.frame = data.load_interactions()
        self.split = matrix.build_split(self.frame)

        codes = self.catalog["stock_code"].tolist()
        if codes != list(self.split.items):
            raise ValueError(
                "The exported catalog is not the matrix column order. The similarity "
                "matrix and the rebuilt customer matrix disagree about what column 0 is."
            )

        self._catalog_codes = set(codes)
        self.description = dict(zip(codes, self.catalog["description"].astype(str)))
        self.popularity_rank = dict(zip(codes, self.catalog["popularity_rank"].astype(int)))
        self.training_customers = dict(zip(codes, self.catalog["training_customers"].astype(int)))

        self.deployed = models.Fitted(lab.DEPLOYED_MODEL_LABEL, "item_item", self.similarity, 0.0)
        self.reorder = models.fit_reorder(self.split)
        self.popularity = models.fit_popularity(self.split)
        self.fallback = models.fit_fallback(self.split)
        self.random = models.fit_random(self.split)
        self.svd = models.fit_svd(self.split)
        self._full_item_item: models.Fitted | None = None
        self._full_lock = threading.Lock()

        self._build_customer_profiles()
        self._build_packaged()

        self.model_version = str(self.card["version"])

    # ── Start-up helpers ────────────────────────────────────────────────────

    def _build_customer_profiles(self) -> None:
        """Per-customer facts the routes need, computed once over the log."""
        registered = self.frame.dropna(subset=["customer_id"]).copy()
        registered["customer_id"] = registered["customer_id"].astype(int)
        cut = self.split.cut
        train = registered[registered["invoice_ts"] <= cut]
        test = registered[registered["invoice_ts"] > cut]

        self._train_rows = train
        self._test_rows = test
        self._train_customers = set(train["customer_id"].unique().tolist())
        self._test_customers = set(test["customer_id"].unique().tolist())
        self._known_customers = self._train_customers | self._test_customers

        self._train_products = (
            train.drop_duplicates(["customer_id", "stock_code"])
            .groupby("customer_id").size().to_dict()
        )
        self._train_baskets = train.groupby("customer_id")["invoice"].nunique().to_dict()
        self._first_purchase = train.groupby("customer_id")["invoice_ts"].min().to_dict()
        self._last_purchase = train.groupby("customer_id")["invoice_ts"].max().to_dict()

        # Every product the customer bought after the cut, by stock code, so the
        # cold-start customers - who have no matrix row and therefore no entry in
        # split.truth_standard - can still be told which slots they went on to buy.
        after = test.drop_duplicates(["customer_id", "stock_code"])
        self._bought_after: dict[int, set[str]] = {}
        for customer, code in zip(after["customer_id"].to_numpy(), after["stock_code"].to_numpy()):
            self._bought_after.setdefault(int(customer), set()).add(str(code))

        owned = train.drop_duplicates(["customer_id", "stock_code"])
        self._owned_before: dict[int, set[str]] = {}
        for customer, code in zip(owned["customer_id"].to_numpy(), owned["stock_code"].to_numpy()):
            self._owned_before.setdefault(int(customer), set()).add(str(code))

        # How many baskets each already-bought product appeared in, for the
        # "Buy it again" strip. The reorder model ranks on exactly this number.
        counts = (train.groupby(["customer_id", "stock_code"])["invoice"]
                  .nunique().reset_index(name="baskets"))
        self._history_baskets: dict[int, dict[str, int]] = {}
        for customer, code, baskets in zip(counts["customer_id"].to_numpy(),
                                           counts["stock_code"].to_numpy(),
                                           counts["baskets"].to_numpy()):
            self._history_baskets.setdefault(int(customer), {})[str(code)] = int(baskets)

    def _cold_start_kind(self, customer_id: int) -> ColdStartKind:
        if customer_id in self.split.user_index:
            return "none"
        if customer_id in self._train_customers:
            return "history_below_the_threshold"
        return "no_history_before_the_cut"

    def _pick_cold_start_examples(self) -> list[tuple[str, int]]:
        """Two unservable customers, chosen by a rule rather than by taste.

        The manifest packages ten customers the model *can* serve, because the
        notebook picked them from the discovery population. 22.4% of the shoppers
        in the test window cannot be served at all, and a demo that never shows
        one of them hides the largest limitation in the case. These two are picked
        from the log by a stated rule so anyone can re-run the choice.
        """
        products_after = {customer: len(codes) for customer, codes in self._bought_after.items()}
        picks: list[tuple[str, int]] = []
        wanted = (
            ("no_history_before_the_cut",
             "Cold start: nothing bought before the cut, so nothing to rank"),
            ("history_below_the_threshold",
             "Cold start: bought before the cut, but under the five-product threshold"),
        )
        for kind, persona in wanted:
            pool = [customer for customer in self._test_customers
                    if self._cold_start_kind(customer) == kind]
            if not pool:
                continue
            best = sorted(pool, key=lambda customer: (-products_after.get(customer, 0), customer))[0]
            picks.append((persona, int(best)))
        return picks

    def _build_packaged(self) -> None:
        """The demo roster: the ten packaged customers, then two cold-start ones."""
        packaged: list[PackagedCustomer] = []
        for _, row in self.manifest.iterrows():
            customer_id = int(row["customer_id"])
            is_discussion = customer_id == lab.DISCUSSION_CUSTOMER
            packaged.append(PackagedCustomer(
                customer_id=customer_id,
                persona=str(row["persona"]),
                source="manifest",
                selection_rule=MANIFEST_RULE,
                cold_start=False,
                cold_start_kind="none",
                is_discussion_case=is_discussion,
                discussion_note=lab.DISCUSSION_NOTE if is_discussion else None,
                training_products=int(row["training_products"]),
                training_baskets=int(row["training_baskets"]),
                bought_after_the_cut=int(row["bought_after_the_cut"]),
                new_to_them_after_the_cut=int(row["new_to_them_after_the_cut"]),
                discovery_hits_out_of_10=int(row["discovery_hits_out_of_10"]),
                reorder_hits_out_of_10_standard=int(row["reorder_hits_out_of_10_standard"]),
                history_note=(
                    f"{int(row['training_products']):,} distinct products across "
                    f"{int(row['training_baskets']):,} baskets before the cut."
                ),
            ))

        for persona, customer_id in self._pick_cold_start_examples():
            kind = self._cold_start_kind(customer_id)
            products = int(self._train_products.get(customer_id, 0))
            baskets = int(self._train_baskets.get(customer_id, 0))
            note = (
                "Nothing at all before the cut."
                if kind == "no_history_before_the_cut"
                else f"{products} distinct product{'' if products == 1 else 's'} before the cut, "
                     f"below the five the matrix requires."
            )
            packaged.append(PackagedCustomer(
                customer_id=customer_id,
                persona=persona,
                source="cold_start_example",
                selection_rule=COLD_START_EXAMPLE_RULE,
                cold_start=True,
                cold_start_kind=kind,
                is_discussion_case=False,
                discussion_note=None,
                training_products=products,
                training_baskets=baskets,
                bought_after_the_cut=len(
                    self._bought_after.get(customer_id, set()) & self._catalog_codes),
                new_to_them_after_the_cut=len(
                    (self._bought_after.get(customer_id, set()) & self._catalog_codes)
                    - self._owned_before.get(customer_id, set())
                ),
                discovery_hits_out_of_10=None,
                reorder_hits_out_of_10_standard=None,
                history_note=note,
            ))

        self.packaged = packaged
        self._packaged_by_id = {entry.customer_id: entry for entry in packaged}

    def _full_similarity_model(self) -> models.Fitted:
        """The untruncated item-item model, fitted on first use and then kept.

        79 MB dense. The comparison view needs it - it is the row that shows
        truncation *raising* discovery hit rate - but nothing else does, so a
        service that only fills slots never allocates it.
        """
        with self._full_lock:
            if self._full_item_item is None:
                self._full_item_item = models.fit_item_item(
                    self.split, None, lab.ITEMITEM_FULL_LABEL)
            return self._full_item_item

    # ── Readiness ───────────────────────────────────────────────────────────

    def artifact_readiness(self) -> dict[str, bool]:
        readiness = {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
        readiness["interactions.parquet"] = INTERACTIONS.exists()
        return readiness

    # ── Packaged customers ──────────────────────────────────────────────────

    def customers(self, limit: int) -> list[PackagedCustomer]:
        return self.packaged[:limit]

    def is_known_customer(self, customer_id: int) -> bool:
        return customer_id in self._known_customers

    def packaged_ids(self) -> list[int]:
        return [entry.customer_id for entry in self.packaged]

    # ── Ranking ─────────────────────────────────────────────────────────────

    def _persona(self, customer_id: int) -> str:
        entry = self._packaged_by_id.get(customer_id)
        if entry is not None:
            return entry.persona
        if customer_id in self.split.user_index:
            return "A customer from the training matrix, not one of the packaged demos"
        return "A customer with no row in the training matrix"

    def _protocol_detail(self, protocol: str) -> ProtocolInfo:
        definition = self.evidence["protocols"][protocol]
        return ProtocolInfo(id=protocol, **definition)

    def _ranked(self, fitted: models.Fitted, row: int, protocol: str) -> tuple[list[int], np.ndarray]:
        """Ten column indices and the full score row, from the notebook's own code."""
        scores = models.score(fitted, self.split, [row])
        top = models.top_k(scores, [row], self.split.seen, lab.SLOTS,
                           protocol == lab.PROTOCOL_DISCOVERY)
        return [int(index) for index in top[row]], np.asarray(scores[0]).ravel()

    def _history_summary(self, customer_id: int) -> HistorySummary:
        in_matrix = customer_id in self.split.user_index
        baskets = self._history_baskets.get(customer_id, {})
        ordered = sorted(baskets.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        top = [
            HistoryProduct(
                stock_code=code,
                description=self.description.get(code, code),
                baskets=count,
                popularity_rank=self.popularity_rank.get(code, 0),
            )
            for code, count in ordered
            if code in self.description
        ]
        # Counted against the 4,443 products that are columns of the matrix, which
        # is the denominator the notebook used. A customer can buy something the
        # matrix has never seen; that purchase is real but it is not a product any
        # model here could have ranked, so it is not counted as one that was missed.
        bought_after = self._bought_after.get(customer_id, set()) & self._catalog_codes
        owned = self._owned_before.get(customer_id, set()) & self._catalog_codes
        first = self._first_purchase.get(customer_id)
        last = self._last_purchase.get(customer_id)
        products = int(self._train_products.get(customer_id, 0))
        note = (
            f"{products:,} distinct products before the cut, so this customer is in the "
            "training matrix and can be ranked against."
            if in_matrix
            else f"{products:,} distinct products before the cut. The matrix needs "
                 f"{lab.MIN_TRAIN_ITEMS_PER_USER}, so there is no row to rank against."
        )
        return HistorySummary(
            in_training_matrix=in_matrix,
            training_products=products,
            training_baskets=int(self._train_baskets.get(customer_id, 0)),
            first_purchase=str(pd.Timestamp(first).date()) if first is not None else None,
            last_purchase=str(pd.Timestamp(last).date()) if last is not None else None,
            bought_after_the_cut=len(bought_after),
            new_to_them_after_the_cut=len(bought_after - owned),
            top_products=top,
            note=note,
        )

    def _because_you_bought(self, row: int, item: int) -> BecauseYouBought | None:
        """The product in this customer's history that pushed hardest on this slot.

        This is the whole reason item-item ships instead of the SVD that scores
        0.0281 higher: the score for a slot is a sum of similarities to products
        the customer actually bought, so the largest term in that sum has a name.
        """
        history = sorted(self.split.seen[row])
        if not history:
            return None
        column = np.asarray(self.similarity[history][:, item].todense()).ravel()
        if column.size == 0 or float(column.max()) <= 0:
            return None
        best = int(np.argmax(column))
        code = self.split.items[history[best]]
        return BecauseYouBought(
            stock_code=code,
            description=self.description.get(code, code),
            contribution=round(float(column[best]), 4),
        )

    def _reorder_strip(self, customer_id: int) -> ReorderStrip:
        surface = self.policy["reorder_surface"]
        row = self.split.user_index.get(customer_id)
        bought_after = self._bought_after.get(customer_id, set())
        baskets = self._history_baskets.get(customer_id, {})
        if row is None:
            return ReorderStrip(
                title=surface["title"],
                available=False,
                rule=surface["rule"],
                never=surface["never"],
                items=[],
                hits_out_of_10_standard=0,
                note=REORDER_UNAVAILABLE,
            )
        top, scores = self._ranked(self.reorder, row, lab.PROTOCOL_STANDARD)
        items = []
        hits = 0
        for position, index in enumerate(top, start=1):
            code = self.split.items[index]
            was_bought = code in bought_after
            hits += int(was_bought)
            items.append(ReorderItem(
                slot=position,
                stock_code=code,
                description=self.description.get(code, code),
                baskets_bought_in=int(baskets.get(code, 0)),
                score=round(float(scores[index]), 4),
                bought_after_the_cut=was_bought,
                popularity_rank=self.popularity_rank.get(code, 0),
            ))
        return ReorderStrip(
            title=surface["title"],
            available=True,
            rule=surface["rule"],
            never=surface["never"],
            items=items,
            hits_out_of_10_standard=hits,
            note=REORDER_NOTE,
        )

    def _fallback_slots(self, customer_id: int) -> list[Slot]:
        """The frozen "Popular right now" list, straight from the policy artifact."""
        bought_after = self._bought_after.get(customer_id, set())
        owned = self._owned_before.get(customer_id, set())
        label = self.policy["fallback"]["label"]
        slots = []
        for entry in self.policy["fallback"]["items"]:
            code = str(entry["stock_code"])
            slots.append(Slot(
                slot=int(entry["slot"]),
                stock_code=code,
                description=str(entry["description"]),
                score=round(float(entry["revenue_in_window"]), 2),
                label=label,
                from_fallback=True,
                already_owned=code in owned,
                bought_after_the_cut=code in bought_after,
                is_new_to_them=code not in owned,
                popularity_rank=self.popularity_rank.get(code, 0),
                training_customers=self.training_customers.get(code, 0),
                because_you_bought=None,
                reason=(
                    "Nothing about this customer chose this product. It is here because it "
                    "took the most revenue in the last 28 days of the training window."
                ),
            ))
        return slots

    def slots(self, customer_id: int, protocol: Protocol) -> SlotsResponse:
        entry = self._packaged_by_id.get(customer_id)
        is_discussion = customer_id == lab.DISCUSSION_CUSTOMER
        row = self.split.user_index.get(customer_id)
        history = self._history_summary(customer_id)
        strip = self._reorder_strip(customer_id)
        detail = self._protocol_detail(
            lab.PROTOCOL_DISCOVERY if protocol == "discovery" else lab.PROTOCOL_STANDARD)
        bought_after = self._bought_after.get(customer_id, set())
        owned = self._owned_before.get(customer_id, set())

        if row is None:
            kind = self._cold_start_kind(customer_id)
            filled = self._fallback_slots(customer_id)
            return SlotsResponse(
                customer_id=customer_id,
                persona=entry.persona if entry else self._persona(customer_id),
                is_discussion_case=False,
                discussion_note=None,
                protocol=protocol,
                protocol_detail=detail,
                module_title=self.policy["fallback"]["label"],
                personalized=False,
                fallback_used=True,
                fallback_slots=len(filled),
                reason=(COLD_REASON_NO_HISTORY
                        if kind == "no_history_before_the_cut" else COLD_REASON_THIN),
                model_used=lab.FALLBACK_LABEL,
                score_basis=SCORE_BASIS_FALLBACK,
                slots=filled,
                hits_out_of_10=sum(slot.bought_after_the_cut for slot in filled),
                buy_it_again=strip,
                history=history,
                matches_shipping_policy=True,
                policy_note=(
                    'The label is "Popular right now" and never "Recommended for you". '
                    "Calling a list personalized when no customer input went into it is "
                    "the one thing this policy will not do."
                ),
                human_authority=self.policy["human_authority"],
                score_note=SCORE_NOTE,
                boundary=self.policy["boundary"],
            )

        lab_protocol = lab.PROTOCOL_DISCOVERY if protocol == "discovery" else lab.PROTOCOL_STANDARD
        top, scores = self._ranked(self.deployed, row, lab_protocol)

        filled: list[Slot] = []
        for position, index in enumerate(top, start=1):
            code = self.split.items[index]
            score = float(scores[index])
            # Show nothing at all rather than a ranking built from a zero score
            # vector: a zero-scored slot is a tie-break, not a recommendation.
            if score <= 0:
                continue
            owns = code in owned
            because = self._because_you_bought(row, index)
            if owns:
                reason = (
                    "This customer has already bought this. It only appears because the "
                    "standard protocol leaves owned products in the candidate pool."
                )
            elif because is not None:
                reason = f"Because this customer bought {because.description}."
            else:
                reason = "Linked to this customer's history through the similarity matrix."
            filled.append(Slot(
                slot=position,
                stock_code=code,
                description=self.description.get(code, code),
                score=round(score, 4),
                label=self.policy["module_title"],
                from_fallback=False,
                already_owned=owns,
                bought_after_the_cut=code in bought_after,
                is_new_to_them=not owns,
                popularity_rank=self.popularity_rank.get(code, 0),
                training_customers=self.training_customers.get(code, 0),
                because_you_bought=because,
                reason=reason,
            ))

        backfilled = 0
        # "If fewer than 10 products score above zero, backfill from the fallback
        # list and re-label the backfilled slots." Measured on the test window this
        # happens for 0 customers, and the branch is here anyway because a policy
        # that is only true on the data it was measured on is not a policy.
        if protocol == "discovery" and len(filled) < lab.SLOTS:
            already = {slot.stock_code for slot in filled}
            for candidate in self._fallback_slots(customer_id):
                if len(filled) >= lab.SLOTS:
                    break
                if candidate.stock_code in already or candidate.already_owned:
                    continue
                candidate.slot = len(filled) + 1
                filled.append(candidate)
                already.add(candidate.stock_code)
                backfilled += 1

        for position, slot in enumerate(filled, start=1):
            slot.slot = position

        return SlotsResponse(
            customer_id=customer_id,
            persona=entry.persona if entry else self._persona(customer_id),
            is_discussion_case=is_discussion,
            discussion_note=lab.DISCUSSION_NOTE if is_discussion else None,
            protocol=protocol,
            protocol_detail=detail,
            module_title=self.policy["module_title"],
            personalized=True,
            fallback_used=backfilled > 0,
            fallback_slots=backfilled,
            reason=DISCOVERY_REASON if protocol == "discovery" else STANDARD_REASON,
            model_used=lab.DEPLOYED_MODEL_LABEL,
            score_basis=SCORE_BASIS_PERSONALIZED,
            slots=filled,
            hits_out_of_10=sum(slot.bought_after_the_cut for slot in filled),
            buy_it_again=strip,
            history=history,
            matches_shipping_policy=protocol == "discovery",
            policy_note=POLICY_NOTE_DISCOVERY if protocol == "discovery" else POLICY_NOTE_STANDARD,
            human_authority=self.policy["human_authority"],
            score_note=SCORE_NOTE,
            boundary=self.policy["boundary"],
        )

    # ── The comparison ──────────────────────────────────────────────────────

    def _comparison_models(self) -> list[tuple[str, models.Fitted]]:
        return [
            (lab.RANDOM_LABEL, self.random),
            (lab.POPULARITY_LABEL, self.popularity),
            (lab.FALLBACK_LABEL, self.fallback),
            (lab.ITEMITEM_FULL_LABEL, self._full_similarity_model()),
            (lab.DEPLOYED_MODEL_LABEL, self.deployed),
            (lab.SVD_LABEL, self.svd),
            (lab.REORDER_LABEL, self.reorder),
        ]

    def _compare_ranking(self, fitted: models.Fitted, row: int, protocol: str,
                         customer_id: int) -> CompareRanking:
        top, scores = self._ranked(fitted, row, protocol)
        owned = self._owned_before.get(customer_id, set())
        bought_after = self._bought_after.get(customer_id, set())
        truth = (self.split.truth_discovery if protocol == lab.PROTOCOL_DISCOVERY
                 else self.split.truth_standard).get(row, set())
        slots = []
        hits = 0
        owned_count = 0
        for position, index in enumerate(top, start=1):
            code = self.split.items[index]
            owns = code in owned
            owned_count += int(owns)
            hits += int(index in truth)
            slots.append(CompareSlot(
                slot=position,
                stock_code=code,
                description=self.description.get(code, code),
                score=round(float(scores[index]), 4),
                already_owned=owns,
                bought_after_the_cut=code in bought_after,
            ))
        all_zero = all(slot.score == 0 for slot in slots)
        return CompareRanking(
            slots=slots,
            hits_out_of_10=hits,
            already_owned_in_slots=owned_count,
            all_scores_zero=all_zero,
            scores_note=(
                "Every slot scored exactly zero. These ten products are the first ten in "
                "index order - a tie-break, not a ranking - and any hit among them is an "
                "accident."
                if all_zero
                else "Ranked by score, highest first."
            ),
        )

    def compare(self, customer_id: int) -> CompareResponse:
        row = self.split.user_index.get(customer_id)
        is_discussion = customer_id == lab.DISCUSSION_CUSTOMER
        protocols = [self._protocol_detail(lab.PROTOCOL_STANDARD),
                     self._protocol_detail(lab.PROTOCOL_DISCOVERY)]
        if row is None:
            return CompareResponse(
                customer_id=customer_id,
                persona=self._persona(customer_id),
                personalized=False,
                reason=COMPARE_COLD,
                is_discussion_case=False,
                discussion_note=None,
                truth_standard=0,
                truth_discovery=0,
                protocols=protocols,
                models=[],
                lesson=COMPARE_LESSON,
                score_note=SCORE_NOTE,
                boundary=self.policy["boundary"],
            )

        side = {row_["Model"]: row_ for row_ in self.evidence["leaderboards"]["side_by_side"]}
        comparisons = []
        for label, fitted in self._comparison_models():
            frozen = side[label]
            comparisons.append(ModelComparison(
                model=label,
                how_it_works=lab.MODEL_ONE_LINERS[label],
                is_deployed=label == lab.DEPLOYED_MODEL_LABEL,
                standard=self._compare_ranking(fitted, row, lab.PROTOCOL_STANDARD, customer_id),
                discovery=self._compare_ranking(fitted, row, lab.PROTOCOL_DISCOVERY, customer_id),
                standard_hr10=float(frozen["Standard HR@10"]),
                standard_rank=int(frozen["Standard rank"]),
                discovery_hr10=float(frozen["Discovery HR@10"]),
                discovery_rank=int(frozen["Discovery rank"]),
                rank_change=int(frozen["Rank change"]),
                discovery_coverage=float(frozen["Discovery coverage"]),
            ))
        return CompareResponse(
            customer_id=customer_id,
            persona=self._persona(customer_id),
            personalized=True,
            reason=(
                "This customer is in the training matrix, so every model can rank for "
                "them. The same customer, the same day, under both protocols."
            ),
            is_discussion_case=is_discussion,
            discussion_note=lab.DISCUSSION_NOTE if is_discussion else None,
            truth_standard=len(self.split.truth_standard.get(row, ())),
            truth_discovery=len(self.split.truth_discovery.get(row, ())),
            protocols=protocols,
            models=comparisons,
            lesson=COMPARE_LESSON,
            score_note=SCORE_NOTE,
            boundary=self.policy["boundary"],
        )

    # ── The model card ──────────────────────────────────────────────────────

    def _leaderboard(self, protocol: str) -> list[LeaderboardRow]:
        rows = self.evidence["leaderboards"][protocol]
        ordered = sorted(rows, key=lambda row: -row["HR@10"])
        return [
            LeaderboardRow(
                model=row["Model"],
                how_it_works=lab.MODEL_ONE_LINERS[row["Model"]],
                hr_at_10=row["HR@10"],
                precision_at_10=row["Precision@10"],
                recall_at_10=row["Recall@10"],
                ndcg_at_10=row["NDCG@10"],
                coverage=row["Coverage"],
                novelty=row["Novelty"],
                mean_popularity_rank=row["Mean pop rank"],
                customers_scored=row["Customers scored"],
                fit_seconds=row["Fit seconds"],
                rank=position,
                is_deployed=row["Model"] == lab.DEPLOYED_MODEL_LABEL,
            )
            for position, row in enumerate(ordered, start=1)
        ]

    def model_info(self) -> ModelInfo:
        card = self.card
        evidence = self.evidence
        policy = self.policy
        deployed = card["deployed_model"]
        stored_bytes = (self.similarity.data.nbytes + self.similarity.indices.nbytes
                        + self.similarity.indptr.nbytes)
        revenue = evidence["incremental_revenue"]
        deployed_share = next(row["Share of available new-product revenue"]
                              for row in revenue["by_model"]
                              if row["Model"] == lab.DEPLOYED_MODEL_LABEL)
        no_personalization = next(row["Share of available new-product revenue"]
                                  for row in revenue["by_model"]
                                  if row["Model"] == lab.FALLBACK_LABEL)
        loop = evidence["popularity_bias"]["exposure_loop"]
        sweep = evidence["policy"]["fallback_sweep"]

        return ModelInfo(
            model_name=card["name"],
            model_version=card["version"],
            generated=card["generated"],
            framework="scipy sparse + scikit-learn, served by FastAPI",
            deployed_model=DeployedModel(
                id=deployed["id"],
                label=deployed["label"],
                how_it_works=deployed["how_it_works"],
                neighbours_kept=deployed["neighbours_kept"],
                scoring=deployed["scoring"],
                why_not_the_most_accurate_model=deployed["why_not_the_most_accurate_model"],
                stored_links=int(self.similarity.nnz),
                stored_megabytes=round(stored_bytes / 1e6, 3),
                similarity_digest=evidence["reload_check"]["similarity_digest"],
            ),
            what_it_does=card["what_it_does"],
            what_it_does_not_do=card["what_it_does_not_do"],
            intended_users=card["intended_users"],
            boundary=card["boundary"],
            prohibited_claims=card["prohibited_claims"],
            known_limits=card["known_limits"],
            dataset=DatasetInfo(
                name=evidence["dataset"]["name"],
                license=evidence["dataset"]["license"],
                citation=evidence["dataset"]["citation"],
                population=evidence["dataset"]["population"],
                raw_rows=evidence["dataset"]["raw_rows"],
                clean_rows=evidence["dataset"]["clean_rows"],
                committed_rows=evidence["dataset"]["committed_rows"],
                committed_grain=evidence["dataset"]["committed_grain"],
                products_in_the_catalog=card["data"]["products_in_the_catalog"],
                customers_in_the_matrix=card["data"]["customers_in_the_matrix"],
                sibling_lab=evidence["dataset"]["sibling_lab"],
            ),
            split=SplitInfo(**evidence["split"]),
            protocols=[
                self._protocol_detail(lab.PROTOCOL_STANDARD),
                self._protocol_detail(lab.PROTOCOL_DISCOVERY),
                self._protocol_detail(lab.PROTOCOL_INCOHERENT),
            ],
            leaderboards=Leaderboards(
                rule=evidence["leaderboards"]["rule"],
                standard=self._leaderboard("standard"),
                discovery=self._leaderboard("discovery"),
                side_by_side=[
                    SideBySideRow(
                        model=row["Model"],
                        standard_hr10=row["Standard HR@10"],
                        standard_rank=row["Standard rank"],
                        discovery_hr10=row["Discovery HR@10"],
                        discovery_rank=row["Discovery rank"],
                        rank_change=row["Rank change"],
                        discovery_coverage=row["Discovery coverage"],
                        is_deployed=row["Model"] == lab.DEPLOYED_MODEL_LABEL,
                    )
                    for row in evidence["leaderboards"]["side_by_side"]
                ],
                reorder_zero_score_diagnosis=ZeroScoreDiagnosis(
                    **evidence["leaderboards"]["reorder_zero_score_diagnosis"]),
            ),
            incremental_revenue=IncrementalRevenue(
                available_new_product_revenue=revenue["available_new_product_revenue"],
                customers=revenue["customers"],
                by_model=[
                    RevenueRow(
                        model=row["Model"],
                        discovery_hits_per_customer=row["Discovery hits per customer"],
                        revenue_reached=row["Revenue reached"],
                        share_of_available_new_product_revenue=(
                            row["Share of available new-product revenue"]),
                        is_deployed=row["Model"] == lab.DEPLOYED_MODEL_LABEL,
                    )
                    for row in revenue["by_model"]
                ],
                deployed_share=deployed_share,
                no_personalization_share=no_personalization,
                gain_percentage_points=round((deployed_share - no_personalization) * 100, 2),
                upper_bound_note=UPPER_BOUND_NOTE,
                boundary=revenue["boundary"],
            ),
            leave_one_out=LeaveOneOut(
                design=evidence["leave_one_out"]["design"],
                plain_words=LOO_PLAIN,
                by_model=[
                    InflationRow(
                        model=row["Model"],
                        honest_hr10=row["A - honest: nothing after the cut, for anyone"],
                        leave_one_out_hr10=(
                            row["B - leave-one-out: everything except the held-out purchase"]),
                        inflation=row["Inflation"],
                    )
                    for row in evidence["leave_one_out"]["by_model"]
                ],
            ),
            popularity_bias=PopularityBias(
                what_each_model_shows=[
                    ExposureRow(
                        model=row["Model"],
                        coverage=row["Coverage"],
                        recommendation_gini=row["Recommendation Gini"],
                        share_from_the_top_100=row["% of slots from the top 100"],
                        share_from_the_less_popular_half=(
                            row["% of slots from the less-popular half"]),
                        median_popularity_rank=row["Median popularity rank"],
                        distinct_products_shown=row["Distinct products shown"],
                        top_product_share_of_all_slots=row["Top product's share of all slots"],
                        is_deployed=row["Model"] == lab.DEPLOYED_MODEL_LABEL,
                    )
                    for row in evidence["popularity_bias"]["what_each_model_shows"]
                ],
                exposure_loop=ExposureLoop(
                    rounds=loop["rounds"],
                    assumed_conversion=loop["assumed_conversion"],
                    assumption_note=loop["assumption_note"],
                    history=[
                        ExposureLoopRow(
                            round=row["Round"],
                            top_10_share=row["Top-10 share"],
                            top_100_share=row["Top-100 share"],
                            gini=row["Gini"],
                            distinct_products_ever_shown=row["Distinct products ever shown"],
                        )
                        for row in loop["history"]
                    ],
                    start_top_10_share=loop["history"][0]["Top-10 share"],
                    end_top_10_share=loop["history"][-1]["Top-10 share"],
                ),
            ),
            engineering=Engineering(
                truncation_trade=[
                    TruncationRow(
                        neighbours_kept=str(row["Neighbours kept"]),
                        discovery_hr10=row["Discovery HR@10"],
                        coverage=row["Coverage"],
                        novelty=row["Novelty"],
                        stored_megabytes=row["Stored megabytes"],
                        shrink_vs_the_full_matrix=row["Shrink vs the full matrix"],
                        is_deployed=str(row["Neighbours kept"]) == str(lab.ITEM_NEIGHBOURS),
                    )
                    for row in evidence["engineering"]["truncation_trade"]
                ],
                popularity_damping_is_a_no_op=[
                    DampingRow(
                        damping_alpha=row["Damping alpha"],
                        discovery_hr10=row["Discovery HR@10"],
                        ndcg_at_10=row["NDCG@10"],
                        coverage=row["Coverage"],
                        largest_difference_from_alpha_zero=(
                            row["Largest difference from alpha=0 in the similarity matrix"]),
                    )
                    for row in evidence["engineering"]["popularity_damping_is_a_no_op"]
                ],
                damping_note=DAMPING_NOTE,
            ),
            cold_start=ColdStart(
                registered_customers_active_in_test=(
                    evidence["cold_start"]["registered_customers_active_in_test"]),
                cold_registered_customers=evidence["cold_start"]["cold_registered_customers"],
                cold_registered_share=evidence["cold_start"]["cold_registered_share"],
                cold_registered_revenue_share=(
                    evidence["cold_start"]["cold_registered_revenue_share"]),
                thin_history_customers=evidence["cold_start"]["thin_history_customers"],
                thin_history_share=evidence["cold_start"]["thin_history_share"],
                unservable_customers=evidence["cold_start"]["unservable_customers"],
                unservable_share=evidence["cold_start"]["unservable_share"],
                products_sold_in_test=evidence["cold_start"]["products_sold_in_test"],
                cold_products=evidence["cold_start"]["cold_products"],
                cold_product_share=evidence["cold_start"]["cold_product_share"],
                cold_product_revenue_share=evidence["cold_start"]["cold_product_revenue_share"],
                guest_baskets_in_test=evidence["cold_start"]["guest_baskets_in_test"],
                guest_revenue_share=evidence["cold_start"]["guest_revenue_share"],
                fallback_hr10=sweep[0]["HR@10"],
                warning=evidence["cold_start"]["warning"],
            ),
            repeat_purchasing=RepeatPurchasing(**evidence["repeat_purchasing"], note=REPEAT_NOTE),
            concentration=Concentration(**evidence["concentration"]),
            policy=PolicyInfo(
                slots=policy["slots"],
                module_title=policy["module_title"],
                ranking_model=policy["ranking_model"],
                eligibility=policy["eligibility"],
                personalize_if=policy["personalize_if"],
                statement=policy["statement"],
                fallback=FallbackPolicy(
                    rule=policy["fallback"]["rule"],
                    window_days=policy["fallback"]["window_days"],
                    refresh=policy["fallback"]["refresh"],
                    label=policy["fallback"]["label"],
                    never_label_it=policy["fallback"]["never_label_it"],
                    items=[FallbackItem(**item) for item in policy["fallback"]["items"]],
                    sweep=[
                        FallbackSweepRow(
                            rule=row["Fallback rule"],
                            hr_at_10=row["HR@10"],
                            precision_at_10=row["Precision@10"],
                            cold_customers_scored=row["Cold customers scored"],
                            is_chosen=index == 0,
                        )
                        for index, row in enumerate(sweep)
                    ],
                ),
                reorder_surface=ReorderSurface(**policy["reorder_surface"]),
                human_authority=policy["human_authority"],
                service_must=policy["service_must"],
                outcomes=PolicyOutcomes(**policy["measured_at_this_policy"]),
                boundary=policy["boundary"],
            ),
            environment={key: str(value) for key, value in evidence["environment"].items()},
        )
