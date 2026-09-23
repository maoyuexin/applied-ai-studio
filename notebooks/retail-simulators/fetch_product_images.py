"""Download only the reviewed product photographs in the image manifest."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / "product-images.json").read_text())
    for code, record in manifest["products"].items():
        destination = HERE / record["file"]
        if destination.exists():
            with Image.open(destination) as image:
                image.verify()
            print(f"Verified {code}: cached photograph")
            continue
        request = Request(record["imageUrl"], headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            content = response.read(12_000_000)
        with Image.open(io.BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            if min(image.size) < 120:
                raise ValueError(f"Image too small for {code}: {image.size}")
            background = Image.new("RGB", image.size, "white")
            if image.mode in {"RGBA", "LA"}:
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            background.save(destination, "WEBP", quality=86, method=6)
        print(f"Downloaded {code}: {background.size}, {destination.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()