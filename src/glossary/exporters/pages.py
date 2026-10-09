"""Страницы карточек для GitHub Pages: свой адрес у каждого термина (#227).

Витрина — одна страница, и карточка в ней открывается якорем ``#id``. Фрагмент
адреса поисковик отбрасывает, поэтому отдельного термина для него нет: человек с
ошибкой в терминале находит в лучшем случае главную. Здесь у карточки появляется
свой адрес — по-русски ``<id>/`` и по-английски ``en/<id>/`` рядом с витриной, —
а ``sitemap.xml`` перечисляет их все. Решение и отвергнутые варианты — в
``docs/dev/architecture.md``, разделе о страницах карточек.

ПОЧЕМУ НЕ СТРОКА В ``_FACTORIES``. Экспортёр формата возвращает одну строку, и
это его контракт: файл или stdout. Здесь на выходе каталог из тысяч файлов,
поэтому модуль отдаёт словарь «путь → текст», а пишет его на диск команда
``glossary pages``. Тестируется он так же, как экспортёры, — без файловой системы.

Слаг — сам ``id``: адрес страницы совпадает с якорем витрины, и второго
идентификатора у карточки нет. Кириллица уходит в адрес percent-encoding.
``id``, который не годится в имя каталога, — отказ сборки с названным id, а не
молча пропущенная страница.

``lastmod`` в ``sitemap.xml`` не пишется: дата коммита у карточки — это дата
файла группы, общая для сотен карточек, а неточный ``lastmod`` поисковик
перестаёт читать вовсе.
"""

import html
import json
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, urlencode

from glossary import taxonomy
from glossary.contracts import PAGES_URL, REPOSITORY_URL
from glossary.errors import ExportError
from glossary.models import LANGUAGES

if TYPE_CHECKING:
    from glossary.models import Entry, Glossary, Text

__all__ = [
    "ENGLISH_DIR",
    "SITEMAP",
    "STYLESHEET",
    "page_path",
    "page_url",
    "render_page",
    "render_pages",
    "render_sitemap",
    "slug_problem",
]

ENGLISH_DIR: Final = "en"
"""Каталог английских страниц. Русские лежат в корне — язык витрины по умолчанию."""
STYLESHEET: Final = PurePosixPath("card.css")
"""Общие стили всех страниц: один файл вместо копии в каждой из тысяч страниц."""
SITEMAP: Final = PurePosixPath("sitemap.xml")

RESERVED: Final[frozenset[str]] = frozenset(
    {ENGLISH_DIR, str(STYLESHEET), str(SITEMAP), "index.html", "glossary.json"}
)
"""Имена, которые уже заняты в корне публикации: каталог карточки их бы затёр."""

SITE_NAME: Final = "Python Glossary"
REPORT_FORM: Final = "content_fix.yml"
"""Форма замечания к карточке — та же, что у кнопки в витрине (#233)."""

LABELS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "open": "Открыть в полном глоссарии",
        "syntax": "Синтаксис",
        "examples": "Примеры",
        "example": "Пример",
        "see_also": "См. также",
        "errors": "Частые ошибки",
        "report": "Сообщить о неточности",
        "since_all": "все Python 3",
        "deprecated": "устарело в",
        "removed": "до",
        "other": "English",
        "term": "понятие",
        "function": "функция",
        "exception": "исключение",
        "construct": "конструкция",
    },
    "en": {
        "open": "Open in the full glossary",
        "syntax": "Syntax",
        "examples": "Examples",
        "example": "Example",
        "see_also": "See also",
        "errors": "Common errors",
        "report": "Report an inaccuracy",
        "since_all": "all Python 3",
        "deprecated": "deprecated in",
        "removed": "until",
        "other": "Русский",
        "term": "term",
        "function": "function",
        "exception": "exception",
        "construct": "construct",
    },
}
"""Подписи страницы. Те же слова, что у карточки в витрине."""


