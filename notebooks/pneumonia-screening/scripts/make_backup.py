"""Export a self-contained offline HTML copy of the executed notebook."""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT_DIR / "01_pneumonia_build.ipynb"
BACKUP_DIR = PROJECT_DIR / "backup"
OUTPUT = BACKUP_DIR / "01_pneumonia_build.html"
REQUIRE_URL = "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js"


def main() -> None:
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
    html = re.sub(r"[ \t]+(?=\r?\n)", "", html)
    OUTPUT.write_text(html, encoding="utf-8")

    remote_scripts = re.findall(r'<script[^>]*src="(https?://[^"]+)"', html)
    remote_styles = re.findall(r'<link[^>]*href="(https?://[^"]+)"', html)
    remote_images = re.findall(r'<img[^>]*src="(https?://[^"]+)"', html)
    remote_resources = remote_scripts + remote_styles + remote_images
    print(f"Wrote {OUTPUT.relative_to(PROJECT_DIR)} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
    print(f"Remote loaded resources: {remote_resources if remote_resources else 'none'}")
    if remote_resources:
        raise SystemExit("Backup still loads a remote resource.")


if __name__ == "__main__":
    main()