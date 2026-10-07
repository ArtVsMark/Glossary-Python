"""Экспорт в Markdown — для чтения на GitHub и переноса в базы знаний."""

import re
from typing import TYPE_CHECKING

from glossary.models import ALL_OS

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

    def __init__(self, *, title: str = "Глоссарий Python", language: str = "ru") -> None:
        """Задать заголовок документа и язык текстов карточек."""
        self._title = title
        self._language = language

    def render(self, glossary: Glossary) -> str:
        """Собрать документ целиком."""
        return "\n".join(self._lines(glossary)) + "\n"

    def _lines(self, glossary: Glossary) -> Iterator[str]:
        stats = glossary.stats()
        yield f"# {self._title}"
        yield ""
        yield f"Карточек: **{stats.total}** · разделов: **{len(stats.sections)}**"
        yield ""
        yield "## Содержание"
        yield ""
        for section in glossary.sections:
            yield f"- [{section}](#{_anchor(section)}) — {stats.sections[section]}"
        yield ""
        for section in glossary.sections:
            yield f"## {section}"
            yield ""
            for entry in glossary.in_section(section):
                yield from self._entry_lines(entry)

    def _entry_lines(self, entry: Entry) -> Iterator[str]:
        version = f" `{entry.added}`" if entry.added else ""
        yield f"### {entry.title.get(self._language)}{version}"
        yield ""
        subcat = entry.subcat.get(self._language)
        platforms = "" if ALL_OS in entry.platforms else ", ".join(entry.platforms)
        subtitle = " · ".join(part for part in (entry.kind, subcat, platforms) if part)
        if subtitle:
            yield f"*{subtitle}*"
            yield ""
        yield entry.summary.get(self._language)
        yield ""
        if entry.syntax:
            yield "```python"
            yield entry.syntax
            yield "```"
            yield ""
        body = entry.body.get(self._language).strip()
        if body:
            yield body
            yield ""
        if entry.examples:
            yield "<details><summary>Примеры</summary>"
            yield ""
            for block in entry.examples:
                yield "```python"
                yield from block
                yield "```"
                yield ""
            yield "</details>"
            yield ""
        if entry.related:
            links = ", ".join(f"[{r}](#{_anchor(r)})" for r in entry.related)
            yield f"См. также: {links}"
            yield ""
        if entry.docs_url:
            yield f"[Документация]({entry.docs_url})"
            yield ""
