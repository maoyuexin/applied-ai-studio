from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import MAX_NARRATIVE_CHARACTERS, REPOSITORY_ROOT
from .schemas import (
    ClassificationResult,
    ConfusionMatrix,
    DatasetInfo,
    DedupeEvidence,
    DedupeTeamShare,
    ExplanationInfo,
    FrozenTestRouting,
    ModelInfo,
    PackagedComplaint,
    PerTeamRow,
    PolicyInfo,
    QueueBoard,
    QueueComplaint,
    QueueSummary,
    RepresentationComparison,
    RepresentationInfo,
    RepresentationResult,
    RepresentationSettings,
    RoutingWord,
    TeamInfo,
    TeamProbability,
    TeamQueue,
    TestMetrics,
    ThresholdSweepRow,
    TriageQueue,
)

# Serving reuses the notebook's own code rather than a second copy that could
# drift from it. The text preparation travels inside model.joblib - the fitted
# TfidfVectorizer that complaintlab.text_prep.build_vectorizer configured - and
# the routing words come from complaintlab.explain, the same function that wrote
# the top_words column of sample_manifest.parquet. Both need the notebook
# package importable, so its directory goes on sys.path before anything loads.
NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "complaint-routing"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from complaintlab import config as lab, explain  # noqa: E402

