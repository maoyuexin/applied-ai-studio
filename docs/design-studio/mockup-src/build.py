"""Build docs/design-studio/ux-mockup.html: inline the thumbnails so the mockup is one offline file."""
import base64
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "ux-mockup.html"


def wave(seed: int) -> str:
    rng = random.Random(seed)
    return "".join(f'<i style="height:{rng.randint(5, 28)}px"></i>' for _ in range(46))


html = (HERE / "template.html").read_text()
thumbs = {p.stem: "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode() for p in (HERE / "thumbs").glob("*.jpg")}
for n in range(1, 5):
    thumbs[f"wave{n}"] = wave(n)
missing = set(re.findall(r"\{\{(\w+)\}\}", html)) - thumbs.keys()
if missing:
    raise SystemExit(f"missing placeholders: {sorted(missing)}")
html = re.sub(r"\{\{(\w+)\}\}", lambda m: thumbs[m.group(1)], html)
OUT.write_text(html)
print(f"wrote {OUT} ({len(html) / 1024:.0f} KB)")
