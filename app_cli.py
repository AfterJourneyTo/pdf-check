# app_cli.py
import argparse
from keep_first_pages import keep_first_pages_auto


def parse_int_set(s: str):
    if not s:
        return None
    parts = [p.strip() for p in s.split(",")]
    vals = set()
    for p in parts:
        if "-" in p:
            a, b = p.split("-", 1)
            vals.update(range(int(a), int(b) + 1))
        else:
            vals.add(int(p))
    return sorted(vals)


def main():
    ap = argparse.ArgumentParser(description="从合并PDF中仅保留每份报账单首页")
    ap.add_argument("input", help="输入PDF路径")
    ap.add_argument("output", help="输出PDF路径（仅首页）")
    ap.add_argument("--allowed-gaps", default="2-10",
                    help="相邻首页合理间距集合，逗号或区间：3,4,5,7 或 2-10（默认2-10）")
    ap.add_argument("--min-gap", type=int, default=1, help="最小间距（默认1）")
    ap.add_argument("--top-ratio", type=float, default=0.35, help="顶部文本比例(0~1)")
    args = ap.parse_args()

    allowed = parse_int_set(args.allowed_gaps) if args.allowed_gaps else None
    count, idxs = keep_first_pages_auto(
        input_pdf=args.input,
        output_pdf=args.output,
        allowed_gaps=allowed,
        min_gap=args.min_gap,
        top_ratio=args.top_ratio,
    )
    print(f"完成：保留 {count} 页；首页索引：{idxs}")


if __name__ == "__main__":
    main()
