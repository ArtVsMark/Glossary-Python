"""Правила качества глоссария.

Валидатор построен как реестр независимых правил: каждое правило получает
глоссарий целиком и возвращает найденные проблемы. Добавление новой проверки —
это одна функция и одна строка в :data:`RULES`, без изменения остального кода.

Разделение на ``ERROR`` и ``WARNING`` намеренное: ошибки ломают сборку в CI,
предупреждения формируют бэклог по качеству данных и не блокируют работу.
"""

import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from glossary.models import (
    ALL_OS,
    COLOR_GROUPS,
    KINDS,
    LANGUAGES,
    PLATFORMS,
    SYSTEMS,
    Entry,
    Glossary,
)

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
CYRILLIC: Final = re.compile(r"[А-Яа-яЁё]")
LATIN: Final = re.compile(r"[A-Za-z]")
VERSION_PATTERN: Final = re.compile(r"^\d+\.\d+$")
DOCS_PREFIX: Final = "https://docs.python.org/3/"
DUPLICATE_THRESHOLD: Final = 2
"""Начиная со скольких вхождений имя считается дублирующимся."""
GENERIC_DOCS: Final = frozenset({DOCS_PREFIX, "https://docs.python.org/3"})
_REQUIRED_TEXT_FIELDS: Final = (
    "id",
    "kind",
    "status",
    "section",
    "syntax",
    "docs_url",
)
_LABEL_FIELDS: Final = ("title", "subcat")
"""Двуязычные подписи карточки (схема v3).

Обе половины обязательны: русскую требует ``required-fields``, английскую —
``label-translated``.
"""


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
    max_foreign_script: float = 0.15
    """Доля кириллицы, выше которой английская половина считается непереведённой.

    Не ноль намеренно: английский текст вправе назвать кириллицу примером —
    так делают карточки о ``string.ascii_letters`` и ``string.printable``.
    """


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
        for name in _LABEL_FIELDS:
            if not getattr(entry, name).ru.strip():
                yield Issue(
                    Severity.ERROR,
                    "required-fields",
                    f"поле {name!r} пустое на языке 'ru'",
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
    """Обе языковые версии заполнены — и сводка, и тело.

    Совпадение ключей — ещё не перевод: пустая половина даёт карточку, которая
    на одном из языков выглядит сломанной, а не отсутствующей.

    Пустое тело было предупреждением, пока 309 карточек ждали текста (#84), и
    стало ошибкой, когда тела заполнены у всех (#114): иначе ``main``
    покраснела бы на незаполненных данных.
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
                    Severity.ERROR,
                    "translated",
                    f"тело карточки не заполнено на языке {language!r}",
                    entry.id,
                )


def rule_label_translated(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Заголовок и подкатегория переведены на английский.

    Отдельно от :func:`rule_translated`, а не внутри него: подписи стали
    двуязычными в схеме v3, и их долг — свой, с собственной планкой. Слитый в
    ``translated``, он поднял бы чужую планку, которая движется только вниз.

    Уровень — ошибка. Правило вошло предупреждением вместе со схемой v3 (#90)
    и стало ошибкой, когда все подписи были переведены (#91): иначе ``main``
    покраснела бы на непереведённых данных.
    """
    for entry in g.entries:
        for name in _LABEL_FIELDS:
            label = getattr(entry, name)
            if label.ru.strip() and not label.en.strip():
                yield Issue(
                    Severity.ERROR,
                    "label-translated",
                    f"поле {name!r} не переведено на английский",
                    entry.id,
                )


def rule_language_script(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Английская половина написана латиницей, а не оставлена русской.

    Правило каталога 077: полнота ключей проверяет, что строку не забыли
    добавить, и ничего не говорит о том, что её **перевели**. Заполненность,
    которую проверяет :func:`rule_translated`, — тоже свойство ключа, а не
    текста: скопированная в английское поле русская фраза проходит её зелёной.
    Здесь проверяется свойство самого текста — письменность.

    ПОРОГ ВЗЯТ ЗАМЕРОМ, А НЕ НА ГЛАЗ. На этом дереве кириллица встречается в
    английской половине двух карточек — ``string.ascii_letters`` и
    ``string.printable``, — и там она законна: обе называют кириллицу примером
    того, чего в константе нет. Их доля — 0.004 и 0.003; у половины, оставшейся
    русской, доля была бы выше 0.5. Порог отделяет одно от другого с запасом.

    ОБРАТНОЕ НАПРАВЛЕНИЕ НЕ ПРОВЕРЯЕТСЯ, и это измерено, а не забыто:
    «русская половина написана латиницей» на этом дереве даёт 0.923 у карточки
    ``string.ascii_lowercase``, которая цитирует алфавит. Признак там шумит, и
    правило о нём молчит вместо того, чтобы краснеть на верных данных.
    """
    for entry in g.entries:
        for field_name in ("summary", "body", *_LABEL_FIELDS):
            text = getattr(entry, field_name).get("en").strip()
            share = _cyrillic_share(text)
            if share > cfg.max_foreign_script:
                yield Issue(
                    Severity.ERROR,
                    "language-script",
                    f"английская половина поля {field_name!r} написана кириллицей "
                    f"на {share:.0%} — похоже, её не перевели, а скопировали",
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


def rule_platforms(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Платформы названы явно, из закрытого списка, у «везде» одна форма.

    «Везде» — ``AllOS`` и только он: пустой список неотличим от «не заполнено»,
    а три системы поимённо — вторая форма того же ответа, и витрина показала бы
    значок там, где ограничения нет.
    """
    for entry in g.entries:
        if not entry.platforms:
            yield Issue(
                Severity.ERROR,
                "platforms",
                f"платформы не указаны; для «везде» — {ALL_OS}",
                entry.id,
            )
            continue
        if ALL_OS in entry.platforms and len(entry.platforms) > 1:
            yield Issue(
                Severity.ERROR,
                "platforms",
                f"{ALL_OS} не сочетается с отдельными системами",
                entry.id,
            )
        unknown = sorted(set(entry.platforms) - set(PLATFORMS))
        if unknown:
            yield Issue(
                Severity.ERROR,
                "platforms",
                f"неизвестные платформы {unknown}; допустимы: {', '.join(PLATFORMS)}",
                entry.id,
            )
        if len(set(entry.platforms)) != len(entry.platforms):
            yield Issue(Severity.ERROR, "platforms", "платформа повторяется", entry.id)
        if set(entry.platforms) == set(SYSTEMS):
            yield Issue(
                Severity.ERROR,
                "platforms",
                f"перечислены все системы — это «везде», пишется {ALL_OS}",
                entry.id,
            )


_CLAIM_SYSTEMS: Final[dict[str, frozenset[str]]] = {
    "Unix": frozenset({"Linux", "macOS"}),
    "Linux": frozenset({"Linux"}),
    "Windows": frozenset({"Windows"}),
}
_CLAIM_RU: Final = re.compile(
    r"(?:^|[.!?]\s+)(?:Доступно на|Только(?: на)?) (Unix|Linux|Windows)\b"
)
_CLAIM_EN: Final = re.compile(
    r"Availability: (Unix|Linux|Windows)\b"
    r"|(?:^|[.!?]\s+)(?:Only on|Available on) (Unix|Linux|Windows)\b"
    r"|(?:^|[.!?]\s+)(Unix|Linux|Windows)[- ]only\b"
)


def rule_platforms_summary(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Сводка, назвавшая доступность, не спорит с полем ``platforms``.

    Сводка с «Доступно на Unix» при ``platforms = AllOS`` учит неправде дважды:
    текстом и значком, говорящими разное. Так разошлись 38 карточек, пока
    поле заполнялось по документации, а сводки оставались прежними (#110).

    Утверждением считается формула о самом объекте: «Доступно на X», «Только
    X» в начале предложения, «Availability: X». Фраза «функция os.uname —
    только на Unix» в середине предложения говорит о соседнем объекте и не
    проверяется — ГРАНИЦА НАЗВАНА, а не подразумевается.
    """
    for entry in g.entries:
        claims = [
            name
            for half, pattern in (("ru", _CLAIM_RU), ("en", _CLAIM_EN))
            for match in pattern.finditer(entry.summary.get(half))
            for name in match.groups()
            if name
        ]
        actual = set(entry.platforms)
        for name in dict.fromkeys(claims):
            allowed = _CLAIM_SYSTEMS[name]
            if ALL_OS in actual or not actual <= allowed:
                yield Issue(
                    Severity.ERROR,
                    "platforms-summary",
                    f"сводка говорит «{name}», а platforms — "
                    f"{', '.join(entry.platforms) or 'пусто'}",
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


def _cyrillic_share(text: str) -> float:
    """Доля кириллицы среди буквенных знаков текста.

    Считается доля, а не наличие: английский текст вправе назвать кириллицу
    примером, и одна буква не делает половину непереведённой.

    Args:
        text: Текст половины карточки.

    Returns:
        Доля от 0 до 1; ноль, если букв в тексте нет вовсе.
    """
    cyrillic = len(CYRILLIC.findall(text))
    latin = len(LATIN.findall(text))
    letters = cyrillic + latin
    return cyrillic / letters if letters else 0.0


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

    Правило существует, чтобы дефект был списком идентификаторов, а не
    словами: по нему карточки правятся в ``data/cards/``.
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


def _title_key(title: str) -> str:
    """Заголовок для сравнения: без регистра и без ``()`` вызова на конце."""
    return title.strip().removesuffix("()").lower()


def rule_duplicate_title(g: Glossary, cfg: ValidationConfig) -> Iterator[Issue]:
    """Две карточки об одном объекте — ошибка: правку получит одна из них.

    Дубль ловится двумя способами. Первый — одинаковый английский заголовок
    после нормализации: ``os.getenv`` и ``os.getenv()`` — одно и то же. Второй —
    голое имя и полное имя с одной ссылкой на документацию: ``Counter`` и
    ``collections.Counter``. Буквальное сравнение пропускало оба случая, и
    8 пар прожили незамеченными, пока их не слили (#79).

    Совпадение последнего сегмента без общей ссылки дублем не считается:
    ``str.count`` и ``list.count`` — разные методы.
    """
    by_title: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in g.entries:
        by_title[_title_key(entry.title.en)].append(entry)
    for title, group in by_title.items():
        if len(group) < DUPLICATE_THRESHOLD:
            continue
        where = ", ".join(f"{e.id} ({e.section})" for e in group)
        yield Issue(
            Severity.ERROR,
            "duplicate-title",
            f"имя {title!r} встречается {len(group)} раза: {where}",
        )
    qualified: defaultdict[tuple[str, str], list[Entry]] = defaultdict(list)
    for entry in g.entries:
        key = _title_key(entry.title.en)
        if "." in key:
            qualified[key.rsplit(".", 1)[1], entry.docs_url].append(entry)
    for entry in g.entries:
        key = _title_key(entry.title.en)
        if "." in key:
            continue
        for twin in qualified.get((key, entry.docs_url), []):
            yield Issue(
                Severity.ERROR,
                "duplicate-title",
                f"{entry.id} и {twin.id} — одно имя ({key!r} и "
                f"{_title_key(twin.title.en)!r}) и одна ссылка на документацию",
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
    rule_label_translated,
    rule_language_script,
    rule_docs_url,
    rule_summary_length,
    rule_body_length,
    rule_version_format,
    rule_platforms,
    rule_platforms_summary,
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