def slug_problem(entry_id: str) -> str | None:
    """Почему ``id`` не годится в имя каталога страницы.

    Args:
        entry_id: Идентификатор карточки.

    Returns:
        Причина словами либо ``None``, если ``id`` годится.
    """
    if not entry_id.strip():
        return "пустой id"
    if entry_id.startswith("."):
        return "начинается с точки — каталог стал бы скрытым и мог не войти в артефакт"
    if "/" in entry_id or "\\" in entry_id:
        return "содержит разделитель пути"
    if entry_id in RESERVED:
        return "совпадает с именем, занятым в корне публикации"
    return None


def page_path(entry_id: str, lang: str) -> PurePosixPath:
    """Путь страницы карточки внутри каталога публикации."""
    page = PurePosixPath(entry_id) / "index.html"
    return PurePosixPath(ENGLISH_DIR) / page if lang == "en" else page


def page_url(entry_id: str, lang: str) -> str:
    """Опубликованный адрес страницы карточки."""
    prefix = f"{ENGLISH_DIR}/" if lang == "en" else ""
    return f"{PAGES_URL}{prefix}{quote(entry_id, safe='')}/"


def _text(text: Text, lang: str) -> str:
    """Текст на языке страницы; непереведённое — по-русски, как в витрине."""
    return text.get(lang) or text.ru


def _versions(entry: Entry, labels: dict[str, str]) -> list[str]:
    """Значки жизненного цикла — те же, что у карточки в витрине (#122)."""
    badges: list[str] = []
    if entry.added:
        since = (
            labels["since_all"]
            if entry.added.startswith("<")
            else f"Python {entry.added}+"
        )
        badges.append(since)
    if entry.removed:
        badges.append(f"{labels['removed']} {entry.removed}")
    elif entry.deprecated:
        badges.append(f"{labels['deprecated']} {entry.deprecated}")
    return badges


def _links(glossary: Glossary, references: tuple[str, ...]) -> list[Entry]:
    """Карточки, на которые ведут ссылки; битая ссылка пропускается молча.

    Битая связь — находка валидатора, а не отказ сборки: страница без одной
    ссылки лучше, чем отсутствие всех страниц.
    """
    seen: set[str] = set()
    found: list[Entry] = []
    for reference in references:
        target = glossary.resolve(reference)
        if target is not None and target.id not in seen:
            seen.add(target.id)
            found.append(target)
    return found


def _report_url(entry: Entry, title: str) -> str:
    """Форма замечания к карточке с уже заполненным id — как в витрине."""
    query = urlencode(
        {
            "template": REPORT_FORM,
            "title": f"[Контент / Content]: {title}",
            "entry_id": entry.id,
        }
    )
    return f"{REPOSITORY_URL}/issues/new?{query}"


