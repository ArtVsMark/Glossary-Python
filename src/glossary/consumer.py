"""Предложения потребителя к содержанию и ответ на них вердиктами (#250).

Stepik-Python-Grader публикует ``proposals.json`` — чего ему не хватает в
глоссарии: карточки синтаксиса, модулей, встроенных имён, соглашения об id. У
каждого предложения стабильный ``slug``, и по нему потребитель ждёт ответа.
Канал зеркальный тому, что связывает нас с каталогом правил: там предлагаем мы,
здесь — нам.

Ответ складывается из двух источников, и порядок важен:

1. **Исполнено** — видно по данным, человек не нужен. Карточка модуля
   появилась, встроенное имя есть в заголовке или синонимах, id переименованы.
   Такое предложение получает ``done`` даже без записи решения: иначе вердикт
   «принято» висел бы после того, как работа сделана.
2. **Решение** из ``data/consumer_verdicts.json``: ``accepted`` (с задачей),
   ``rejected`` (с причиной). Ключ — ``slug`` или образец ``вид:*``; точный
   ключ сильнее образца.

Предложение без решения и без исполнения — ``pending``. Это не молчание, а
очередь: отчёт называет такие slug поимённо.

Сеть модуль не трогает: файл предложений скачивает шаг публикации по адресу из
поля ``source`` файла решений, сюда он приходит путём. Адрес — контракт на
расположение, объявленный потребителем (Stepik-Python-Grader#1624), и живёт в
данных рядом с ответами, а не в коде: проба ответа по правилу 190 сторожит, чтобы
других чтений чужих публикуемых файлов в коде не появилось. Так тесты не
зависят от чужого репозитория, а отсутствие файла остаётся отдельным исходом
шага, а не исключением в коде.
"""

import fnmatch
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from glossary.completeness import known_names
from glossary.contracts import envelope
from glossary.loader import digest

SYNTAX_MARKER: Final = "syntax:"
"""Префикс ключевого слова, которым карточка конструкции называет признак потребителя."""

if TYPE_CHECKING:
    from pathlib import Path

    from glossary.models import Glossary

__all__ = [
    "DECISIONS_FILE",
    "SCHEMA_OF",
    "VERDICTS",
    "Proposal",
    "collect",
    "load_decisions",
    "read_proposals",
    "verdict_of",
]

PRODUCER: Final = "ArtVsMark/Stepik-Python-Grader"
"""Кто имеет право присылать предложения — шапка чужого файла сверяется с ним."""

SCHEMA_MAJOR: Final = "1"
"""Главный номер формата предложений, который мы умеем читать."""

DECISIONS_FILE: Final = "consumer_verdicts.json"
"""Решения по предложениям — рядом с карточками: ``data/consumer_verdicts.json``."""

VERDICTS: Final = ("done", "accepted", "rejected", "pending")
"""Ответы: исполнено, принято в работу, отклонено с причиной, ещё не решено."""

SCHEMA_OF: Final = "вердикты глоссария по предложениям потребителя"


class ProposalsError(ValueError):
    """Файл предложений не того формата: читать его как ответ нельзя."""


@dataclass(frozen=True, slots=True)
class Proposal:
    """Одно предложение потребителя."""

    slug: str
    kind: str
    subject: str
    suggested: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


