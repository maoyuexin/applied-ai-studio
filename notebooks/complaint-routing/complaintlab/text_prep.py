"""Turning complaint text into numbers, and the small demonstrations that show it.

Two representations appear in this lab:

- **TF-IDF**, which counts words and 2-word phrases and weights each one by how
  rare it is across complaints. One complaint becomes a very wide, mostly-zero
  row of counts. Nothing about word order survives.
- **Sentence embeddings**, which run the complaint through a small transformer
  and read out one fixed-length vector of 384 numbers.

Everything here is either the fitted TF-IDF object itself or a worked example
small enough to read in the notebook.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from . import config

# A deliberately tiny corpus: three one-sentence complaints, one per team, short
# enough that every number in the resulting table can be checked by hand.
WORKED_EXAMPLE_CORPUS = [
    "my credit card was charged twice for one purchase",
    "the collector called my job about an old debt",
    "my credit report shows an account i never opened",
]
WORKED_EXAMPLE_TEAMS = ["Credit cards", "Debt collection", "Credit reporting"]
WORKED_EXAMPLE_SENTENCE = WORKED_EXAMPLE_CORPUS[0]


def build_vectorizer(min_df: int | None = None) -> TfidfVectorizer:
    """The frozen TF-IDF settings, in one place."""
    return TfidfVectorizer(
        ngram_range=config.TFIDF_NGRAM_RANGE,
        min_df=config.TFIDF_MIN_DF if min_df is None else min_df,
        max_features=config.TFIDF_MAX_FEATURES,
        sublinear_tf=config.TFIDF_SUBLINEAR_TF,
        strip_accents=config.TFIDF_STRIP_ACCENTS,
    )


def worked_example() -> pd.DataFrame:
    """Turn one short sentence into TF-IDF numbers, showing every step.

    Fitted on the three-sentence corpus above so the document frequencies are
    small enough to verify: a term in all three sentences gets a low weight, a
    term in one sentence gets a high one.
    """
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(WORKED_EXAMPLE_CORPUS)
    names = np.array(vectorizer.get_feature_names_out())
    row = matrix[0].toarray()[0]
    present = np.flatnonzero(row)
    document_counts = (matrix > 0).sum(axis=0).A1
    frame = pd.DataFrame(
        {
            "Word or 2-word phrase": names[present],
            "In how many of the 3 complaints": document_counts[present],
            "TF-IDF weight in complaint 1": row[present].round(3),
        }
    )
    return frame.sort_values("TF-IDF weight in complaint 1", ascending=False).reset_index(
        drop=True
    )


def worked_example_shape() -> pd.DataFrame:
    """How wide the row gets: 3 tiny complaints vs the real training split."""
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(WORKED_EXAMPLE_CORPUS)
    row = matrix[0].toarray()[0]
    return pd.DataFrame(
        [
            {
                "Corpus": "the 3 toy complaints above",
                "Columns (words and phrases)": matrix.shape[1],
                "Non-zero values in complaint 1": int((row != 0).sum()),
                "Share of the row that is zero": 1 - (row != 0).sum() / matrix.shape[1],
            }
        ]
    )


def vocabulary_profile(vectorizer: TfidfVectorizer, narratives: pd.Series) -> pd.DataFrame:
    """How the fitted vocabulary and one real complaint's row actually look."""
    matrix = vectorizer.transform(narratives.head(1))
    row = matrix.toarray()[0]
    n_features = len(vectorizer.vocabulary_)
    single_words = sum(1 for term in vectorizer.vocabulary_ if " " not in term)
    return pd.DataFrame(
        [
            ("Columns the model uses", f"{n_features:,}"),
            ("Single words among them", f"{single_words:,}"),
            ("2-word phrases among them", f"{n_features - single_words:,}"),
            ("Non-zero values for one real complaint", f"{int((row != 0).sum()):,}"),
            ("Share of that row that is zero", f"{1 - (row != 0).sum() / n_features:.4%}"),
        ],
        columns=["The complaint as numbers", "Value"],
    )


def length_profile(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Character and word counts per split, plus the long tail."""
    rows = []
    for name, part in splits.items():
        characters = part[config.TEXT_COLUMN].str.len()
        words = part[config.TEXT_COLUMN].str.split().str.len()
        rows.append(
            {
                "Split": name,
                "Median words": int(words.median()),
                "Median characters": int(characters.median()),
                "90th percentile characters": int(characters.quantile(0.90)),
                "Longest characters": int(characters.max()),
                "Shortest characters": int(characters.min()),
            }
        )
    return pd.DataFrame(rows)


def redaction_profile(narratives: pd.Series) -> pd.DataFrame:
    """How often the CFPB's XXXX redaction appears in the training narratives."""
    has_redaction = narratives.str.contains("XXXX", regex=False)
    counts = narratives.str.count("XXXX")
    return pd.DataFrame(
        [
            ("Complaints containing at least one XXXX", f"{has_redaction.mean():.1%}"),
            ("Median XXXX blocks in those complaints", f"{counts[has_redaction].median():.0f}"),
            ("Most XXXX blocks in one complaint", f"{int(counts.max()):,}"),
        ],
        columns=["Redaction by the publisher", "Value"],
    )


def token_truncation_profile(narratives: pd.Series, max_tokens: int = 256) -> pd.DataFrame:
    """Share of complaints longer than the embedding model can read.

    Word count is a deliberate under-estimate of wordpiece tokens, so the true
    truncated share is higher than the number reported here.
    """
    words = narratives.str.split().str.len()
    return pd.DataFrame(
        [
            (
                f"Complaints with more than {max_tokens} words",
                f"{(words > max_tokens).mean():.1%}",
            ),
            ("Median words per complaint", f"{words.median():.0f}"),
            (
                "Words in the longest complaint",
                f"{int(words.max()):,}",
            ),
        ],
        columns=["Length against the 256-token limit", "Value"],
    )
