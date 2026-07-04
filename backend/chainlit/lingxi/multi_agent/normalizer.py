"""MessageNormalizer：把用户原始输入标准化，供 Router 关键词匹配。

纯模块，不依赖 chainlit。
"""

import re
from dataclasses import dataclass


@dataclass
class NormalizedInput:
    text: str      # 原文：去首尾空白、折叠连续空白，保留大小写与标点
    compact: str   # 匹配文本：小写、全角转半角、去掉所有空白


def _to_halfwidth(s: str) -> str:
    """全角字符转半角（全角空格 U+3000 → 空格，FF01-FF5E → 对应 ASCII）。"""
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:
            code = 0x20
        elif 0xFF01 <= code <= 0xFF5E:
            code -= 0xFEE0
        out.append(chr(code))
    return "".join(out)


def normalize(raw: str) -> NormalizedInput:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    compact = re.sub(r"\s+", "", _to_halfwidth(text).lower())
    return NormalizedInput(text=text, compact=compact)
