"""Замечания к содержанию — контракт с источником.

Карточки правятся не здесь: содержание ведётся в базе знаний
``ArtVsMark/Stepik-Python-Grader``, поток односторонний. Поэтому находка
валидатора бесполезна, пока она не превратилась в предъявимый список.

Замечания отдаются в двух видах, и оба — не украшение:

* **Markdown** — человеку, в issue источника как есть;
* **JSON** — машине. Он публикуется рядом с ``facts.json`` в ветку ``badges``:
  издатель считает, потребитель читает обычным HTTP, без клона и без токена
  (правило каталога 174). Ручной перенос списка из 434 идентификаторов не
  выживает ни одной итерации.

В JSON **нет отметки времени**. Она меняла бы файл при каждом прогоне, и ветка
``badges`` копила бы коммиты «ничего не изменилось»; публикующий прогон именно
на неизменность файла и смотрит, решая, коммитить ли. Дата же есть у самого
коммита — и там она честнее.

Список идентификаторов в JSON **не усекается**: усечённый контракт хуже
отсутствующего, потому что выглядит полным.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from glossary.validation import Severity, validate

if TYPE_CHECKING:
    from glossary.models import Glossary
    from glossary.validation import Issue

__all__ = ["PRODUCER", "SCHEMA", "SOURCE", "as_json", "as_markdown", "collect"]

SCHEMA: Final = 1
"""Версия формата ``objections.json``. Растёт при несовместимом изменении."""

PRODUCER: Final = "ArtVsMark/Glossary-Python"
SOURCE: Final = "ArtVsMark/Stepik-Python-Grader"

DEFAULT_LIMIT: Final = 25
"""Сколько идентификаторов перечислять в Markdown.

Список из шестисот не читают. Полный перечень достаётся ``--limit 0``, когда
его действительно собираются разбирать целиком; в JSON он всегда полный.
"""


def collect(glossary: Glossary) -> dict[str, Any]:
    """Собрать замечания в машиночитаемый вид.

    Карточка может дать несколько находок по одному правилу — например, по
    находке на язык. В ``cards`` каждая встречается один раз: список адресован
    тому, кто пойдёт их править, а не считать находки.
    """
    report = validate(glossary)
    grouped: dict[str, list[Issue]] = {}
    for issue in report.issues:
        grouped.setdefault(issue.rule, []).append(issue)

    findings = [
        {
            "rule": rule,
            "severity": issues[0].severity.value,
            "message": issues[0].message,
            "count": len(issues),
            "cards": list(dict.fromkeys(i.entry_id for i in issues if i.entry_id)),
        }
        for rule, issues in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    affected = {i.entry_id for i in report.issues if i.entry_id}
    return {
        "schema": SCHEMA,
        "producer": PRODUCER,
        "source": SOURCE,
        "snapshot": {
            "cards": len(glossary),
            "schema_version": glossary.schema_version,
        },
        "totals": {
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "cards_affected": len(affected),
        },
        "findings": findings,
    }


def as_json(glossary: Glossary) -> str:
    """Замечания как публикуемый контракт."""
    return json.dumps(collect(glossary), ensure_ascii=False, indent=2) + "\n"


def as_markdown(glossary: Glossary, *, limit: int = DEFAULT_LIMIT) -> str:
    """Замечания как письмо: кладётся в issue источника без правки."""
    data = collect(glossary)
    totals = data["totals"]
    snapshot = data["snapshot"]
    lines = [
        "# Замечания к содержанию глоссария",
        "",
        f"Проверено карточек: **{snapshot['cards']}**. "
        f"Ошибок: **{totals['errors']}**, предупреждений: **{totals['warnings']}**. "
        f"Затронуто карточек: **{totals['cards_affected']}**.",
        "",
        f"Отчёт собран `glossary objections` в витрине "
        f"([{PRODUCER}](https://github.com/{PRODUCER})). "
        "Витрина карточки не правит — правки идут в источнике. "
        "Тот же список машиночитаемо — `objections.json` в ветке `badges`.",
        "",
    ]
    if not data["findings"]:
        return "\n".join([*lines, "Замечаний нет."]) + "\n"

    for finding in data["findings"]:
        severity = "ошибка" if finding["severity"] == Severity.ERROR else "предупреждение"
        heading = f"## `{finding['rule']}` — {finding['count']} ({severity})"
        cards: list[str] = finding["cards"]
        if cards and len(cards) != finding["count"]:
            heading += f", карточек: {len(cards)}"
        lines += [heading, "", finding["message"], ""]
        if not cards:
            continue
        shown = cards if limit <= 0 else cards[:limit]
        lines += [f"- `{card}`" for card in shown]
        if len(cards) > len(shown):
            hidden = len(cards) - len(shown)
            lines += ["", f"…и ещё {hidden}. Полный список: `--limit 0`."]
        lines += [""]

    return "\n".join(lines).rstrip() + "\n"
