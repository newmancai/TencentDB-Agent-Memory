"""Download only the seven predeclared public RAG graphs, approximately180MB."""
import json
import sys
import urllib.request
from pathlib import Path

REVISION = '2a12240b36330aab5f40207c078eba0a2cc41194'
FILES = [f'rag/locomo_locomo-{i}.json' for i in (1, 10, 2, 5)] + [
    f'rag/realmem_realmem-{name}.json' for name in ('Adeleke_Okonjo', 'Ethan_Hunt', 'Liam_O_Connor')]


def main():
    root = Path(sys.argv[1])
    (root / 'memtrace').mkdir(parents=True, exist_ok=True)
    records = []
    for path in FILES:
        target = root / 'memtrace' / path.replace('/', '-')
        if not target.exists():
            temporary = target.with_suffix('.part')
            with urllib.request.urlopen(f'https://huggingface.co/datasets/zjunlp/MemTraceBench/resolve/{REVISION}/{path}', timeout=60) as response, temporary.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            temporary.replace(target)
        records.append(dict(path=path, local=str(target.resolve())))
    (root / 'downloaded.json').write_text(json.dumps(records, indent=2))
    (root / 'source.json').write_text(json.dumps(dict(revision=REVISION, paths=FILES), indent=2))


if __name__ == '__main__':
    main()
