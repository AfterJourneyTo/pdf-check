# 直接替换到你的 keep_first_pages.py 中

import re
from typing import List, Optional, Tuple, Collection
import pdfplumber
from pypdf import PdfReader, PdfWriter

DEFAULT_KEYWORDS = ["报账单", "报帐单", "报销单", "费用报销单", "费用报账单"]
DEFAULT_ID_REGEX = [r"(?:报销单号|报账单号|单号|编号)\s*[:：]?\s*([A-Za-z0-9\-_]+)"]
DEFAULT_FIRST_PAGE_REGEX = [r"第\s*1\s*页\b", r"\bPage\s*1\b", r"\b1\s*/\s*\d+\b"]
FIELD_LABELS = ["报销人", "部门", "费用类别", "申请日期", "金额", "合计", "大写", "小写"]


def _compile(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p) for p in patterns]


def _extract_text_top(page, top_ratio=0.35) -> str:
    w, h = page.width, page.height
    top_bbox = (0, h * (1 - top_ratio), w, h)
    try:
        return (page.crop(top_bbox).extract_text() or "")
    except Exception:
        return page.extract_text() or ""


def _find_first_group(pats: List[re.Pattern], text: str) -> Optional[str]:
    for p in pats:
        m = p.search(text)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return None


def _has_any(text: str, kws: List[str]) -> bool:
    return any(k in text for k in kws)


def _header_score(text_top: str, text_full: str,
                  id_pats: List[re.Pattern],
                  first_pats: List[re.Pattern],
                  keywords: List[str]) -> int:
    """给“像首页”的页面打分：越高越像首页。"""
    score = 0
    if _find_first_group(id_pats, text_top) or _find_first_group(id_pats, text_full):
        score += 5
    if _find_first_group(first_pats, text_top) or _find_first_group(first_pats, text_full):
        score += 3
    if _has_any(text_top, keywords):
        score += 2
    if _has_any(text_full, FIELD_LABELS):
        score += 1
    return score


_TOTAL_PAGE_PATTERNS = [
    # 第1页/共7页、共 7 页
    re.compile(r"第\s*1\s*页\s*/?\s*共\s*(\d+)\s*页"),
    re.compile(r"共\s*(\d+)\s*页"),
    # 1/7、Page 1 of 7
    re.compile(r"\b1\s*/\s*(\d+)\b"),
    re.compile(r"Page\s*1\s*of\s*(\d+)", re.IGNORECASE),
]


def parse_total_pages(text: str) -> Optional[int]:
    """从文本里解析“总页数 N”，仅在当前页明确是第1页的情况下可靠。"""
    for p in _TOTAL_PAGE_PATTERNS:
        m = p.search(text)
        if m:
            try:
                n = int(m.group(1))
                if 1 < n < 200:  # 简单上限，避免噪声
                    return n
            except ValueError:
                pass
    return None


def keep_first_pages_auto(
        input_pdf: str,
        output_pdf: str,
        *,
        keywords: Optional[List[str]] = None,
        id_regex: Optional[List[str]] = None,
        first_page_regex: Optional[List[str]] = None,
        top_ratio: float = 0.35,
        # 非必需：如果你仍希望限制“合理间隔”，可给一个宽松区间（如 2~10）
        allowed_gaps: Optional[Collection[int]] = None,
        min_gap: int = 1,
) -> Tuple[int, List[int]]:
    """
    自动识别各报账单首页，仅保留首页并导出。
    关键点：识别到首页时，优先解析“共N页”，用 N 动态预测下一份首页位置；
          同时保留 ID 变化与启发式作为兜底，兼容 3/4/5/7 等任意页数。

    参数：
      - allowed_gaps: 可选，限制相邻首页的合理间距集合，如 {3,4,5,7} 或 range(2,11)
      - min_gap: 最小允许间距（避免连续页被误判为两份首页）

    返回：(保留页数, 首页索引列表)
    """
    keywords = keywords or DEFAULT_KEYWORDS
    id_pats = _compile(id_regex or DEFAULT_ID_REGEX)
    first_pats = _compile(first_page_regex or DEFAULT_FIRST_PAGE_REGEX)
    gap_set = set(allowed_gaps) if allowed_gaps else None

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    kept: List[int] = []
    last_kept_idx: Optional[int] = None
    last_id: Optional[str] = None
    expected_gap: Optional[int] = None  # 由“共N页”推断得到

    with pdfplumber.open(input_pdf) as pdf:
        for i, page in enumerate(pdf.pages):
            text_top = _extract_text_top(page, top_ratio=top_ratio)
            text_full = text_top + "\n" + (page.extract_text() or "")

            # 解析证据
            cur_id = _find_first_group(id_pats, text_top) or _find_first_group(id_pats, text_full)
            is_first_mark = bool(_find_first_group(first_pats, text_top) or _find_first_group(first_pats, text_full))
            total_pages = parse_total_pages(text_full)
            score = _header_score(text_top, text_full, id_pats, first_pats, keywords)

            def gap_ok(idx: int) -> bool:
                if last_kept_idx is None:
                    return True
                gap = idx - last_kept_idx
                if gap < max(1, min_gap):
                    return False
                if gap_set and gap not in gap_set:
                    # 若给了限制集合，严格限制
                    return False
                return True

            accept = False

            # 规则1：单号变化最强（不依赖间距）
            if cur_id and cur_id != last_id and gap_ok(i):
                accept = True
            # 规则2：明确“第1页”标记，或“1/总页”，且间距合理
            elif (is_first_mark or total_pages) and gap_ok(i):
                accept = True
            # 规则3：启发式高分兜底（避免错过真正首页）
            elif score >= 5 and gap_ok(i):
                accept = True
            # 规则4：如果有“预测间隔 expected_gap”，且正好命中，也接受
            elif expected_gap and last_kept_idx is not None and i == last_kept_idx + expected_gap and gap_ok(i):
                accept = True

            if not accept:
                continue

            # 接受为首页
            writer.add_page(reader.pages[i])
            kept.append(i)
            last_kept_idx = i
            if cur_id:
                last_id = cur_id

            # 更新动态“预测下一份首页间隔”
            if total_pages:  # 解析到了“共N页”
                expected_gap = total_pages
            else:
                # 解析不到就不预测；若你愿意，用近似：最近一次 N 或经验均值
                expected_gap = None

    if not kept:
        raise RuntimeError("未识别到首页；请检查是否为扫描件（需先OCR），或调整正则/关键词。")

    with open(output_pdf, "wb") as f:
        writer.write(f)

    return len(kept), kept
