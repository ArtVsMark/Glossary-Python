"""Сборка HTML-витрины из шаблона и данных.

Шаблон — это исходная одностраничная витрина, в которой блок данных заменён
плейсхолдером. Такой подход намеренно проще шаблонизатора: точек подстановки
две — данные и таблица фильтра, — а разметка остаётся обычным HTML, который
можно открыть в браузере и править в любом редакторе.
"""

import json
from importlib import resources
from typing import TYPE_CHECKING, Final

from glossary import taxonomy
from glossary.errors import ExportError

if TYPE_CHECKING:
    from glossary.models import Glossary

__all__ = ["NAVIGATION", "PLACEHOLDER", "HtmlExporter", "load_template"]

PLACEHOLDER: Final = "{{GLOSSARY_DATA}}"
NAVIGATION: Final = "{{NAVIGATION}}"
"""Таблица фильтра: семейства и подписи разделов (:mod:`glossary.taxonomy`).

Вторая точка подстановки, а не поле в данных: классификация — свойство
витрины, а не карточки, и в экспорт JSON она не едет. Шаблон без неё
собирается — проверочные шаблоны в тестах малы, — а что поставляемый шаблон
её содержит, держит ``tests/test_taxonomy.py``."""
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

        Raises:
            ExportError: глоссарий пуст. Пустая витрина неотличима от исправной
                до открытия в браузере, поэтому собирается не она, а отказ.
        """
        if not glossary.entries:
            raise ExportError(
                "Глоссарий пуст — витрина не собирается. "
                "Пустая страница выглядит исправной и молча заменит рабочую."
            )
        payload = json.dumps(
            [entry.to_dict() for entry in glossary.entries],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # ``</script>`` внутри строкового литерала закрыл бы блок данных раньше
        # времени; экранирование по стандартной для встроенного JSON схеме.
        payload = payload.replace("</", "<\\/")
        navigation = json.dumps(
            taxonomy.table(list(glossary.sections)),
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("</", "<\\/")
        # Таблица подставляется первой: текст карточек не должен попасть под
        # вторую замену, если в нём встретится имя плейсхолдера.
        return self._template.replace(NAVIGATION, navigation).replace(
            PLACEHOLDER, payload
        )