def read_proposals(payload: dict[str, Any]) -> tuple[dict[str, Any], list[Proposal]]:
    """Сверить шапку и разобрать предложения.

    Args:
        payload: Разобранный ``proposals.json``.

    Returns:
        Пара «что потребитель смотрел (``examined``)», «предложения».

    Raises:
        ProposalsError: чужой издатель или формат, который мы не умеем читать.
    """
    if payload.get("producer") != PRODUCER:
        raise ProposalsError(f"издатель {payload.get('producer')!r}, ждали {PRODUCER!r}")
    schema = str(payload.get("schema", ""))
    if schema.split(".", 1)[0] != SCHEMA_MAJOR:
        raise ProposalsError(f"формат {schema!r}, читаем {SCHEMA_MAJOR}.x")
    items = payload.get("proposals")
    if not isinstance(items, list):
        raise ProposalsError("нет списка proposals")
    proposals = [
        Proposal(
            slug=str(item["slug"]),
            kind=str(item.get("kind", "")),
            subject=str(item.get("subject", "")),
            suggested=dict(item.get("suggested") or {}),
            evidence=dict(item.get("evidence") or {}),
        )
        for item in items
    ]
    return dict(payload.get("examined") or {}), proposals


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    """Решения владельца по ключу ``slug`` или образцу ``вид:*``.

    Ключи с подчёркиванием — пояснения файла, а не решения.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    decisions: dict[str, dict[str, Any]] = raw.get("decisions", {})
    return decisions


def _decision(slug: str, decisions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Решение для slug: точный ключ сильнее образца, длинный образец — короткого."""
    if slug in decisions:
        return decisions[slug]
    wildcards = (key for key in decisions if any(ch in key for ch in "*?["))
    patterns = sorted(
        (key for key in wildcards if fnmatch.fnmatchcase(slug, key)),
        key=len,
        reverse=True,
    )
    return decisions[patterns[0]] if patterns else None


def _done(proposal: Proposal, glossary: Glossary, names: frozenset[str]) -> bool:
    """Исполнено ли предложение — по одним данным, без решения человека."""
    ids = {entry.id for entry in glossary}
    if proposal.kind == "module-card":
        return proposal.subject in ids
    if proposal.kind == "builtin-card":
        return proposal.subject.lower() in names
    if proposal.kind == "syntax-card":
        # У конструкции нет имени, которое знал бы язык: признак ставит сама
        # карточка ключевым словом ``syntax:<subject>`` — по нему её ищет и
        # проверка совместимости потребителя.
        marker = f"{SYNTAX_MARKER}{proposal.subject}"
        return any(marker in entry.keywords for entry in glossary)
    if proposal.kind == "id-convention":
        cards = proposal.evidence.get("cards") or []
        return bool(cards) and all(
            card.get("name") in ids and card.get("id") not in ids for card in cards
        )
    return False


def verdict_of(
    proposal: Proposal,
    glossary: Glossary,
    decisions: dict[str, dict[str, Any]],
    names: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Ответ на одно предложение.

    Returns:
        ``slug``, ``verdict`` из :data:`VERDICTS` и то, чем он обоснован:
        ``issue`` у принятого, ``why`` у отклонённого.
    """
    known = names if names is not None else known_names(glossary)
    if _done(proposal, glossary, known):
        return {"slug": proposal.slug, "verdict": "done"}
    decision = _decision(proposal.slug, decisions)
    if decision is None:
        return {"slug": proposal.slug, "verdict": "pending"}
    answer = {"slug": proposal.slug, "verdict": decision["verdict"]}
    for key in ("issue", "why"):
        if key in decision:
            answer[key] = decision[key]
    return answer


def collect(
    payload: dict[str, Any],
    glossary: Glossary,
    decisions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Вердикты по всем предложениям — публикуемый контракт.

    Список не усекается: потребитель сверяет по нему каждый свой slug.
    """
    examined, proposals = read_proposals(payload)
    names = known_names(glossary)
    answers = [verdict_of(p, glossary, decisions, names) for p in proposals]
    totals = dict.fromkeys(VERDICTS, 0)
    for answer in answers:
        totals[answer["verdict"]] += 1
    return {
        **envelope(SCHEMA_OF),
        "answers_to": {
            "producer": payload.get("producer"),
            "generated_at": payload.get("generated_at"),
            "examined": examined,
        },
        "snapshot": {"cards": len(glossary), "digest": digest(glossary)},
        "totals": totals,
        "verdicts": answers,
    }
