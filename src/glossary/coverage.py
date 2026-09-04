"""Покрытие официального Python карточками глоссария.

Сопоставляет инвентарь языка (:mod:`glossary.inventory`) с тем, что описано,
и отвечает на вопрос, которого не задаёт ни одно правило валидации: **чего в
глоссарии нет вовсе**. Валидатор судит написанные карточки; здесь считаются
ненаписанные.

Отсюда и отдельный контракт: находка валидатора говорит «эту карточку надо
поправить», находка покрытия — «эту карточку надо написать». Разные действия,
разный объём, разная частота изменений — смешивать их в одном файле значило бы
утопить сотню замечаний по содержанию в тысячах ненаписанных.

Сопоставление **точное**, без эвристик по «хвосту» имени. Так вышло не из
осторожности, а из формы данных: идентификаторы карточек уже полные — не
``reduce``, а ``functools.reduce``, не ``split``, а ``str.split``. Эвристика по
хвосту при таких данных не помогает, а вредит: одна карточка ``split`` закрыла
бы методы всех типов сразу.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from glossary.inventory import build_inventory
from glossary.loader import digest
from glossary.objections import PRODUCER, SOURCE

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glossary.inventory import Inventory
    from glossary.models import Glossary

__all__ = [
    "CATEGORIES",
    "SCHEMA",
    "SCHEMA_OF",
    "CategoryCoverage",
    "CoverageReport",
    "as_json",
    "as_markdown",
    "build_coverage",
    "collect",
    "known_names",
]

CATEGORIES: Final[tuple[str, ...]] = ("builtins", "methods", "exceptions", "stdlib")
"""Разрезы покрытия в порядке, в котором их читают.

