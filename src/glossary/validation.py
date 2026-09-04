"""Правила качества глоссария.

Валидатор построен как реестр независимых правил: каждое правило получает
глоссарий целиком и возвращает найденные проблемы. Добавление новой проверки —
это одна функция и одна строка в :data:`RULES`, без изменения остального кода.

Разделение на ``ERROR`` и ``WARNING`` намеренное: ошибки ломают сборку в CI,
предупреждения формируют бэклог по качеству данных и не блокируют работу.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from glossary.models import COLOR_GROUPS, KINDS, LANGUAGES, Entry, Glossary

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
VERSION_PATTERN: Final = re.compile(r"^\d+\.\d+$")
DOCS_PREFIX: Final = "https://docs.python.org/3/"
DUPLICATE_THRESHOLD: Final = 2
"""Начиная со скольких вхождений имя считается дублирующимся."""
GENERIC_DOCS: Final = frozenset({DOCS_PREFIX, "https://docs.python.org/3"})
_REQUIRED_TEXT_FIELDS: Final = (
    "id",
    "title",
    "kind",
    "status",
    "section",
    "subcat",
    "syntax",
    "docs_url",
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

    min_summary: int = 30
    max_summary: int = 200
    min_body: int = 60
    min_examples: int = 1
    min_section_size: int = 2


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


def rule_non_empty(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Пустой снимок — отсутствие проверки, а не её успех.

    У гейта два разных состояния успеха, и их легко перепутать: «проверил, и
    нарушений нет» и «проверять было нечего». Второе не успех.
    """
    if not g.entries:
        yield Issue(
            Severity.ERROR,
            "non-empty",
            "снимок не содержит ни одной карточки — проверять нечего, "
            "это ошибка входа, а не успешная проверка",
        )


