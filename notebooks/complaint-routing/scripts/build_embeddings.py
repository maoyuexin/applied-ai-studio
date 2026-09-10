"""Precompute the MiniLM embeddings the notebook's representation comparison uses.

WHY THIS SCRIPT EXISTS
======================

The notebook compares two ways of turning a complaint into numbers: TF-IDF word
counts, and sentence embeddings from ``sentence-transformers/all-MiniLM-L6-v2``.
Producing those embeddings live would mean a 183 MB model download and about
two minutes of CPU work in the middle of class. So they are computed once, here,
and committed as float16 parquet. The notebook loads them and never touches the
network or the transformer library.

WHAT IT EMBEDS
==============

A fixed comparison set, so the comparison is fair:

- ``complaintlab.models.comparison_subsample`` picks 15,000 training complaints,
  stratified by team with seed 42 - the same ids on every machine.
- the full 8,728-complaint validation split.

Both representations in the notebook are fitted on exactly these 15,000 rows and
scored on exactly these 8,728 rows, so the only thing that differs between them
is the representation.

STORAGE
-------

384 columns named ``dim_000`` ... ``dim_383``, stored as float16 next to the
complaint id. float16 keeps about three decimal digits, which is far more than
a logistic regression needs to separate eight teams, and it halves the committed
size. Parquet's BYTE_STREAM_SPLIT encoding is applied on top: it groups the
high bytes of every value together and the low bytes together, which compresses
much better than interleaved floats and takes both files from 23.7 MB to about
17 MB. Both choices are lossless with respect to the float16 values written.

USAGE
=====

    python scripts/build_embeddings.py            # writes both parquets
    python scripts/build_embeddings.py --check    # verifies what is committed

The first run downloads the model into the local Hugging Face cache. That is a
one-time author-side cost, never a classroom one.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaintlab import config, data, models  # noqa: E402

BATCH_SIZE = 64
DIMENSION_COLUMNS = [f"dim_{i:03d}" for i in range(config.EMBEDDING_DIM)]


def to_frame(complaint_ids: pd.Series, embeddings: np.ndarray) -> pd.DataFrame:
    frame = pd.DataFrame(
        embeddings.astype(np.float16), columns=DIMENSION_COLUMNS
    )
    frame.insert(0, "complaint_id", complaint_ids.to_numpy())
    return frame


def write(frame: pd.DataFrame, path: Path) -> None:
    """Write float16 columns with BYTE_STREAM_SPLIT + zstd."""
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False),
        path,
        compression="zstd",
        compression_level=9,
        use_dictionary=False,
        column_encoding={column: "BYTE_STREAM_SPLIT" for column in DIMENSION_COLUMNS},
    )


def build() -> None:
    from sentence_transformers import SentenceTransformer

    splits = data.load_splits()
    subsample = models.comparison_subsample(splits["train"])
    validation = splits["validation"]
    print(
        f"Comparison set: {len(subsample):,} training complaints "
        f"(stratified, seed {config.RANDOM_STATE}) + {len(validation):,} validation complaints"
    )
    print(f"Loading {config.EMBEDDING_MODEL} on CPU (downloads once, then cached)...")
    encoder = SentenceTransformer(config.EMBEDDING_MODEL, device="cpu")

    for name, frame, path in (
        ("train", subsample, config.EMBEDDINGS_TRAIN_PARQUET),
        ("validation", validation, config.EMBEDDINGS_VAL_PARQUET),
    ):
        start = time.perf_counter()
        vectors = encoder.encode(
            frame[config.TEXT_COLUMN].tolist(),
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        )
        seconds = time.perf_counter() - start
        write(to_frame(frame["complaint_id"], vectors), path)
        print(
            f"  {path.name:<34} {len(frame):>6,} rows x {config.EMBEDDING_DIM} float16  "
            f"{path.stat().st_size / 1e6:5.1f} MB  encoded in {seconds:.0f}s "
            f"({len(frame) / seconds:.0f} complaints/s)"
        )
    check()


def check() -> None:
    """Verify the committed embeddings line up with the committed splits."""
    splits = data.load_splits()
    subsample = models.comparison_subsample(splits["train"])
    pairs = (
        ("train subsample", subsample, config.EMBEDDINGS_TRAIN_PARQUET),
        ("validation", splits["validation"], config.EMBEDDINGS_VAL_PARQUET),
    )
    total_mb = 0.0
    for name, frame, path in pairs:
        matrix = models.load_embeddings(path, frame["complaint_id"])
        norms = np.linalg.norm(matrix, axis=1)
        size_mb = path.stat().st_size / 1e6
        total_mb += size_mb
        print(
            f"  {name:<16} {matrix.shape[0]:>6,} x {matrix.shape[1]}  "
            f"{size_mb:5.1f} MB  vector length {norms.mean():.3f} +/- {norms.std():.3f}"
        )
    print(f"  committed embedding total: {total_mb:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Only verify the committed parquets."
    )
    if parser.parse_args().check:
        check()
    else:
        build()
