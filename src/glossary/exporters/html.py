"""Сборка HTML-витрины из шаблона и данных.

Шаблон — это исходная одностраничная витрина, в которой блок данных заменён
плейсхолдером. Такой подход намеренно проще шаблонизатора: у проекта ровно одна
точка подстановки, а разметка остаётся обычным HTML, который можно открыть в
браузере и править в любом редакторе.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import TYPE_CHECKING, Final

from glossary.errors import ExportError

if TYPE_CHECKING:
    from glossary.models import Glossary

__all__ = ["PLACEHOLDER", "HtmlExporter", "load_template"]

PLACEHOLDER: Final = "{{GLOSSARY_DATA}}"
TEMPLATE_NAME: Final = "showcase.html"
_PACKAGE: Final = "glossary.templates"


def load_template() -> str:
    """Прочитать шаблон витрины, поставляемый вместе с пакетом."""
    try:
        return (
            resources.files(_PACKAGE).joinpath(TEMPLATE_NAME).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise ExportError(f"Шаблон {TEMPLATE_NAME} не найден в пакете") from exc


class HtmlExporter:
    """Подставляет данные глоссария в одностраничную витрину."""

    name = "html"
    suffix = ".html"

    def __init__(self, template: str | None = None) -> None:
        """Принять готовый шаблон или загрузить поставляемый с пакетом."""
        self._template = template if template is not None else load_template()
        if PLACEHOLDER not in self._template:
            raise ExportError(
                f"В шаблоне нет плейсхолдера {PLACEHOLDER} — подставлять данные некуда"
            )

    def render(self, glossary: Glossary) -> str:
        """Собрать готовую страницу.

        Данные сериализуются компактно и одной строкой: витрина читает их через
        ``JSON.parse``, а компактный вид сокращает размер страницы примерно на
        пятую часть по сравнению с форматированным JSON.
        """
        payload = json.dumps(
            [entry.to_dict() for entry in glossary.entries],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # ``</script>`` внутри строкового литерала закрыл бы блок данных раньше
        # времени; экранирование по стандартной для встроенного JSON схеме.
        payload = payload.replace("</", "<\\/")
        return self._template.replace(PLACEHOLDER, payload)
