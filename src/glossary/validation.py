"""Правила качества глоссария.

Валидатор построен как реестр независимых правил: каждое правило получает
глоссарий целиком и возвращает найденные проблемы. Добавление новой проверки —
это одна функция и одна строка в :data:`RULES`, без изменения остального кода.

Разделение на ``ERROR`` и ``WARNING`` намеренное: ошибки ломают сборку в CI,
предупреждения формируют бэклог по качеству данных и не блокируют работу.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from glossary.models import COLOR_GROUPS, Entry, Glossary

__all__ = [
    "RULES",
    "Issue",
    "Rule",
    "Severity",
    "ValidationConfig",
    "ValidationReport",
    "validate",
]

# Идентификатор используется как якорь URL и как значение атрибута id в
# разметке, поэтому ограничение ровно одно: в нём не должно быть символов,
# ломающих фрагмент URL или CSS-селектор. Алфавит намеренно свободный —
# в глоссарии соседствуют латинские слаги API и кириллические слаги понятий.
ID_FORBIDDEN: Final = re.compile(r"""[\s#/?&=%"'<>]""")
VERSION_PATTERN: Final = re.compile(r"^3\.\d+\+?$")
DOCS_PREFIX: Final = "https://docs.python.org/3/"
DUPLICATE_THRESHOLD: Final = 2
"""Начиная со скольких вхождений имя считается дублирующимся."""
GENERIC_DOCS: Final = frozenset({DOCS_PREFIX, "https://docs.python.org/3"})
_REQUIRED_TEXT_FIELDS: Final = (
    "id",
    "name",
    "group",
    "subcat",
    "cg",
    "description",
    "syntax",
    "examples",
    "docs",
)


class Severity(StrEnum):
    """Уровень серьёзности найденной проблемы."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True, order=True)
class Issue:
    """Одна проблема, найденная правилом."""

    severity: Severity
    rule: str
    message: str
    entry_id: str | None = None

    def format(self) -> str:
        """Однострочное представление для терминала и логов CI."""
        location = self.entry_id or "<глоссарий>"
        return f"{self.severity.value:>7} [{self.rule}] {location}: {self.message}"


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Пороговые значения правил.

    Вынесены в конфигурацию, чтобы ужесточать требования постепенно, не
    переписывая правила: сначала предупреждение, затем — ошибка.
    """

    min_description: int = 60
    max_description: int = 400
    min_example_lines: int = 2
    min_group_size: int = 2


Rule = Callable[[Glossary, ValidationConfig], Iterator[Issue]]
"""Правило: чистая функция от глоссария и конфигурации к списку проблем."""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Результат проверки глоссария."""

    issues: tuple[Issue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[Issue, ...]:
        """Проблемы уровня ``ERROR``."""
        return tuple(i for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Issue, ...]:
        """Проблемы уровня ``WARNING``."""
        return tuple(i for i in self.issues if i.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        """``True``, если ошибок нет (предупреждения допустимы)."""
        return not self.errors

    def by_rule(self) -> Counter[str]:
        """Счётчик проблем по правилам — удобная сводка для отчёта."""
        return Counter(i.rule for i in self.issues)


# --------------------------------------------------------------------------- #
# Правила
# --------------------------------------------------------------------------- #


def rule_required_fields(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Все текстовые поля карточки заполнены."""
    for entry in g.entries:
        for name in _REQUIRED_TEXT_FIELDS:
            value = getattr(entry, name)
            if not isinstance(value, str) or not value.strip():
                yield Issue(
                    Severity.ERROR,
                    "required-fields",
                    f"поле {name!r} пустое или не является строкой",
                    entry.id or None,
                )


def rule_id_format(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Идентификатор пригоден для использования в якоре URL и в разметке."""
    for entry in g.entries:
        if not entry.id:
            continue
        found = sorted({m.group() for m in ID_FORBIDDEN.finditer(entry.id)})
        if found:
            listed = ", ".join(repr(c) for c in found)
            yield Issue(
                Severity.ERROR,
                "id-format",
                f"идентификатор содержит недопустимые для якоря символы: {listed}",
                entry.id,
            )


def rule_unique_id(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Идентификаторы уникальны — иначе ломается навигация по якорям."""
    for entry_id, count in Counter(e.id for e in g.entries).items():
        if count > 1:
            yield Issue(
                Severity.ERROR,
                "unique-id",
                f"идентификатор встречается {count} раз",
                entry_id,
            )


def rule_color_group(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Цветовая группа входит в поддерживаемый витриной набор."""
    for entry in g.entries:
        if entry.cg not in COLOR_GROUPS:
            yield Issue(
                Severity.ERROR,
                "color-group",
                f"неизвестная цветовая группа {entry.cg!r}; "
                f"допустимы: {', '.join(sorted(COLOR_GROUPS))}",
                entry.id,
            )


def rule_docs_url(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Ссылка ведёт на официальную документацию и указывает на конкретный раздел."""
    for entry in g.entries:
        if not entry.docs.startswith(DOCS_PREFIX):
            yield Issue(
                Severity.ERROR,
                "docs-url",
                f"ссылка должна начинаться с {DOCS_PREFIX}, получено {entry.docs!r}",
                entry.id,
            )
        elif entry.docs.rstrip("/") in {u.rstrip("/") for u in GENERIC_DOCS}:
            yield Issue(
                Severity.WARNING,
                "docs-url",
                "ссылка ведёт на корень документации — нужен конкретный раздел или якорь",
                entry.id,
            )


def rule_description_length(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Описание достаточно содержательно и при этом не превращается в статью."""
    for entry in g.entries:
        length = len(entry.description)
        if 0 < length < cfg.min_description:
            yield Issue(
                Severity.ERROR,
                "description-length",
                f"описание короче {cfg.min_description} символов ({length})",
                entry.id,
            )
        elif length > cfg.max_description:
            yield Issue(
                Severity.WARNING,
                "description-length",
                f"описание длиннее {cfg.max_description} символов ({length}) — "
                "стоит разбить на несколько карточек",
                entry.id,
            )


def rule_version_format(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Маркер версии записан канонически: ``3.N+`` либо ``null``."""
    for entry in g.entries:
        if entry.version is None:
            continue
        if not VERSION_PATTERN.match(entry.version):
            yield Issue(
                Severity.ERROR,
                "version-format",
                f"маркер версии {entry.version!r} не соответствует "
                f"{VERSION_PATTERN.pattern}",
                entry.id,
            )
        elif not entry.version.endswith("+"):
            yield Issue(
                Severity.WARNING,
                "version-format",
                f"маркер версии {entry.version!r} записан без '+': "
                f"канонический вид — {entry.version}+",
                entry.id,
            )


def rule_examples_depth(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """В карточке есть хотя бы несколько строк примеров."""
    for entry in g.entries:
        lines = [line for line in entry.example_lines if line.strip()]
        if lines and len(lines) < cfg.min_example_lines:
            yield Issue(
                Severity.WARNING,
                "examples-depth",
                f"всего {len(lines)} строк(и) примеров, ожидается "
                f"минимум {cfg.min_example_lines}",
                entry.id,
            )


def rule_duplicate_name(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Одинаковые имена в разных разделах — кандидаты на слияние."""
    by_name: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in g.entries:
        by_name[entry.name].append(entry)
    for name, group in by_name.items():
        if len(group) < DUPLICATE_THRESHOLD:
            continue
        where = ", ".join(f"{e.id} ({e.group})" for e in group)
        yield Issue(
            Severity.WARNING,
            "duplicate-name",
            f"имя {name!r} встречается {len(group)} раза: {where}",
        )


def rule_group_size(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Слишком маленький раздел — признак неполного покрытия темы."""
    for group, count in Counter(e.group for e in g.entries).items():
        if count < cfg.min_group_size:
            yield Issue(
                Severity.WARNING,
                "group-size",
                f"раздел {group!r} содержит {count} карточк(и) — "
                "тема покрыта не полностью",
            )


RULES: Final[tuple[Rule, ...]] = (
    rule_required_fields,
    rule_id_format,
    rule_unique_id,
    rule_color_group,
    rule_docs_url,
    rule_description_length,
    rule_version_format,
    rule_examples_depth,
    rule_duplicate_name,
    rule_group_size,
)
"""Реестр активных правил. Порядок определяет порядок вывода в отчёте."""


def validate(
    glossary: Glossary,
    *,
    config: ValidationConfig | None = None,
    rules: Sequence[Rule] | None = None,
) -> ValidationReport:
    """Прогнать глоссарий через набор правил и собрать отчёт.

    Args:
        glossary: проверяемый глоссарий.
        config: пороговые значения; по умолчанию — :class:`ValidationConfig`.
        rules: набор правил; по умолчанию — :data:`RULES`.
    """
    cfg = config or ValidationConfig()
    active: Iterable[Rule] = rules if rules is not None else RULES
    issues: list[Issue] = []
    for rule in active:
        issues.extend(rule(glossary, cfg))
    return ValidationReport(issues=tuple(issues))
