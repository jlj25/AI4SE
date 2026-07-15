"""生成 review Package：git log + diff stat + full diff 写入文件。"""
import subprocess
import sys
from pathlib import Path


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, encoding="utf-8",
    )
    return result.stdout


def generate(base: str, head: str) -> Path:
    log = _git(["log", "--oneline", f"{base}..{head}"])
    stat = _git(["diff", "--stat", f"{base}..{head}"])
    diff = _git(["diff", "-U10", f"{base}..{head}"])
    content = f"## Commits ({base}..{head})\n\n{log}\n## Stat\n\n{stat}\n## Full Diff\n\n{diff}"
    outpath = Path(f".superpowers/sdd/review-{base[:7]}-{head[:7]}.diff")
    outpath.write_text(content, encoding="utf-8")
    print(f"wrote {outpath}: {len(content)} chars")
    return outpath


if __name__ == "__main__":
    generate(sys.argv[1], sys.argv[2])
