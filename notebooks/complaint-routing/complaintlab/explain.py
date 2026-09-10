"""Routing words: why this complaint went to this team.

The mechanism is arithmetic, not interpretation. Logistic regression gives every
team its own weight for every one of the 50,000 words and phrases. Scoring one
complaint multiplies the complaint's TF-IDF value for a word by that team's
weight for the same word, and adds the results up. The words with the largest
positive products are the ones that pushed the complaint toward the team the
model chose.

That is a description of this model's arithmetic. It is not the consumer's
reason for complaining, and it is not a judgement about the company.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def routing_words(pipeline, narrative: str, team: str, top: int = config.TOP_WORDS) -> pd.DataFrame:
    """The words that pushed ONE complaint toward ONE team, strongest first.

    Returns up to ``top`` rows; a very short complaint can produce fewer, and no
    row is ever padded in.
    """
    vectorizer = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["lr"]
    team_index = list(classifier.classes_).index(team)

    values = vectorizer.transform([narrative]).toarray()[0]
    contributions = values * classifier.coef_[team_index]
    order = np.argsort(-contributions)[:top]
    names = vectorizer.get_feature_names_out()

    rows = [
        {
            "Word or phrase": names[index],
            "Push toward this team": float(contributions[index]),
        }
        for index in order
        if contributions[index] > 0
    ]
    return pd.DataFrame(rows)


def routing_words_json(pipeline, narrative: str, team: str) -> list[dict]:
    """The same words, rounded, ready for the manifest's JSON column."""
    frame = routing_words(pipeline, narrative, team)
    return [
        {"word": row["Word or phrase"], "push": round(row["Push toward this team"], 4)}
        for _, row in frame.iterrows()
    ]


def team_signature_words(pipeline, team: str, top: int = 12) -> pd.DataFrame:
    """The words this team's weights favour most, across all complaints.

    A model-level view, not a complaint-level one: these are the words that would
    push any complaint toward the team if it contained them.
    """
    classifier = pipeline.named_steps["lr"]
    names = pipeline.named_steps["tfidf"].get_feature_names_out()
    weights = classifier.coef_[list(classifier.classes_).index(team)]
    order = np.argsort(-weights)[:top]
    return pd.DataFrame(
        {
            "Team": team,
            "Word or phrase": names[order],
            "Weight for this team": weights[order].round(3),
        }
    )


def signature_table(pipeline, teams: list[str] | None = None, top: int = 6) -> pd.DataFrame:
    """One row per team: its strongest words, as a readable comma list."""
    rows = []
    for team in teams or config.TEAMS:
        words = team_signature_words(pipeline, team, top)["Word or phrase"].tolist()
        rows.append({"Team": team, f"Its {top} strongest words": ", ".join(words)})
    return pd.DataFrame(rows)


def route_card(pipeline, row: pd.Series) -> pd.DataFrame:
    """One complaint end to end: what it is, what the model said, what happens.

    ``row`` is a test-split row, so the true team is available and is shown
    separately from the prediction - never blended into it.
    """
    probabilities = pipeline.predict_proba([row[config.TEXT_COLUMN]])[0]
    classes = pipeline.named_steps["lr"].classes_
    predicted = classes[int(np.argmax(probabilities))]
    confidence = float(probabilities.max())
    route = (
        config.ROUTE_AUTO
        if confidence >= config.CONFIDENCE_THRESHOLD
        else config.ROUTE_TRIAGE
    )
    facts = [
        ("Complaint ID", row["complaint_id"]),
        ("Received", row["date_received"]),
        ("CFPB issue field (not shown to the model)", row["issue"]),
        ("Characters in the narrative", f"{len(row[config.TEXT_COLUMN]):,}"),
        ("Model's team", predicted),
        ("Confidence", f"{confidence:.3f}"),
        ("Threshold", f"{config.CONFIDENCE_THRESHOLD}"),
        ("Route", route),
        ("What happens next", config.ROUTE_ACTIONS[route]),
        ("Team it actually belonged to", row[config.TARGET]),
        ("Model was", "right" if predicted == row[config.TARGET] else "WRONG"),
    ]
    return pd.DataFrame(facts, columns=["Field", "Value"])


def team_probabilities(pipeline, narrative: str) -> pd.DataFrame:
    """All eight team probabilities for one complaint, largest first."""
    classifier = pipeline.named_steps["lr"]
    probabilities = pipeline.predict_proba([narrative])[0]
    return (
        pd.DataFrame({"Team": classifier.classes_, "Probability": probabilities})
        .sort_values("Probability", ascending=False)
        .reset_index(drop=True)
    )
