"""Build the fixed mentor submission bundle without dependencies or local evidence."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
IMPLEMENTATION = "84ba04dee30bd72d7e9f9e57365c5015e7cd5e6d"
BASE = "0ddea892f1e362b4b937b2b38d23beb2a5ac4329"
SOURCE_ARCHIVE = HERE / "B_E_实现与测试源码_84ba04d.tar.gz"
PATCH_OUTPUT = HERE / "B_E_完整方案_相对MemoryCore基座.patch"
MANIFEST = HERE / "MANIFEST.sha256"
PACKAGE = HERE / "B_E_导师最终交付_2026-09-14.zip"


def run(*args: str, capture: bool = False) -> bytes:
    result = subprocess.run(
        args,
        cwd=REPO,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else b""


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    report_md = HERE / "B_E_方案介绍与测试结论报告.md"
    report_pdf = HERE / "B_E_方案介绍与测试结论报告.pdf"
    if not report_md.exists() or not report_pdf.exists():
        raise SystemExit("Render the report first with render_report.py")

    run("git", "cat-file", "-e", f"{IMPLEMENTATION}^{{commit}}")
    run("git", "cat-file", "-e", f"{BASE}^{{commit}}")
    run(
        "git", "archive", "--format=tar.gz", f"--output={SOURCE_ARCHIVE}",
        IMPLEMENTATION, "MemoryCore", ".github",
    )
    PATCH_OUTPUT.write_bytes(run(
        "git", "diff", "--binary", f"{BASE}..{IMPLEMENTATION}", "--", ".github", "MemoryCore",
        capture=True,
    ))

    outside_files = [
        report_pdf,
        report_md,
        SOURCE_ARCHIVE,
        PATCH_OUTPUT,
        HERE / "CODE_AND_TEST_INDEX.md",
        HERE / "REVISION.txt",
    ]
    manifest_text = "".join(
        f"{digest(path)}  {path.name}\n" for path in outside_files
    )
    MANIFEST.write_text(manifest_text, encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="be-mentor-delivery-") as temporary:
        root = Path(temporary) / "B_E_导师最终交付_2026-09-14"
        root.mkdir()
        mapping = {
            HERE / "README.md": "README.md",
            report_pdf: "01_B_E_方案介绍与测试结论报告.pdf",
            report_md: "01_B_E_方案介绍与测试结论报告.md",
            SOURCE_ARCHIVE: "02_B_E_实现与测试源码_84ba04d.tar.gz",
            PATCH_OUTPUT: "03_B_E_完整方案_相对MemoryCore基座.patch",
            HERE / "CODE_AND_TEST_INDEX.md": "04_CODE_AND_TEST_INDEX.md",
            HERE / "REVISION.txt": "05_REVISION.txt",
        }
        for source, destination in mapping.items():
            shutil.copy2(source, root / destination)
        package_manifest = "".join(
            f"{digest(root / destination)}  {destination}\n"
            for destination in mapping.values()
        )
        (root / "06_MANIFEST.sha256").write_text(package_manifest, encoding="utf-8")

        with zipfile.ZipFile(PACKAGE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(Path(temporary)))

    with zipfile.ZipFile(PACKAGE) as archive:
        prefix = "B_E_导师最终交付_2026-09-14/"
        manifest = archive.read(prefix + "06_MANIFEST.sha256").decode("utf-8")
        for line in manifest.splitlines():
            expected, name = line.split("  ", 1)
            actual = sha256(archive.read(prefix + name)).hexdigest()
            if actual != expected:
                raise RuntimeError(f"package checksum mismatch: {name}")

    print(f"Built {PACKAGE} ({PACKAGE.stat().st_size} bytes)")
    print(manifest_text, end="")


if __name__ == "__main__":
    main()
