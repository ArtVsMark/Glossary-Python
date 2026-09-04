"""Экспорт в Markdown — для чтения на GitHub и переноса в базы знаний."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glossary.models import Entry, Glossary

__all__ = ["MarkdownExporter"]

_ANCHOR_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)
_ANCHOR_SPACES = re.compile(r"\s+")


def _anchor(text: str) -> str:
    """Сформировать якорь заголовка по правилам GitHub Flavored Markdown."""
    slug = _ANCHOR_STRIP.sub("", text.lower())
    return _ANCHOR_SPACES.sub("-", slug.strip())


class MarkdownExporter:
    """Один документ: оглавление по разделам, затем карточки внутри разделов."""

    name = "markdown"
    suffix = ".md"

    def __init__(self, *, title: str = "Глоссарий Python") -> None:
        """Задать заголовок первого уровня в собираемом документе."""
        self._title = title

    def render(self, glossary: Glossary) -> str:
        """Собрать документ целиком."""
        return "\n".join(self._lines(glossary)) + "\n"

    def _lines(self, glossary: Glossary) -> Iterator[str]:
        stats = glossary.stats()
        yield f"# {self._title}"
        yield ""
        yield f"Карточек: **{stats.total}** · разделов: **{len(stats.groups)}**"
        yield ""
        yield "## Содержание"
        yield ""
        for group in glossary.groups:
            count = stats.groups[group]
            yield f"- [{group}](#{_anchor(group)}) — {count}"
        yield ""
        for group in glossary.groups:
            yield f"## {group}"
            yield ""
            for entry in glossary.in_group(group):
                yield from self._entry_lines(entry)

    def _entry_lines(self, entry: Entry) -> Iterator[str]:
        version = f" `{entry.version}`" if entry.version else ""
        yield f"### {entry.name}{version}"
        yield ""
        yield f"*{entry.subcat}*"
        yield ""
        yield entry.description
        yield ""
        yield "```python"
        yield entry.syntax
        yield "```"
        yield ""
        if entry.examples.strip():
            yield "<details><summary>Примеры</summary>"
            yield ""
            yield "```python"
            yield entry.examples.rstrip()
            yield "```"
            yield ""
            yield "</details>"
            yield ""
        yield f"[Документация]({entry.docs})"
        yield ""