ARTIFACT_FILES = (
    "model.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)

SCORE_NOTE = (
    "A team probability used to pick a queue. It is not a judgement about whether the "
    "complaint is valid, and it never decides what a company owes; a person answers "
    "every complaint."
)

ROUTING_WORDS_NOTE = (
    "These are the words that pushed this complaint toward this team. They describe "
    "the model's arithmetic, not the consumer's reason for complaining and not a "
    "finding about the company."
)

PLAIN_MECHANISM = (
    "The model holds a weight for every word and 2-word phrase, one set of weights per "
    "team. For one complaint it multiplies how strongly the word appears by the chosen "
    "team's weight for that word. The largest results are the words below."
)

PLAIN_RULE = (
    "Read the model's strongest team score. At 0.55 or higher the complaint goes "
    "straight into that team's queue. Below 0.55 it goes to a person, who reads it and "
    "picks the team by hand."
)

DEDUPE_LESSON = (
    "The same template letter was filed thousands of times, so removing exact copies "
    "before drawing the splits was not tidying: it was the difference between a test "
    "score and a memory test. Skipping it put 17% of the test complaints word for word "
    "in the training data and reported 84.3% accuracy where the honest number is 81.9%."
)

REPRESENTATION_LESSON = (
    "On matched data the transformer scored lower here, and it could not show a triage "
    "clerk which words caused a route. That is a trade between two ways of turning "
    "text into numbers, not a newer model beating an older one. Long complaints get cut "
    "off at 256 tokens, and routing turns on vocabulary that word counts already catch."
)

BASELINE_NOTE = (
    "The comparison floor: a rule that always answers Credit reporting, the largest "
    "team. It gets 30.5% right and has nothing to explain."
)

TEST_NOTE = (
    "Measured once on the untouched test split after the model and the 0.55 rule were "
    "frozen. These numbers do not move when you route a complaint on this page."
)

SELECTION_NOTE = (
    "These packaged complaints were chosen to span both routes, so the triage share "
    "here is deliberately larger than it would be in a day's real intake. The frozen "
    "test-split figures are alongside."
)

OUTCOME_PACKAGED = (
    "This is a packaged held-out complaint, so the team it actually belonged to is on "
    "record and can be compared with the route."
)

OUTCOME_PASTED = (
    "This text is not one of the packaged complaints, so there is no recorded team to "
    "compare the route with. The model still routes it; nobody can say yet whether the "
    "route is right."
)


def _route_label(route: str, team: str) -> str:
    return f"Auto-routed to {team}" if route == lab.ROUTE_AUTO else "Sent to human triage"


def _excerpt(narrative: str, characters: int = 220) -> str:
    text = " ".join(narrative.split())
    if len(text) <= characters:
        return text
    return f"{text[:characters].rstrip()}..."


def _spread(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    """Evenly spaced rows across an ordering, so a smaller limit still spans it.

    Taking ``head(count)`` of a confidence-sorted frame would drop every triage
    complaint first, which is exactly the part of the worklist worth seeing.
    """
    if count >= len(frame):
        return frame
    picks = np.unique(np.linspace(0, len(frame) - 1, count).round().astype(int))
    return frame.iloc[picks]


class ComplaintRuntime:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = artifact_dir
        missing = [name for name in ARTIFACT_FILES if not (artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing complaint artifacts in {artifact_dir}: {', '.join(missing)}."
            )

        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.evaluation = json.loads((artifact_dir / "evaluation.json").read_text())
        self.policy = json.loads((artifact_dir / "operating_policy.json").read_text())
        # Loaded from the fixed artifact path only. Nothing here accepts a model
        # path, a model upload, or any file a caller names.
        self.pipeline = joblib.load(artifact_dir / "model.joblib")
        self.classifier = self.pipeline.named_steps["lr"]
        self.teams = [str(team) for team in self.classifier.classes_]
        self.descriptions = dict(self.card["teams"])
        self.threshold = float(self.policy["confidence_threshold"])
        self.model_version = str(self.card["model_version"])

        manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
        manifest["complaint_id"] = manifest["complaint_id"].astype(str)
        manifest["date_received"] = manifest["date_received"].astype(str)
        manifest["_words"] = [json.loads(value) for value in manifest["top_words"]]
        self.manifest = manifest
        # Lookup for the "known team" comparison. Surrounding whitespace cannot
        # change a TF-IDF row, so it cannot change the score either; matching on
        # the stripped text keeps a pasted copy of a packaged complaint
        # recognisable.
        self.packaged_by_text = {
            str(row["narrative"]).strip(): row for _, row in manifest.iterrows()
        }

    # ── Routing one complaint ───────────────────────────────────────────────

    def classify(self, narrative: str) -> ClassificationResult:
        # complaintlab.explain runs the same pipeline call the notebook ran, so
        # a packaged narrative reproduces its stored confidence bit for bit.
        table = explain.team_probabilities(self.pipeline, narrative)
        predicted = str(table.loc[0, "Team"])
        confidence = float(table.loc[0, "Probability"])
        route = lab.ROUTE_AUTO if confidence >= self.threshold else lab.ROUTE_TRIAGE
        packaged = self.packaged_by_text.get(narrative.strip())
        known_team = str(packaged["team"]) if packaged is not None else None

        return ClassificationResult(
            predicted_team=predicted,
            predicted_team_description=self.descriptions[predicted],
            confidence=confidence,
            threshold=self.threshold,
            route=route,
            route_label=_route_label(route, predicted),
            route_rule=str(self.policy["routes"][route]["when"]),
            route_action=lab.ROUTE_ACTIONS[route],
            probabilities=[
                TeamProbability(
                    team=str(row["Team"]),
                    description=self.descriptions[str(row["Team"])],
                    probability=float(row["Probability"]),
                    is_predicted=str(row["Team"]) == predicted,
                )
                for _, row in table.iterrows()
            ],
            routing_words=self._routing_words(narrative, predicted),
            routing_words_note=ROUTING_WORDS_NOTE,
            characters=len(narrative),
            words=len(narrative.split()),
            is_packaged_complaint=packaged is not None,
            known_team=known_team,
            correct=None if known_team is None else known_team == predicted,
            outcome_note=OUTCOME_PASTED if packaged is None else OUTCOME_PACKAGED,
            model_version=self.model_version,
            score_note=SCORE_NOTE,
            boundary=str(self.policy["boundary"]),
        )

    def _routing_words(self, narrative: str, team: str) -> list[RoutingWord]:
        frame = explain.routing_words(self.pipeline, narrative, team)
        return [
            # Rounded exactly as complaintlab.explain.routing_words_json rounds
            # them for the manifest, so the two are comparable digit for digit.
            RoutingWord(
                word=str(row["Word or phrase"]),
                push=round(float(row["Push toward this team"]), 4),
            )
            for _, row in frame.iterrows()
        ]

    # ── Packaged complaints ─────────────────────────────────────────────────

    def samples(self, limit: int = 12) -> list[PackagedComplaint]:
        """The screened complaints first, then a spread of the rest.

        The twelve curated complaints cover all eight teams, a deliberate
        above-threshold misroute, and two below-threshold triage cases, so the
        human path is one click away at any limit of 11 or more.
        """
        ordered = self.manifest.sort_values("confidence", ascending=False)
        curated = ordered[ordered["curated"]]
        rest = ordered[~ordered["curated"]]
        chosen = pd.concat([curated.head(limit), _spread(rest, max(0, limit - len(curated)))])
        return [self._packaged(row) for _, row in chosen.head(limit).iterrows()]

    def _packaged(self, row: pd.Series) -> PackagedComplaint:
        label, note = self._scenario(row)
        route = str(row["route"])
        return PackagedComplaint(
            scenario_id=f"complaint-{row['complaint_id']}",
            scenario_label=label,
            learning_note=note,
            complaint_id=str(row["complaint_id"]),
            date_received=str(row["date_received"]),
            narrative=str(row["narrative"]),
            characters=len(str(row["narrative"])),
            issue=str(row["issue"]),
            known_team=str(row["team"]),
            predicted_team=str(row["predicted_team"]),
            confidence=float(row["confidence"]),
            route=route,
            route_label=_route_label(route, str(row["predicted_team"])),
            correct=bool(row["correct"]),
            curated=bool(row["curated"]),
            is_misroute_example=bool(row["is_misroute_example"]),
            top_words=[RoutingWord(**word) for word in row["_words"]],
        )

    def _scenario(self, row: pd.Series) -> tuple[str, str]:
        confidence = float(row["confidence"])
        correct = bool(row["correct"])
        if bool(row["is_misroute_example"]):
            return (
                "Auto-routed and wrong",
                "The model was confident and still picked the wrong team. Nothing in the "
                "route flags this; only a person reading the complaint, or a count of how "
                "often a team sends complaints back, would catch it.",
            )
        if str(row["route"]) == lab.ROUTE_TRIAGE:
            return (
                "Sent to human triage",
                "The strongest team score stayed below 0.55, so no queue was chosen. A "
                "clerk reads this one and assigns the team by hand.",
            )
        if not correct:
            return (
                "Auto-routed to the wrong team",
                "Above the cutoff and still wrong. The receiving team has to send it back, "
                "and the days spent are days on a regulatory clock.",
            )
        if confidence >= 0.9:
            return (
                "Confident auto-route",
                "The complaint uses the vocabulary of one team and nothing else. This is "
                "the case the automatic path exists for.",
            )
        return (
            "Borderline auto-route",
            "Just above the 0.55 cutoff. It goes straight to a team, but a small change in "
            "wording would have sent it to a person instead.",
        )

    # ── The routed worklist ─────────────────────────────────────────────────

    def queues(self, limit: int = 60) -> QueueBoard:
        ordered = self.manifest.sort_values("confidence", ascending=False)
        selected = _spread(ordered, limit)
        auto = selected[selected["route"] == lab.ROUTE_AUTO]
        triage = selected[selected["route"] == lab.ROUTE_TRIAGE]
        triage_share = len(triage) / len(selected) if len(selected) else 0.0
        test = self.evaluation["test_frozen"]

        teams = []
        for team in self.teams:
            rows = auto[auto["predicted_team"] == team]
            teams.append(
                TeamQueue(
                    team=team,
                    description=self.descriptions[team],
                    complaints=len(rows),
                    share_of_auto_routed=len(rows) / len(auto) if len(auto) else 0.0,
                    misrouted=int((~rows["correct"]).sum()),
                    items=[self._queue_item(row) for _, row in rows.iterrows()],
                )
            )

        return QueueBoard(
            summary=QueueSummary(
                packaged_complaints=len(selected),
                auto_routed=len(auto),
                sent_to_triage=len(triage),
                triage_share=triage_share,
                misroutes_in_auto_routed=int((~auto["correct"]).sum()),
                threshold=self.threshold,
                rule=str(self.policy["rule"]),
                plain_rule=PLAIN_RULE,
                workload_note=(
                    f"On the untouched test split {test['triage_share']:.1%} of complaints "
                    f"reached a person: {test['triage_rows']:,} of {test['complaints']:,}. "
                    "That is the hand-sorting workload this policy creates, and it is work "
                    "the team has to staff."
                ),
                selection_note=SELECTION_NOTE,
                boundary=str(self.policy["boundary"]),
                boundary_detail=str(self.policy["boundary_detail"]),
            ),
            test=FrozenTestRouting(
                complaints=int(test["complaints"]),
                auto_routed=int(test["auto_routed"]),
                coverage=float(test["coverage"]),
                accuracy_among_auto_routed=float(test["accuracy_among_auto_routed"]),
                triage_rows=int(test["triage_rows"]),
                triage_share=float(test["triage_share"]),
                accuracy_among_triage=float(test["accuracy_among_triage"]),
                note=TEST_NOTE,
            ),
            teams=teams,
            triage=TriageQueue(
                complaints=len(triage),
                share=triage_share,
                workload_note=(
                    f"{len(triage)} of these {len(selected)} packaged complaints wait for a "
                    "person. Nothing here is closed, delayed, or dismissed by landing in "
                    "this queue."
                ),
                action=lab.ROUTE_ACTIONS[lab.ROUTE_TRIAGE],
                items=[self._queue_item(row) for _, row in triage.iterrows()],
            ),
        )

    def _queue_item(self, row: pd.Series) -> QueueComplaint:
        narrative = str(row["narrative"])
        return QueueComplaint(
            complaint_id=str(row["complaint_id"]),
            date_received=str(row["date_received"]),
            issue=str(row["issue"]),
            excerpt=_excerpt(narrative),
            narrative=narrative,
            characters=len(narrative),
            predicted_team=str(row["predicted_team"]),
            confidence=float(row["confidence"]),
            route=str(row["route"]),
            known_team=str(row["team"]),
            correct=bool(row["correct"]),
            curated=bool(row["curated"]),
            is_misroute_example=bool(row["is_misroute_example"]),
        )

    # ── Model card and evidence ─────────────────────────────────────────────

    def model_info(self) -> ModelInfo:
        test = self.evaluation["test_frozen"]
        baseline = self.evaluation["validation_leaderboard"][0]
        comparison = self.evaluation["representation_comparison"]
        dedupe = self.evaluation["dedupe"]
        leakage = dedupe["leakage_if_skipped"]
        representation = self.card["representation"]
        per_team = {row["Team"]: row for row in test["per_team"]}
        results = [self._representation_row(row) for row in comparison["results"]]
        winner = max(results, key=lambda row: row.validation_accuracy)

        return ModelInfo(
            model_name=str(self.card["model_name"]),
            model_version=self.model_version,
            framework=str(self.card["framework"]),
            packaging=str(self.card["packaging"]),
            estimator=str(self.card["estimator"]),
            task=str(self.card["task"]),
            input=str(self.card["input"]),
            output=str(self.card["output"]),
            intended_use=str(self.card["intended_use"]),
            score_note=SCORE_NOTE,
            max_narrative_characters=MAX_NARRATIVE_CHARACTERS,
            representation=RepresentationInfo(
                kind=str(representation["kind"]),
                settings=RepresentationSettings(**representation["settings"]),
                columns_learned=int(representation["columns_learned"]),
                why_not_a_transformer=str(representation["why_not_a_transformer"]),
            ),
            explanation=ExplanationInfo(
                mechanism=str(self.card["explanation"]["mechanism"]),
                output=str(self.card["explanation"]["output"]),
                note=str(self.card["explanation"]["note"]),
                plain_mechanism=PLAIN_MECHANISM,
            ),
            teams=[
                TeamInfo(
                    name=team,
                    description=self.descriptions[team],
                    precision=float(per_team[team]["Precision"]),
                    recall=float(per_team[team]["Recall"]),
                    f1=float(per_team[team]["F1"]),
                    complaints_in_test=int(per_team[team]["Complaints in the split"]),
                )
                for team in self.teams
            ],
            per_team=[
                PerTeamRow(
                    team=str(row["Team"]),
                    precision=float(row["Precision"]),
                    recall=float(row["Recall"]),
                    f1=float(row["F1"]),
                    complaints=int(row["Complaints in the split"]),
                )
                for row in test["per_team"]
            ],
            confusion=ConfusionMatrix(
                labels=list(test["confusion"]["labels"]),
                rows_are_true_team=bool(test["confusion"]["rows_are_true_team"]),
                matrix=[[int(value) for value in row] for row in test["confusion"]["matrix"]],
            ),
            dataset=DatasetInfo(
                name=str(self.card["dataset"]["name"]),
                publisher=str(self.card["dataset"]["publisher"]),
                home=str(self.card["dataset"]["home"]),
                retrieved=str(self.card["dataset"]["retrieved"]),
                rights=str(self.card["dataset"]["rights"]),
                window=str(self.card["dataset"]["window"]),
                row_meaning=lab.DATASET_ROW_MEANING,
                narratives=str(self.card["dataset"]["narratives"]),
                dedupe_rule=str(self.card["dataset"]["dedupe_rule"]),
                class_cap=str(self.card["dataset"]["class_cap"]),
                split_counts={
                    name: int(count)
                    for name, count in self.card["dataset"]["split_counts"].items()
                },
            ),
            test_metrics=TestMetrics(
                accuracy=float(test["accuracy"]),
                macro_f1=float(test["macro_f1"]),
                threshold=float(test["threshold"]),
                complaints=int(test["complaints"]),
                auto_routed=int(test["auto_routed"]),
                coverage=float(test["coverage"]),
                accuracy_among_auto_routed=float(test["accuracy_among_auto_routed"]),
                triage_rows=int(test["triage_rows"]),
                triage_share=float(test["triage_share"]),
                accuracy_among_triage=float(test["accuracy_among_triage"]),
                baseline_accuracy=float(baseline["Validation accuracy"]),
                baseline_macro_f1=float(baseline["Validation macro-F1"]),
                baseline_note=BASELINE_NOTE,
                note=TEST_NOTE,
            ),
            policy=PolicyInfo(
                name=str(self.policy["name"]),
                rule=str(self.policy["rule"]),
                plain_rule=PLAIN_RULE,
                confidence_threshold=self.threshold,
                confidence_definition=str(self.policy["confidence_definition"]),
                selected_on=str(self.policy["selected_on"]),
                auto_route_when=str(self.policy["routes"]["auto_route"]["when"]),
                auto_route_action=lab.ROUTE_ACTIONS[lab.ROUTE_AUTO],
                auto_route_coverage=float(
                    self.policy["routes"]["auto_route"]["measured_on_test"]["coverage"]
                ),
                auto_route_accuracy=float(
                    self.policy["routes"]["auto_route"]["measured_on_test"][
                        "accuracy_among_auto_routed"
                    ]
                ),
                triage_when=str(self.policy["routes"]["human_triage"]["when"]),
                triage_action=lab.ROUTE_ACTIONS[lab.ROUTE_TRIAGE],
                triage_share=float(
                    self.policy["routes"]["human_triage"]["measured_on_test"]["share"]
                ),
                triage_complaints=int(
                    self.policy["routes"]["human_triage"]["measured_on_test"]["complaints"]
                ),
                fallback=str(self.policy["fallback"]),
                boundary=str(self.policy["boundary"]),
                boundary_detail=str(self.policy["boundary_detail"]),
            ),
            threshold_sweep=[
                ThresholdSweepRow(
                    threshold=float(row["threshold"]),
                    coverage=float(row["coverage"]),
                    accuracy_among_auto_routed=float(row["accuracy_among_auto_routed"]),
                    triage_share=float(row["triage_share"]),
                    overall_accuracy=float(row["overall_accuracy"]),
                    is_chosen=float(row["threshold"]) == self.threshold,
                )
                for row in self.evaluation["threshold_sweep_validation"]
            ],
            representation_comparison=RepresentationComparison(
                design=str(comparison["design"]),
                embedding_model=str(comparison["embedding_model"]),
                embedding_facts={
                    key: str(value) for key, value in comparison["embedding_facts"].items()
                },
                results=results,
                winner=winner.model,
                accuracy_gap=round(
                    max(row.validation_accuracy for row in results)
                    - min(row.validation_accuracy for row in results),
                    4,
                ),
                lesson=REPRESENTATION_LESSON,
            ),
            dedupe=DedupeEvidence(
                rule=str(dedupe["rule"]),
                mapped_rows_in_window=int(dedupe["mapped_rows_in_window"]),
                rows_removed=int(dedupe["rows_removed"]),
                share_removed=float(dedupe["share_removed"]),
                distinct_narratives=int(dedupe["distinct_narratives"]),
                narratives_filed_more_than_once=int(dedupe["narratives_filed_more_than_once"]),
                share_removed_by_team=[
                    DedupeTeamShare(team=team, share_removed=float(share))
                    for team, share in sorted(
                        dedupe["share_removed_by_team"].items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ],
                test_rows_seen_verbatim_in_train=float(leakage["test_rows_seen_verbatim_in_train"]),
                inflated_test_accuracy=float(leakage["inflated_test_accuracy"]),
                honest_test_accuracy=float(leakage["honest_test_accuracy"]),
                inflation_percentage_points=float(leakage["inflation_percentage_points"]),
                lesson=DEDUPE_LESSON,
            ),
            limitations=list(self.card["limitations"]),
            excluded_uses=list(self.card["excluded_uses"]),
            environment={key: str(value) for key, value in self.card["environment"].items()},
        )

    @staticmethod
    def _representation_row(row: dict) -> RepresentationResult:
        return RepresentationResult(
            model=str(row["Model"]),
            trained_on=int(row["Trained on"]),
            representation=str(row["Representation"]),
            validation_accuracy=float(row["Validation accuracy"]),
            validation_macro_f1=float(row["Validation macro-F1"]),
            fit_seconds=float(row["Fit seconds"]),
            explanation_available=str(row["Explanation available"]),
        )

    def artifact_readiness(self) -> dict[str, bool]:
        return {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
