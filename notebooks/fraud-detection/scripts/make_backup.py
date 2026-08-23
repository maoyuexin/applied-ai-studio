"""Export a genuinely self-contained HTML copy of the executed notebook.

`nbconvert --to html` inlines the Plotly bundle but still pulls `require.js` from
a CDN, and Plotly's notebook renderer needs it to draw. That makes the "offline
backup" quietly dependent on the very network that failed. This script inlines
require.js and drops the unused MathJax tags, so the result opens with no
network at all.

    python scripts/make_backup.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
NOTEBOOK = PROJECT_DIR / "01_fraud_build.ipynb"
BACKUP_DIR = PROJECT_DIR / "backup"
OUTPUT = BACKUP_DIR / "01_fraud_build.html"

REQUIRE_URL = "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js"


def main() -> None:
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

    # A lambda, not a string: require.js is full of backslashes and re.sub would
    # read them as escape sequences in the replacement.
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

    remaining = re.findall(r'<script[^>]*src="(https?://[^"]+)"', html)
    print(f"\nWrote {OUTPUT.relative_to(PROJECT_DIR)}  ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
    print(f"Remote scripts remaining: {remaining if remaining else 'none -- fully offline'}")
    if remaining:
        raise SystemExit("Backup still depends on the network. Do not rely on it in class.")


if __name__ == "__main__":
    main()