def rule_required_fields(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Обязательные текстовые поля карточки заполнены."""
    for entry in g.entries:
        for name in _REQUIRED_TEXT_FIELDS:
            value = getattr(entry, name)
            if not isinstance(value, str) or not value.strip():
                yield Issue(
                    Severity.ERROR,
                    "required-fields",
                    f"поле {name!r} пустое",
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


def rule_kind(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Вид карточки известен: от него зависит подача и фильтры."""
    for entry in g.entries:
        if entry.kind and entry.kind not in KINDS:
            yield Issue(
                Severity.ERROR,
                "kind",
                f"неизвестный вид {entry.kind!r}; допустимы: {', '.join(sorted(KINDS))}",
                entry.id,
            )


def rule_color_group(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Цветовая группа названа и известна витрине.

    Значение приходит из имени файла-источника. Незнакомая группа означает, что
    в базе знаний появился новый файл, о котором витрина не знает: карточки
    получат цвет по умолчанию и сольются с чужой рубрикой. Это ошибка импорта,
    а не свойство карточки, поэтому уровень — ошибка.
    """
    for entry in g.entries:
        if entry.color_group not in COLOR_GROUPS:
            yield Issue(
                Severity.ERROR,
                "color-group",
                f"неизвестная цветовая группа {entry.color_group!r}; "
                f"допустимы: {', '.join(sorted(COLOR_GROUPS))}",
                entry.id,
            )


def rule_translated(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Обе языковые версии заполнены.

    Совпадение ключей — ещё не перевод: пустая половина даёт карточку, которая
    на одном из языков выглядит сломанной, а не отсутствующей.
    """
    for entry in g.entries:
        for language in LANGUAGES:
            if not entry.summary.get(language).strip():
                yield Issue(
                    Severity.ERROR,
                    "translated",
                    f"сводка не заполнена на языке {language!r}",
                    entry.id,
                )
            if not entry.body.get(language).strip():
                yield Issue(
                    Severity.WARNING,
                    "translated",
                    f"тело карточки не заполнено на языке {language!r}",
                    entry.id,
                )


def rule_docs_url(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Ссылка ведёт на официальную документацию и указывает на конкретный раздел."""
    for entry in g.entries:
        if not entry.docs_url.startswith(DOCS_PREFIX):
            yield Issue(
                Severity.ERROR,
                "docs-url",
                f"ссылка должна начинаться с {DOCS_PREFIX}, получено {entry.docs_url!r}",
                entry.id,
            )
        elif entry.docs_url.rstrip("/") in {u.rstrip("/") for u in GENERIC_DOCS}:
            yield Issue(
                Severity.WARNING,
                "docs-url",
                "ссылка ведёт на корень документации — нужен конкретный раздел",
                entry.id,
            )


def rule_summary_length(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Сводка коротка настолько, чтобы её прочли, и длинна настолько, чтобы поняли."""
    for entry in g.entries:
        length = len(entry.summary.ru)
        if 0 < length < cfg.min_summary:
            yield Issue(
                Severity.WARNING,
                "summary-length",
                f"сводка короче {cfg.min_summary} символов ({length})",
                entry.id,
            )
        elif length > cfg.max_summary:
            yield Issue(
                Severity.WARNING,
                "summary-length",
                f"сводка длиннее {cfg.max_summary} символов ({length}) — "
                "она попадает в список, где место ограничено",
                entry.id,
            )


def rule_body_length(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Тело карточки объясняет, а не повторяет сводку."""
    for entry in g.entries:
        length = len(entry.body.ru)
        if 0 < length < cfg.min_body:
            yield Issue(
                Severity.WARNING,
                "body-length",
                f"тело короче {cfg.min_body} символов ({length}) — "
                "оно не добавляет к сводке ничего",
                entry.id,
            )


def rule_version_format(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Маркер версии записан как ``N.N`` либо пуст."""
    for entry in g.entries:
        if entry.version and not VERSION_PATTERN.match(entry.version):
            yield Issue(
                Severity.ERROR,
                "version-format",
                f"маркер версии {entry.version!r} не соответствует "
                f"{VERSION_PATTERN.pattern}",
                entry.id,
            )


def rule_examples(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """У карточки есть хотя бы один пример."""
    for entry in g.entries:
        if len(entry.examples) < cfg.min_examples:
            yield Issue(
                Severity.WARNING,
                "examples",
                "примеров нет — по одной сводке конструкцию не применить",
                entry.id,
            )


def _from_the_future(version: str) -> bool:
    """Возможность объявлена новее, чем интерпретатор, на котором проверяем."""
    if not version:
        return False
    try:
        declared = tuple(int(part) for part in version.split("."))
    except ValueError:
        return False  # Форму маркера судит rule_version_format, не это правило.
    return declared > sys.version_info[: len(declared)]


def rule_example_compiles(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Пример карточки — синтаксически верный Python.

    Проверка та же, которой пользуется источник: ``compile`` по склеенным
    строкам примера. Раньше здесь стояла эвристика «блок открыт, а строки с
    отступом нет» — она ловила самый частый случай, но не всякий, и давала
    число, несравнимое с числом источника. Общий инвариант дороже своей мерки:
    возражение читается без перевода.

    Компилируется, а не исполняется: разбор кода безопасен, запуск чужого
    примера — нет.

    Карточка, объявившая версию новее работающего интерпретатора, пропускается.
    ``type X = int`` и ``def f[*Ts]()`` — синтаксис 3.12, и на 3.11 он не
    разберётся никогда. Требовать этого значило бы требовать невозможного, а
    находка была бы не о карточке, а о том, чем её проверяли.

    Находка адресована источнику: содержание правится там, поток односторонний.
    Правило существует, чтобы возражение было предъявимым — со списком
    идентификаторов, а не на словах.
    """
    for entry in g.entries:
        if not entry.examples or _from_the_future(entry.version):
            continue
        try:
            compile("\n".join(entry.examples), f"<{entry.id}>", "exec")
        except SyntaxError as exc:
            yield Issue(
                Severity.WARNING,
                "example-compiles",
                f"пример не компилируется: {type(exc).__name__} — {exc.msg}",
                entry.id,
            )
        except ValueError as exc:
            # Нулевой байт и подобное: compile() отвергает это ValueError,
            # и такой пример так же непригоден, как несобирающийся.
            yield Issue(
                Severity.WARNING,
                "example-compiles",
                f"пример не компилируется: {exc}",
                entry.id,
            )


def rule_related_resolves(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Связь «см. также» ведёт на существующую карточку.

    Оборванная ссылка не видна глазами: она просто не отрисуется, и читатель
    не узнает, что рядом было что-то полезное.
    """
    for entry in g.entries:
        for target in entry.related:
            if g.resolve(target) is None:
                yield Issue(
                    Severity.WARNING,
                    "related-resolves",
                    f"связь ведёт на {target!r}, которого в снимке нет",
                    entry.id,
                )


def rule_related_errors_resolve(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Названная в карточке ошибка соответствует карточке-исключению.

    Источник хранит здесь имена (``IndexError``), а не идентификаторы, поэтому
    разрешение идёт через :meth:`Glossary.resolve` — без учёта регистра. Имя,
    не соответствующее ни одной карточке, читателю не поможет: блок «частые
    ошибки» его просто не отрисует, и связь пропадёт молча.
    """
    for entry in g.entries:
        for target in entry.related_errors:
            found = g.resolve(target)
            if found is None:
                yield Issue(
                    Severity.WARNING,
                    "related-errors-resolve",
                    f"названа ошибка {target!r}, карточки с таким именем в снимке нет",
                    entry.id,
                )
            elif found.kind != "exception":
                yield Issue(
                    Severity.WARNING,
                    "related-errors-resolve",
                    f"{target!r} — карточка вида {found.kind!r}, а не исключение",
                    entry.id,
                )


def rule_duplicate_title(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Одинаковые имена в разных разделах — кандидаты на слияние."""
    by_title: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in g.entries:
        by_title[entry.title].append(entry)
    for title, group in by_title.items():
        if len(group) < DUPLICATE_THRESHOLD:
            continue
        where = ", ".join(f"{e.id} ({e.section})" for e in group)
        yield Issue(
            Severity.WARNING,
            "duplicate-title",
            f"имя {title!r} встречается {len(group)} раза: {where}",
        )


def rule_section_size(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Слишком маленький раздел — признак неполного покрытия темы."""
    for section, count in Counter(e.section for e in g.entries).items():
        if count < cfg.min_section_size:
            yield Issue(
                Severity.WARNING,
                "section-size",
                f"раздел {section!r} содержит {count} карточк(и) — "
                "тема покрыта не полностью",
            )


RULES: Final[tuple[Rule, ...]] = (
    rule_non_empty,
    rule_required_fields,
    rule_id_format,
    rule_unique_id,
    rule_kind,
    rule_color_group,
    rule_translated,
    rule_docs_url,
    rule_summary_length,
    rule_body_length,
    rule_version_format,
    rule_examples,
    rule_example_compiles,
    rule_related_resolves,
    rule_related_errors_resolve,
    rule_duplicate_title,
    rule_section_size,
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
