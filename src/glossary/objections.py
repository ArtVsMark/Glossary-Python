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

Шапка файла — общая для всех публикуемых контрактов, включая отметку времени;
почему она там есть, написано в :mod:`glossary.contracts`. Рядом с ней стоит
``snapshot.digest`` — отпечаток самих данных: отметка отвечает на «свежий ли
файл», отпечаток на «о каком снимке речь». Вопроса два, и ответов тоже два.

Список идентификаторов в JSON **не усекается**: усечённый контракт хуже
отсутствующего, потому что выглядит полным.

У находки есть **область** (``scope``). Не всякое замечание относится к
карточке: «раздел из одной карточки» — про раздел, «в Python есть, в глоссарии
нет» — вообще про отсутствующую карточку. Потребитель, который строит задачи
по ``cards``, такие находки молча терял бы, а пустой список выглядит как
«замечаний нет». Поэтому область названа явно, а предмет находки, если это не
карточка, лежит в ``details``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from glossary.contracts import PRODUCER, envelope
from glossary.loader import digest
from glossary.validation import Severity, validate

if TYPE_CHECKING:
    from glossary.models import Glossary
    from glossary.validation import Issue

__all__ = ["SCHEMA_OF", "as_json", "as_markdown", "collect"]

SCHEMA_OF: Final = "замечания витрины к содержанию глоссария"
"""Чего именно эта версия.

В экосистеме соседствуют четыре разных ``schema`` — выгрузка правил каталога,
ответ потребителя, сводка, факты. Витрина на этом уже обжигалась: держала в
своём ответе чужой номер, файл при этом оставался валидным, а гейт зелёным
(правило каталога 164). Номер, который не говорит, чего он, — не номер.
"""

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

    findings: list[dict[str, Any]] = []
    for rule, issues in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cards = list(dict.fromkeys(i.entry_id for i in issues if i.entry_id))
        finding: dict[str, Any] = {
            "rule": rule,
            "severity": issues[0].severity.value,
            "scope": "card" if cards else "glossary",
            "message": issues[0].message,
            "count": len(issues),
            "cards": cards,
        }
        # Предмет находки уровня глоссария — не карточка, и в cards его не
        # положить. Без details он исчез бы вместе с самой находкой.
        if not cards:
            finding["details"] = list(dict.fromkeys(i.message for i in issues))
        findings.append(finding)

    affected = {i.entry_id for i in report.issues if i.entry_id}
    return {
        **envelope(SCHEMA_OF),
        "snapshot": {
            "cards": len(glossary),
            "schema_version": glossary.schema_version,
            "digest": digest(glossary),
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
        lines += [heading, ""]

        # Находка не о карточке: предмет назван в details, и повторять его
        # заголовком-примером незачем — он там первым же пунктом.
        details: list[str] = finding.get("details", [])
        if details:
            shown_details = details if limit <= 0 else details[:limit]
            lines += [f"- {text}" for text in shown_details]
            if len(details) > len(shown_details):
                hidden = len(details) - len(shown_details)
                lines += ["", f"…и ещё {hidden}. Полный список: `--limit 0`."]
            lines += [""]
            continue

        lines += [finding["message"], ""]
        if not cards:
            continue
        shown = cards if limit <= 0 else cards[:limit]
        lines += [f"- `{card}`" for card in shown]
        if len(cards) > len(shown):
            hidden = len(cards) - len(shown)
            lines += ["", f"…и ещё {hidden}. Полный список: `--limit 0`."]
        lines += [""]

    return "\n".join(lines).rstrip() + "\n"
