from __future__ import annotations

import html
from typing import Callable

try:
    import markdown as md_lib
except ImportError:  # pragma: no cover
    md_lib = None

from usecases.ports import MarkdownRendererPort


class DefaultMarkdownRenderer(MarkdownRendererPort):
    """軽量な Markdown -> HTML 変換。markdown が無ければ簡易変換。"""

    def __init__(self, fallback_converter: Callable[[str], str] | None = None) -> None:
        self.fallback_converter = fallback_converter or self._simple_converter

    def to_html(self, markdown: str) -> str:
        if md_lib:
            return md_lib.markdown(markdown)
        return self.fallback_converter(markdown)

    @staticmethod
    def _simple_converter(text: str) -> str:
        escaped = html.escape(text)
        paragraphs = escaped.split("\n\n")
        return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())

