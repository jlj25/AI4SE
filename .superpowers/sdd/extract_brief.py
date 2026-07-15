"""从 PLAN.md 提取指定 Task 的全文到 brief 文件。"""
import re
import sys
from pathlib import Path


def extract(plan_file: str, task_num: int) -> Path:
    plan = Path(plan_file).read_text(encoding="utf-8")
    lines = plan.splitlines()
    out: list[str] = []
    in_task = False
    for line in lines:
        if re.match(r"^#+\s+Task\s+" + str(task_num) + r"([^0-9]|$)", line):
            in_task = True
        elif re.match(r"^#+\s+Task\s+\d+", line) and in_task:
            break
        if in_task:
            out.append(line)
    result = "\n".join(out).strip()
    if not result:
        print(f"Task {task_num} not found in {plan_file}", file=sys.stderr)
        sys.exit(3)
    outpath = Path(f".superpowers/sdd/task-{task_num}-brief.md")
    outpath.write_text(result, encoding="utf-8")
    print(f"wrote {outpath}: {len(out)} lines")
    return outpath


if __name__ == "__main__":
    extract(sys.argv[1], int(sys.argv[2]))
