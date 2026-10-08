"""Сборка HTML-витрины из шаблона и данных.

Шаблон — это исходная одностраничная витрина, в которой блок данных заменён
плейсхолдером. Такой подход намеренно проще шаблонизатора: точек подстановки
две — данные и таблица фильтра, — а разметка остаётся обычным HTML, который
можно открыть в браузере и править в любом редакторе.
"""

import html
import json
from importlib import resources
from typing import TYPE_CHECKING, Final

from glossary import taxonomy
from glossary.contracts import PAGES_URL, REPOSITORY_URL
from glossary.errors import ExportError

if TYPE_CHECKING:
    from glossary.models import Glossary

__all__ = [
    "HEAD",
    "NAVIGATION",
    "PLACEHOLDER",
    "REPOSITORY",
    "HtmlExporter",
    "head",
    "load_template",
]

PLACEHOLDER: Final = "{{GLOSSARY_DATA}}"
NAVIGATION: Final = "{{NAVIGATION}}"
"""Таблица фильтра: семейства и подписи разделов (:mod:`glossary.taxonomy`).

Вторая точка подстановки, а не поле в данных: классификация — свойство
витрины, а не карточки, и в экспорт JSON она не едет. Шаблон без неё
собирается — проверочные шаблоны в тестах малы, — а что поставляемый шаблон
её содержит, держит ``tests/test_taxonomy.py``."""
HEAD: Final = "{{HEAD}}"
"""Метаданные страницы для поисковика и превью ссылки (#222).

Собираются кодом, а не пишутся в шаблоне: в них числа сборки, а число,
вписанное рукой, устаревает молча. Шаблон без этой точки собирается — как и без
таблицы фильтра."""
REPOSITORY: Final = "{{REPOSITORY}}"
"""Адрес репозитория: кнопка в шапке, ссылки обратной связи из карточек (#233).

Подставляется из :data:`glossary.contracts.REPOSITORY_URL`, а не пишется в
шаблоне строкой: адрес проекта назван в пакете один раз."""
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


_FEW: Final = range(2, 5)
"""Последняя цифра, при которой существительное в родительном единственном."""
_TEENS: Final = range(11, 15)
"""Две последние цифры, при которых правило последней цифры не действует."""


def _count(number: int, one: str, few: str, many: str) -> str:
    """Число с существительным в верной форме: 1 карточка, 2 карточки, 5 карточек."""
    tens, units = number % 100, number % 10
    if tens in _TEENS:
        word = many
    elif units == 1:
        word = one
    elif units in _FEW:
        word = few
    else:
        word = many
    return f"{number} {word}"


def head(glossary: Glossary) -> str:
    """Метаданные витрины: описание, превью ссылки, адрес и JSON-LD.

    Внешних запросов они не добавляют, поэтому скачанная копия работает офлайн
    как прежде; ``canonical`` в ней указывает на опубликованный адрес — так и
    задумано: копия не выдаёт себя за отдельный сайт.

    Args:
        glossary: Сборка, из которой берутся числа.

    Returns:
        Строки ``<meta>``, ``<link>`` и блок JSON-LD для ``<head>``.
    """
    cards = len(glossary.entries)
    sections = len(glossary.sections)
    ru = (
        "Двуязычный справочник стандартной библиотеки Python: "
        f"{_count(cards, 'карточка', 'карточки', 'карточек')} "
        f"в {_count(sections, 'разделе', 'разделах', 'разделах')} — сводка, разбор, "
        "синтаксис, исполняемые примеры, "
        "версия Python и ссылка на официальную документацию."
    )
    en = (
        f"A bilingual reference to the Python standard library: {cards} cards in "
        f"{sections} sections — summary, explanation, syntax, runnable examples, "
        "Python version and a link to the official documentation."
    )
    title = "Python Glossary"
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": title,
                "url": PAGES_URL,
                "inLanguage": ["ru", "en"],
            },
            {
                "@type": "DefinedTermSet",
                "name": title,
                "url": PAGES_URL,
                "description": [
                    {"@language": "ru", "@value": ru},
                    {"@language": "en", "@value": en},
                ],
                "inLanguage": ["ru", "en"],
                "numberOfItems": cards,
            },
        ],
    }
    # ``</script>`` в тексте закрыл бы блок раньше времени — как и у данных.
    ld = json.dumps(structured, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    attr = html.escape
    return "\n".join(
        (
            f'<meta name="description" content="{attr(ru)}">',
            f'<link rel="canonical" href="{attr(PAGES_URL)}">',
            '<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{title}">',
            f'<meta property="og:title" content="{title}">',
            f'<meta property="og:description" content="{attr(ru)}">',
            f'<meta property="og:url" content="{attr(PAGES_URL)}">',
            '<meta property="og:locale" content="ru_RU">',
            '<meta property="og:locale:alternate" content="en_US">',
            '<meta name="twitter:card" content="summary">',
            f'<script type="application/ld+json">{ld}</script>',
        )
    )


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
        return (
            self._template.replace(HEAD, head(glossary))
            .replace(REPOSITORY, REPOSITORY_URL)
            .replace(NAVIGATION, navigation)
            .replace(PLACEHOLDER, payload)
        )
