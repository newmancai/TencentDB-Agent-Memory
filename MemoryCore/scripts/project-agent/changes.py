"""Preserve a reviewable working-tree snapshot alongside an agent receipt."""

from pathlib import Path

from backend import run_command

GIT_TIMEOUT_SECONDS = 10
MAX_UNTRACKED_BYTES = 1024 * 1024


def _omission_reason(path: Path, state: Path) -> str | None:
    if path.is_symlink() or path.resolve().is_relative_to(state.resolve()):
        return "symlink_or_private_state"
    if not path.is_file() or path.stat().st_size > MAX_UNTRACKED_BYTES:
        return "not_regular_or_over_1MiB"
    return None


def capture_changes(workspace: Path, evidence: Path, state: Path) -> dict:
    revision = run_command(["git", "rev-parse", "HEAD"], workspace, GIT_TIMEOUT_SECONDS)
    if revision["returncode"] != 0:
        return {"status": "not_git", "scope": "working_tree_against_HEAD"}
    tracked = run_command(["git", "diff", "--binary", "HEAD"], workspace, GIT_TIMEOUT_SECONDS)
    untracked = run_command(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        workspace,
        GIT_TIMEOUT_SECONDS,
    )
    if tracked["returncode"] != 0 or untracked["returncode"] != 0:
        return {"status": "unavailable", "scope": "working_tree_against_HEAD"}
    patches = [tracked["stdout"]]
    omitted = []
    for name in untracked["stdout"].split("\0"):
        if not name:
            continue
        path = workspace / name
        if reason := _omission_reason(path, state):
            omitted.append({"path": name, "reason": reason})
            continue
        result = run_command(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", name],
            workspace,
            GIT_TIMEOUT_SECONDS,
        )
        if result["returncode"] in (0, 1):
            patches.append(result["stdout"])
        else:
            omitted.append({"path": name, "reason": "diff_failed"})
    path = evidence / "changes.diff"
    path.write_text("\n".join(patches))
    return {
        "status": "captured",
        "base_commit": revision["stdout"].strip(),
        "diff": str(path),
        "scope": "working_tree_against_HEAD_including_preexisting_edits",
        "omitted": omitted,
    }
