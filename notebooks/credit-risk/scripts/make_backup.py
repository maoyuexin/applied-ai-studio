"""Export a genuinely self-contained offline HTML copy of the executed notebook.

`nbconvert --to html` already inlines the Plotly bundle that the notebook's
`notebook` renderer embedded in the first figure's output, but it still pulls
`require.js` from a CDN - and Plotly's notebook renderer needs require.js to
draw anything. That would make the "offline backup" quietly depend on the very
network that failed in the first place. This script inlines require.js, drops
the unused MathJax tags, and then refuses to finish unless the result loads no
remote script, stylesheet, or image at all.

    node scripts/venv-python.mjs notebooks/credit-risk/scripts/make_backup.py

The classroom copy is offline. Building it needs the network once, to fetch
require.js.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT_DIR / "01_credit_build.ipynb"
BACKUP_DIR = PROJECT_DIR / "backup"
OUTPUT = BACKUP_DIR / "01_credit_build.html"

REQUIRE_URL = "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js"


def main() -> None:
    if not NOTEBOOK.exists():
        raise SystemExit(f"{NOTEBOOK} does not exist. Build and execute the notebook first.")
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "scripts/validate_teaching_notebook.py"), str(NOTEBOOK)],
        check=True,
    )
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [sys.executable, "-m", "nbconvert", "--to", "html", "--embed-images",
         "--output", str(OUTPUT), str(NOTEBOOK)],
        check=True, cwd=PROJECT_DIR,
    )
    html = OUTPUT.read_text(encoding="utf-8")

    print("Inlining require.js ...")
    with urllib.request.urlopen(REQUIRE_URL, timeout=30) as response:
        require_js = response.read().decode("utf-8")

    # A lambda, not a replacement string: require.js is full of backslashes and
    # re.sub would read them as escape sequences in the replacement.
    html = re.sub(
        r'<script[^>]*src="' + re.escape(REQUIRE_URL) + r'"[^>]*>\s*</script>',
        lambda _: f"<script>{require_js}</script>",
        html,
    )
    html = re.sub(
        r'<script[^>]*src="https://cdnjs\.cloudflare\.com/ajax/libs/mathjax[^"]*"[^>]*>\s*</script>',
        "", html,
    )
    OUTPUT.write_text(html, encoding="utf-8")

    remote = (
        re.findall(r'<script[^>]*src="(https?://[^"]+)"', html)
        + re.findall(r'<link[^>]*href="(https?://[^"]+)"', html)
        + re.findall(r'<img[^>]*src="(https?://[^"]+)"', html)
    )
    figures = html.count("Plotly.newPlot")
    has_bundle = "plotly.min.js v" in html or "require.undef" in html

    print(f"\nWrote {OUTPUT.relative_to(PROJECT_DIR)}  ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
    print(f"Plotly figures embedded : {figures}")
    print(f"Plotly bundle inlined   : {has_bundle}")
    print(f"Remote resources        : {remote if remote else 'none -- fully offline'}")

    if remote:
        raise SystemExit("Backup still depends on the network. Do not rely on it in class.")
    if not has_bundle or figures == 0:
        raise SystemExit("Backup contains no inlined Plotly bundle or no figures.")


if __name__ == "__main__":
    main()