def _structured(entry: Entry, lang: str, title: str, summary: str) -> str:
    """JSON-LD ``DefinedTerm``: термин и набор, в который он входит."""
    data = {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "name": title,
        "description": summary,
        "termCode": entry.id,
        "url": page_url(entry.id, lang),
        "inLanguage": lang,
        "inDefinedTermSet": {
            "@type": "DefinedTermSet",
            "name": SITE_NAME,
            "url": PAGES_URL,
        },
    }
    # ``</script>`` в тексте закрыл бы блок раньше времени — как и у витрины.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def render_page(glossary: Glossary, entry: Entry, lang: str) -> str:
    """Собрать страницу одной карточки на одном языке.

    Args:
        glossary: Сборка — по ней разрешаются ссылки «см. также».
        entry: Карточка.
        lang: ``ru`` или ``en``.

    Returns:
        Готовый HTML.
    """
    esc = html.escape
    labels = LABELS[lang]
    other = "en" if lang == "ru" else "ru"
    root = "../../" if lang == "en" else "../"
    title = _text(entry.title, lang) or entry.id
    summary = _text(entry.summary, lang)
    section = taxonomy.section_label(entry.section, lang)
    kind = labels.get(entry.kind, entry.kind)
    platforms = [] if "AllOS" in entry.platforms else list(entry.platforms)
    badges = [*_versions(entry, labels), *([" · ".join(platforms)] if platforms else [])]
    badges = [badge for badge in (*badges, section, kind) if badge]

    parts: list[str] = []
    subcat = _text(entry.subcat, lang)
    if subcat:
        parts.append(f'<p class="subcat">{esc(subcat)}</p>')
    parts.append(f'<p class="summary">{esc(summary)}</p>')
    if entry.syntax:
        parts.append(
            f'<h2>{labels["syntax"]}</h2>\n<pre class="syntax"><code>'
            f"{esc(entry.syntax)}</code></pre>"
        )
    body = _text(entry.body, lang)
    if body:
        parts.append(f'<p class="body">{esc(body)}</p>')
    if entry.examples:
        parts.append(f"<h2>{labels['examples']}</h2>")
        parts.extend(
            f'<pre class="example"><code>{esc(chr(10).join(block))}</code></pre>'
            for block in entry.examples
        )
    for heading, references in (
        (labels["see_also"], entry.related),
        (labels["errors"], entry.related_errors),
    ):
        targets = _links(glossary, references)
        if targets:
            items = "".join(
                f'<a href="../{quote(t.id, safe="")}/">'
                f"{esc(_text(t.title, lang) or t.id)}</a>"
                for t in targets
            )
            parts.append(f'<h2>{heading}</h2>\n<nav class="related">{items}</nav>')

    actions = [
        f'<a class="primary" href="{root}#{quote(entry.id, safe="")}">'
        f"{labels['open']}</a>"
    ]
    if entry.docs_url:
        actions.append(f'<a href="{esc(entry.docs_url)}">docs.python.org</a>')
    actions.append(f'<a href="{esc(_report_url(entry, title))}">{labels["report"]}</a>')

    own, ru_url, en_url = (
        page_url(entry.id, lang),
        page_url(entry.id, "ru"),
        page_url(entry.id, "en"),
    )
    other_href = (
        f"../../{quote(entry.id, safe='')}/"
        if lang == "en"
        else (f"../{ENGLISH_DIR}/{quote(entry.id, safe='')}/")
    )
    group = entry.color_group if entry.color_group else "op"
    switch = labels["other"]
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — {SITE_NAME}</title>
<meta name="description" content="{esc(summary)}">
<link rel="canonical" href="{esc(own)}">
<link rel="alternate" hreflang="ru" href="{esc(ru_url)}">
<link rel="alternate" hreflang="en" href="{esc(en_url)}">
<link rel="alternate" hreflang="x-default" href="{esc(ru_url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(summary)}">
<meta property="og:url" content="{esc(own)}">
<meta property="og:locale" content="{"en_US" if lang == "en" else "ru_RU"}">
<link rel="stylesheet" href="{root}{STYLESHEET}">
<script type="application/ld+json">{_structured(entry, lang, title, summary)}</script>
</head>
<body>
<header class="top">
<a class="brand" href="{root}">{SITE_NAME}</a>
<a class="lang" href="{other_href}" hreflang="{other}" lang="{other}">{switch}</a>
</header>
<main class="card" style="--cg:var(--c-{esc(group)})">
<p class="badges">{"".join(f"<span>{esc(b)}</span>" for b in badges)}</p>
<h1>{esc(title)}</h1>
{chr(10).join(parts)}
<p class="actions">{"".join(actions)}</p>
</main>
</body>
</html>
"""


def render_sitemap(glossary: Glossary) -> str:
    """``sitemap.xml``: витрина и обе страницы каждой карточки."""
    urls = [PAGES_URL] + [
        page_url(entry.id, lang) for entry in glossary.entries for lang in LANGUAGES
    ]
    rows = "\n".join(f"  <url><loc>{html.escape(url)}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{rows}\n</urlset>\n"
    )


STYLES: Final = """:root{
  --bg:#f4f2ec; --surface:#fff; --surface-2:#faf9f5; --border:#e6e2d8;
  --text:#161b26; --muted:#666e7d;
  --accent:#2f54eb; --accent-soft:#e9edfd; --on-accent:#fff;
  --code-bg:#f7f5ef; --code-border:#eae5d9;
  --shadow:0 1px 2px rgba(22,27,38,.05), 0 3px 12px rgba(22,27,38,.05);
  --c-builtin:#3b82f6; --c-str:#0d9f6e; --c-seq:#8b5cf6; --c-mapset:#6366f1;
  --c-oop:#ec4899; --c-exc:#ef4444; --c-module:#e0850b; --c-iter:#06b6d4;
  --c-op:#64748b; --c-typing:#9173f0;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1220; --surface:#151c2c; --surface-2:#1a2234; --border:#273148;
    --text:#e7ebf3; --muted:#95a1b6;
    --accent:#6b8cff; --accent-soft:#1b2646; --on-accent:#0d1220;
    --code-bg:#0f1626; --code-border:#273148;
    --shadow:0 1px 2px rgba(0,0,0,.32), 0 3px 14px rgba(0,0,0,.36);
    --c-builtin:#60a5fa; --c-str:#34d399; --c-seq:#a78bfa; --c-mapset:#818cf8;
    --c-oop:#f472b6; --c-exc:#f87171; --c-module:#fbbf24; --c-iter:#22d3ee;
    --c-op:#94a3b8; --c-typing:#b39cf7;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.6;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
code,pre{font-family:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace}
.top{max-width:820px;margin:0 auto;padding:18px 16px;display:flex;
  justify-content:space-between;align-items:center;gap:12px}
.brand{font-weight:700;color:var(--text);text-decoration:none}
.lang{color:var(--accent);text-decoration:none;font-size:14px}
.card{max-width:820px;margin:0 auto 40px;background:var(--surface);
  border:1px solid var(--border);border-top:4px solid var(--cg);border-radius:15px;
  box-shadow:var(--shadow);padding:22px 24px}
@media (max-width:600px){.card{margin:0 0 24px;border-radius:0;padding:18px 16px}}
h1{margin:8px 0 6px;font-size:26px;overflow-wrap:anywhere}
h2{margin:22px 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted)}
.badges{margin:0;display:flex;flex-wrap:wrap;gap:6px}
.badges span{font-size:12px;padding:2px 9px;border-radius:999px;
  background:var(--surface-2);border:1px solid var(--border);color:var(--muted)}
