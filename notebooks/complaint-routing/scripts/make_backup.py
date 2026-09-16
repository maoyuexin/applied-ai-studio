"""Export a self-contained offline HTML copy of the executed notebook.

nbconvert leaves two CDN script tags in its HTML output. Both are removed here:
require.js is downloaded once and inlined, and the MathJax tag is dropped
because this notebook contains no mathematics. The result loads with no network
at all. Plotly is embedded independently when saved outputs lack its shared
renderer, so removing the first chart does not break the remaining figures.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from plotly.offline import get_plotlyjs


PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT_DIR / "01_complaint_build.ipynb"
BACKUP_DIR = PROJECT_DIR / "backup"
OUTPUT = BACKUP_DIR / "01_complaint_build.html"
REQUIRE_URL = "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js"


def collapse_walkthrough_code(document: BeautifulSoup) -> int:
    """Keep example code accessible without putting it ahead of the visual output."""
    count = 0
    for cell in document.select(".jp-CodeCell"):
        source = cell.select_one(".jp-InputArea")
        if source is None or cell.select_one("details.walkthrough-code"):
            continue
        if cell.select_one(".complaint-view") is None and "# 5.4 THE WORDS THAT CAUSED THE ROUTE" not in source.get_text():
            continue
        details = document.new_tag("details", attrs={"class": "walkthrough-code"})
        summary = document.new_tag("summary")
        summary.string = "Python code"
        source.wrap(details)
        details.insert(0, summary)
        count += 1
    if count and document.head is not None:
        style = document.new_tag("style", id="walkthrough-code-style")
        style.string = """
        .walkthrough-code { margin: 0 0 10px; }
        .walkthrough-code > summary { cursor: pointer; min-height: 44px; padding: 10px 12px;
          color: #505761; font-size: 14px; border-bottom: 1px solid #d8dde2; }
        .walkthrough-code > summary:focus-visible { outline: 3px solid #08766d; }
        """
        document.head.append(style)
    return count


def main() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "scripts/validate_teaching_notebook.py"), str(NOTEBOOK)],
        check=True,
    )
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "nbconvert",
            "--to",
            "html",
            "--embed-images",
            "--output",
            str(OUTPUT),
            str(NOTEBOOK),
        ],
        check=True,
        cwd=PROJECT_DIR,
    )
    html = OUTPUT.read_text(encoding="utf-8")

    print("Inlining require.js ...")
    with urllib.request.urlopen(REQUIRE_URL, timeout=30) as response:
        require_js = response.read().decode("utf-8")
    html = re.sub(
        r'<script[^>]*src="' + re.escape(REQUIRE_URL) + r'"[^>]*>\s*</script>',
        lambda _: f"<script>{require_js}</script>",
        html,
    )
    html = re.sub(
        r'<script[^>]*src="https://cdnjs\.cloudflare\.com/ajax/libs/mathjax[^"]*"[^>]*>\s*</script>',
        "",
        html,
    )
    document = BeautifulSoup(html, "html.parser")
    if document.select_one(".plotly-graph-div") and not any(
        "plotly.js v" in (script.string or "") for script in document.find_all("script")
    ):
        if document.head is None:
            raise ValueError("Notebook export is missing its HTML head.")
        renderer = document.new_tag("script", id="offline-plotly-runtime")
        renderer.string = get_plotlyjs()
        document.head.insert(0, renderer)
        print("Embedded Plotly renderer from the installed package.")
    collapsed = collapse_walkthrough_code(document)
    html = str(document)
    print(f"Walkthrough code disclosures: {collapsed}")
    OUTPUT.write_text(html, encoding="utf-8")

    remote_scripts = re.findall(r'<script[^>]*src="(https?://[^"]+)"', html)
    remote_styles = re.findall(r'<link[^>]*href="(https?://[^"]+)"', html)
    remote_images = re.findall(r'<img[^>]*src="(https?://[^"]+)"', html)
    remote_resources = remote_scripts + remote_styles + remote_images
    plotly_divs = len(re.findall(r'class="plotly-graph-div"', html))
    print(f"Wrote {OUTPUT.relative_to(PROJECT_DIR)} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
    print(f"Plotly figures embedded: {plotly_divs}")
    print(f"Remote loaded resources: {remote_resources if remote_resources else 'none'}")
    if remote_resources:
        raise SystemExit("Backup still loads a remote resource.")


if __name__ == "__main__":
    main()
