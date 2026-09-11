#!/usr/bin/env python3
"""scripts/gen_data.py — 从 front_desk_spec.md 机械生成数据文件（spec v1.2 §4.1）。

解析 spec 中以 `<!-- GEN:文件路径 -->` 单独成行标记、紧跟其后的代码块，两种模式：

- 默认模式（无参数）：逐字写入对应路径，然后逐字反查（写出的内容与代码块完全一致，
  否则报错退出）。
- --check 模式：只读，不写任何文件。逐字比对现有生成文件与 spec 代码块；有任何文件
  缺失或内容不一致，打印文件路径和第一处不同的行号，exit 1；全部一致则 exit 0。

不得手工编辑生成的文件，由 --check 在提交时强制执行。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "front_desk_spec.md"

# 必须整行匹配：这样 §4.1 正文里行内反引号提到的标记不会被误当成真标记。
MARKER = re.compile(r"^<!-- GEN:(\S+) -->$")
FENCE_OPEN = re.compile(r"^```[A-Za-z0-9]*$")
FENCE_CLOSE = "```"


def die(msg):
    print(f"gen_data: 错误：{msg}", file=sys.stderr)
    sys.exit(1)


def check_relpath(rel, lineno):
    p = Path(rel)
    if p.is_absolute() or rel.startswith("/"):
        die(f"spec 第 {lineno} 行：GEN 路径必须是相对路径：{rel}")
    if ".." in p.parts:
        die(f"spec 第 {lineno} 行：GEN 路径不得包含 ..：{rel}")
    target = (ROOT / p).resolve()
    if ROOT not in target.parents:
        die(f"spec 第 {lineno} 行：GEN 路径解析后落在仓库外：{rel}")
    return target


def parse_blocks():
    """返回 [(相对路径, 内容, spec 行号)]。"""
    if not SPEC.is_file():
        die(f"找不到 spec：{SPEC}")
    lines = SPEC.read_text(encoding="utf-8").split("\n")
    blocks = []
    seen = {}
    i = 0
    while i < len(lines):
        m = MARKER.match(lines[i])
        if not m:
            i += 1
            continue
        lineno = i + 1
        rel = m.group(1)
        if i + 1 >= len(lines) or not FENCE_OPEN.match(lines[i + 1]):
            die(f"spec 第 {lineno} 行的 GEN 标记后面不是代码块围栏")
        j = i + 2
        body = []
        while j < len(lines) and lines[j] != FENCE_CLOSE:
            body.append(lines[j])
            j += 1
        if j >= len(lines):
            die(f"spec 第 {lineno} 行的 GEN 代码块围栏未闭合")
        if rel in seen:
            die(f"GEN 路径重复：{rel}（spec 第 {seen[rel]} 行和第 {lineno} 行）")
        seen[rel] = lineno
        check_relpath(rel, lineno)
        blocks.append((rel, "".join(line + "\n" for line in body), lineno))
        i = j + 1
    if not blocks:
        die("spec 中没有解析到任何 GEN 代码块")
    return blocks


def first_diff_line(actual, expected):
    """返回第一处不同的行号（1 起）。"""
    a = actual.split("\n")
    e = expected.split("\n")
    for n, (x, y) in enumerate(zip(a, e), start=1):
        if x != y:
            return n
    return min(len(a), len(e)) + 1


def run_default(blocks):
    print(f"gen_data: spec = {SPEC.name}（{len(blocks)} 个 GEN 块）")
    for rel, content, _ in blocks:
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        # 逐字反查：读回来与代码块逐字节比对
        actual = target.read_bytes()
        expected = content.encode("utf-8")
        if actual != expected:
            n = first_diff_line(actual.decode("utf-8", "replace"), content)
            die(f"反查失败：{rel} 与 spec 代码块第 {n} 行起不一致")
        print(f"  {rel}  {len(content.splitlines())} 行  {len(expected)} 字节  OK")
    print(f"反查通过: {len(blocks)}/{len(blocks)}")
    return 0


def run_check(blocks):
    problems = []
    for rel, content, _ in blocks:
        target = ROOT / rel
        if not target.is_file():
            problems.append(f"  {rel}  缺失")
            continue
        actual = target.read_bytes()
        expected = content.encode("utf-8")
        if actual != expected:
            n = first_diff_line(actual.decode("utf-8", "replace"), content)
            problems.append(f"  {rel}  第 {n} 行起与 spec 不一致")
    if problems:
        print("gen_data: --check 失败 —— 生成文件与 spec 不一致：", file=sys.stderr)
        for line in problems:
            print(line, file=sys.stderr)
        print(
            "gen_data: 不得手工编辑生成的文件；跑 `uv run scripts/gen_data.py` 重新生成。",
            file=sys.stderr,
        )
        return 1
    print(f"--check 通过: {len(blocks)}/{len(blocks)}")
    return 0


def main(argv):
    if argv == []:
        mode = "write"
    elif argv == ["--check"]:
        mode = "check"
    else:
        die(f"用法：gen_data.py [--check]（收到：{' '.join(argv)}）")
    blocks = parse_blocks()
    return run_default(blocks) if mode == "write" else run_check(blocks)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