Разрезы не равнозначны по цене пробела: непокрытая встроенная функция задевает
каждого, непокрытый член модуля — только тех, кто до него дошёл. Общее число
покрытия усреднило бы это в одно ничего не значащее число.
"""

_KIND_TO_CATEGORY: Final[Mapping[str, str]] = {
    "function": "builtins",
    "class": "builtins",
    "method": "methods",
    "exception": "exceptions",
}


def _category(module: str, kind: str) -> str:
    """Разрез, к которому относится сущность."""
    if kind == "exception":
        return "exceptions"
    if module != "builtins":
        return "stdlib"
    return _KIND_TO_CATEGORY.get(kind, "stdlib")


def known_names(glossary: Glossary) -> frozenset[str]:
    """Имена, которые глоссарий считает описанными.

    Берутся и идентификатор, и заголовок: карточка исключения хранит id в
    нижнем регистре (``indexerror``), а заголовком несёт настоящее имя
    (``IndexError``). Регистр снимается, скобки вызова отбрасываются —
    ``len()`` в заголовке и ``len`` в языке это одно и то же.
    """
    names: set[str] = set()
    for entry in glossary:
        for raw in (entry.id, entry.title, *entry.aliases):
            cleaned = raw.strip().removesuffix("()").lower()
            if cleaned:
                names.add(cleaned)
    return frozenset(names)


@dataclass(frozen=True, slots=True)
class CategoryCoverage:
    """Покрытие одного разреза."""

    name: str
    total: int
    missing: tuple[str, ...] = ()

    @property
    def covered(self) -> int:
        """Сколько сущностей разреза описано карточками."""
        return self.total - len(self.missing)

    @property
    def ratio(self) -> float:
        """Доля покрытия от нуля до единицы; пустой разрез — единица.

        Пустой разрез не «не покрыт»: покрывать в нём нечего. Ноль здесь читался
        бы как провал, а это разные вещи.
        """
        return 1.0 if not self.total else self.covered / self.total


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Покрытие языка карточками на одной версии Python."""

    python_version: str
    categories: tuple[CategoryCoverage, ...]
    _by_name: dict[str, CategoryCoverage] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Построить индекс по имени разреза."""
        object.__setattr__(self, "_by_name", {c.name: c for c in self.categories})

    def __getitem__(self, name: str) -> CategoryCoverage:
        """Разрез по имени."""
        return self._by_name[name]

    @property
    def total(self) -> int:
        """Сколько сущностей языка учтено всего."""
        return sum(c.total for c in self.categories)

    @property
    def missing(self) -> tuple[str, ...]:
        """Все непокрытые имена в каноническом порядке."""
        return tuple(sorted(name for c in self.categories for name in c.missing))

    @property
    def covered(self) -> int:
        """Сколько сущностей языка описано карточками."""
        return self.total - len(self.missing)

    @property
    def ratio(self) -> float:
        """Общая доля покрытия."""
        return 1.0 if not self.total else self.covered / self.total


def build_coverage(
    glossary: Glossary, inventory: Inventory | None = None
) -> CoverageReport:
    """Сопоставить глоссарий с инвентарём языка.

    Инвентарь передаётся параметром, а не снимается всегда сам: тест обязан
    уметь задать язык из трёх сущностей, иначе он будет проверять интроспекцию
    вместо сопоставления.
    """
    snapshot = inventory if inventory is not None else build_inventory()
    known = known_names(glossary)

    totals: dict[str, int] = dict.fromkeys(CATEGORIES, 0)
    missing: dict[str, list[str]] = {name: [] for name in CATEGORIES}
    for item in snapshot:
        category = _category(item.module, item.kind)
        totals[category] += 1
        if item.qualname.lower() not in known:
            missing[category].append(item.qualname)

    return CoverageReport(
        python_version=snapshot.python_version,
        categories=tuple(
            CategoryCoverage(
                name=name,
                total=totals[name],
                missing=tuple(sorted(missing[name])),
            )
            for name in CATEGORIES
        ),
    )


# --------------------------------------------------------------------------- #
# Контракт наружу
# --------------------------------------------------------------------------- #

SCHEMA: Final = 1
"""Версия формата ``coverage.json``. Растёт при несовместимом изменении."""

SCHEMA_OF: Final = "покрытие официального Python карточками глоссария"
"""Чего именно эта версия (правило каталога 164)."""

DEFAULT_LIMIT: Final = 20
"""Сколько имён показывать в разрезе человеку. В JSON список всегда полный."""


def collect(glossary: Glossary, inventory: Inventory | None = None) -> dict[str, Any]:
    """Собрать покрытие в машиночитаемый вид.

    ``python_version`` вынесена наверх, а не спрятана в разрезы: это ось
    измерения. Один и тот же глоссарий на разных версиях языка даёт разные
    ответы, и файл без версии нечем сравнить со вчерашним.
    """
    report = build_coverage(glossary, inventory)
    return {
        "schema": SCHEMA,
        "schema_of": SCHEMA_OF,
        "producer": PRODUCER,
        "source": SOURCE,
        "python_version": report.python_version,
        "snapshot": {"cards": len(glossary), "digest": digest(glossary)},
        "totals": {
            "known": report.total,
            "covered": report.covered,
            "missing": len(report.missing),
            "ratio": round(report.ratio, 4),
        },
        "categories": [
            {
                "name": category.name,
                "total": category.total,
                "covered": category.covered,
                "ratio": round(category.ratio, 4),
                "missing": list(category.missing),
            }
            for category in report.categories
        ],
    }


def as_json(glossary: Glossary, inventory: Inventory | None = None) -> str:
    """Покрытие как публикуемый контракт."""
    return json.dumps(collect(glossary, inventory), ensure_ascii=False, indent=2) + "\n"


def as_markdown(
    glossary: Glossary,
    inventory: Inventory | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Покрытие как письмо: что описать следующим."""
    data = collect(glossary, inventory)
    totals = data["totals"]
    lines = [
        "# Покрытие официального Python",
        "",
        f"Python **{data['python_version']}**, карточек **{data['snapshot']['cards']}**. "
        f"Описано **{totals['covered']}** из **{totals['known']}** "
        f"({totals['ratio']:.1%}), не описано **{totals['missing']}**.",
        "",
        "Инвентарь снят интроспекцией интерпретатора, без сети и без разбора "
        "документации. Синтаксис, устаревания и удаления в него не попадают — "
        "это видно только в документации, и такие пласты здесь не измеряются.",
        "",
        "| Разрез | Описано | Всего | Доля |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| `{c['name']}` | {c['covered']} | {c['total']} | {c['ratio']:.1%} |"
        for c in data["categories"]
    ]
    lines.append("")

    for category in data["categories"]:
        missing: list[str] = category["missing"]
        if not missing:
            continue
        lines += [f"## `{category['name']}` — не описано {len(missing)}", ""]
        shown = missing if limit <= 0 else missing[:limit]
        lines += [f"- `{name}`" for name in shown]
        if len(missing) > len(shown):
            hidden = len(missing) - len(shown)
            lines += ["", f"…и ещё {hidden}. Полный список: `--limit 0`."]
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
