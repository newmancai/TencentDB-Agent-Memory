"""Download the two public main-experiment files at a fixed MIT revision."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

REVISION = "a8076d5608c93ba2a28983cd78aa99b01a163ae7"
FILES = {"questions_32k.csv": "persona_v1_questions_32k.csv", "shared_contexts_32k.jsonl": "persona_v1_shared_contexts_32k.jsonl"}


def main():
    p = argparse.ArgumentParser(); p.add_argument("output", type=Path); a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True); manifest = []
    for upstream, local in FILES.items():
        url = f"https://huggingface.co/datasets/bowen-upenn/PersonaMem-v1/resolve/{REVISION}/{upstream}"
        target = a.output / local
        if target.exists():
            raise FileExistsError(f"use a fresh download directory: {target}")
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        target.write_bytes(data)
        manifest.append(dict(file=local, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    (a.output / "download-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
