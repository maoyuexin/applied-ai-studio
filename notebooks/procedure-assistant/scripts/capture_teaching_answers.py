"""Record real LLM outputs for offline classroom replay; requires Copilot sign-in."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raglab import index, teaching


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=teaching.CAPTURE)
    arguments = parser.parse_args()
    chunks = teaching.prepare_chunks(teaching.load_sources())
    retriever = index.EmbedRetriever(chunks)
    result = asyncio.run(teaching.capture_answers(retriever, arguments.output))
    for case, record in zip(teaching.CASES, result["records"]):
        response = record["response"]
        print(f"{case['name']}: {response['answer']} [{response['citation']}]")
    print(f"Saved {len(result['records'])} real {result['model']} responses to {arguments.output}")


if __name__ == "__main__":
    main()