.subcat{margin:0;color:var(--muted);font-size:14px}
.summary{font-size:17px}
pre{background:var(--code-bg);border:1px solid var(--code-border);border-radius:10px;
  padding:12px 14px;overflow-x:auto;font-size:14px;line-height:1.5}
.related{display:flex;flex-wrap:wrap;gap:8px}
.related a,.actions a{font-size:14px;padding:6px 12px;border-radius:999px;
  background:var(--accent-soft);color:var(--accent);text-decoration:none}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:26px}
.actions a.primary{background:var(--accent);color:var(--on-accent)}
a:hover{text-decoration:underline}
"""
"""Стили страниц — токены витрины: цвет группы, светлая и тёмная тема."""


def render_pages(glossary: Glossary) -> dict[PurePosixPath, str]:
    """Собрать все страницы карточек, общие стили и ``sitemap.xml``.

    Args:
        glossary: Сборка.

    Returns:
        Путь внутри каталога публикации → содержимое файла.

    Raises:
        ExportError: глоссарий пуст; ``id`` не годится в имя каталога; два ``id``
            совпадают. Каждый отказ называет карточки поимённо.
    """
    if not glossary.entries:
        raise ExportError("Глоссарий пуст — страниц карточек не будет")
    problems = [
        f"{entry.id!r}: {problem}"
        for entry in glossary.entries
        if (problem := slug_problem(entry.id)) is not None
    ]
    if problems:
        raise ExportError("id не годится в адрес страницы: " + "; ".join(problems))

    files: dict[PurePosixPath, str] = {}
    for entry in glossary.entries:
        for lang in LANGUAGES:
            path = page_path(entry.id, lang)
            if path in files:
                raise ExportError(f"две карточки с id {entry.id!r} — страница одна")
            files[path] = render_page(glossary, entry, lang)
    files[STYLESHEET] = STYLES
    files[SITEMAP] = render_sitemap(glossary)
    return files
