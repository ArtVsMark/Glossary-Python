"""Факты о проекте: считает издатель, читает потребитель.

Число, вписанное в документацию руками, устаревает молча. Здесь оно считается
из порождающего источника, попадает в README **внутрь именованного маркера** и
проверяется гейтом: пропал маркер — падает сборка, а не тихо остаётся старое
значение (правила каталога 005, 127, 174).

Производное не коммитится в общую ветку: ``facts.json`` и значки собираются
прогоном и уезжают на Pages рядом с витриной. В ``main`` их нет — они
пересобираются чаще, чем идут изменения (правило 160).

Ключа, который не удалось измерить, в выдаче **нет**. Ноль читался бы как
измеренный ноль, а это разные вещи.

Запуск::

    python scripts/facts.py --json                # факты в stdout
    python scripts/facts.py --badges _site/badges # значки shields.io
    python scripts/facts.py --render              # переписать маркеры README
    python scripts/facts.py --check               # гейт: маркеры на месте и совпадают
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Final

import yaml

from glossary.loader import load_glossary
from glossary.validation import Severity, validate

ROOT: Final = Path(__file__).resolve().parent.parent
README: Final = ROOT / "README.md"
COVERAGE: Final = ROOT / "coverage.xml"

SCHEMA: Final = 1
REPO: Final = "ArtVsMark/Glossary-Python"
GOOD_COVERAGE: Final = 90.0
"""С какого покрытия значок зеленеет. Совпадает с порогом --cov-fail-under в CI."""

MARKER: Final = re.compile(
    r"<!--m:(?P<name>[a-z0-9_]+)-->(?P<value>.*?)<!--/m:(?P=name)-->", re.DOTALL
)
"""Именованный маркер вокруг числа. Форма та же, что у каталога правил."""


def _glossary_facts() -> dict[str, int]:
    """Числа о самом глоссарии — из файла-источника, а не из витрины."""
    glossary = load_glossary(ROOT / "data" / "glossary.json")
    report = validate(glossary)
    stats = glossary.stats()
    return {
        "cards": stats.total,
        "groups": len(stats.groups),
        "errors": sum(1 for i in report.issues if i.severity is Severity.ERROR),
        "warnings": sum(1 for i in report.issues if i.severity is Severity.WARNING),
    }


def _rules_facts() -> dict[str, int]:
    """Состав ответа каталогу правил — из самого ответа."""
    doc = json.loads((ROOT / ".rules" / "bindings.json").read_text(encoding="utf-8"))
    answers: dict[str, dict[str, str]] = doc["rules"]
    mechanisms = Counter(
        v.get("mechanism") for v in answers.values() if v["status"] == "active"
    )
    statuses = Counter(v["status"] for v in answers.values())
    held = sum(count for name, count in mechanisms.items() if name != "none")
    return {
        "total": len(answers),
        "gate": mechanisms["gate"],
        "document": mechanisms["document"],
        "pipeline": mechanisms["pipeline"],
        "mechanised": held,
        "none": mechanisms["none"],
        "not_applicable": statuses["not-applicable"],
    }


def _coverage_percent() -> float | None:
    """Покрытие из ``coverage.xml``; ``None``, если отчёта нет.

    Отсутствие отчёта — «не измеряли», а не «ноль процентов», поэтому ключ
    в выдаче не появляется вовсе.
    """
    if not COVERAGE.exists():
        return None
    try:
        # S314: разбирается coverage.xml, порождённый нашим же прогоном
        # в этом же рабочем каталоге, — не чужой ввод.
        rate = ET.parse(COVERAGE).getroot().get("line-rate")  # noqa: S314
    except ET.ParseError:
        return None
    return round(float(rate) * 100, 1) if rate is not None else None


def _python_versions() -> list[str]:
    """Матрица версий — из прогона, а не из прозы о нём."""
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    versions = ci["jobs"]["tests"]["strategy"]["matrix"]["python-version"]
    return [str(v) for v in versions]


def build_facts() -> dict[str, Any]:
    """Собрать факты о проекте.

    Returns:
        Словарь, пригодный к публикации. Ключи, которые не удалось измерить,
        отсутствуют — их не выставляют нулём.
    """
    facts: dict[str, Any] = {
        "schema": SCHEMA,
        "repo": REPO,
        "glossary": _glossary_facts(),
        "rules": _rules_facts(),
        "python_versions": _python_versions(),
    }
    coverage = _coverage_percent()
    if coverage is not None:
        facts["coverage_percent"] = coverage
    return facts


def marker_values(facts: dict[str, Any]) -> dict[str, str]:
    """Значения маркеров README, выведенные из фактов."""
    glossary = facts["glossary"]
    rules = facts["rules"]
    return {
        "cards": str(glossary["cards"]),
        "groups": str(glossary["groups"]),
        "errors": str(glossary["errors"]),
        "warnings": str(glossary["warnings"]),
        "rules_total": str(rules["total"]),
        "rules_mechanised": str(rules["mechanised"]),
        "rules_gate": str(rules["gate"]),
        "rules_document": str(rules["document"]),
        "rules_pipeline": str(rules["pipeline"]),
        "rules_none": str(rules["none"]),
        "rules_na": str(rules["not_applicable"]),
    }


def render(text: str, values: dict[str, str]) -> str:
    """Переписать значения внутри маркеров, не трогая остальной текст."""

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        value = values.get(name, match.group("value"))
        return f"<!--m:{name}-->{value}<!--/m:{name}-->"

    return MARKER.sub(replace, text)


def check(text: str, values: dict[str, str]) -> list[str]:
    """Найти расхождения README с фактами.

    Пропавший маркер — тоже расхождение: без третьего условия правила 127
    механизма нет, есть ручное число с лишним шагом.
    """
    found = {m.group("name"): m.group("value") for m in MARKER.finditer(text)}
    problems: list[str] = []
    for name, expected in sorted(values.items()):
        if name not in found:
            problems.append(f"маркер {name!r} пропал из README — сборке нечего писать")
        elif found[name] != expected:
            problems.append(
                f"маркер {name!r}: в README {found[name]!r}, по источнику {expected!r}"
            )
    problems.extend(
        f"маркер {name!r} есть в README, но фактов для него нет"
        for name in sorted(found.keys() - values.keys())
    )
    return problems


def write_badges(facts: dict[str, Any], target: Path) -> list[Path]:
    """Записать значки в формате shields.io endpoint."""
    rules = facts["rules"]
    glossary = facts["glossary"]
    badges: dict[str, dict[str, Any]] = {
        "cards": {
            "label": "карточек",
            "message": str(glossary["cards"]),
            "color": "blue",
        },
        "rules": {
            "label": "правил без механизма",
            "message": str(rules["none"]),
            "color": "orange" if rules["none"] else "brightgreen",
        },
        "warnings": {
            "label": "замечаний",
            "message": str(glossary["warnings"]),
            "color": "yellow" if glossary["warnings"] else "brightgreen",
        },
    }
    if "coverage_percent" in facts:
        percent = facts["coverage_percent"]
        badges["coverage"] = {
            "label": "покрытие",
            "message": f"{percent}%",
            "color": "brightgreen" if percent >= GOOD_COVERAGE else "yellow",
        }

    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Факты лежат рядом со значками намеренно: потребитель забирает их тем же
    # способом и из того же места, что и значки (правило 174).
    facts_path = target / "facts.json"
    facts_path.write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    written.append(facts_path)

    for name, body in badges.items():
        path = target / f"{name}.json"
        path.write_text(
            json.dumps({"schemaVersion": 1, **body}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 1, если гейт нашёл расхождения."""
    parser = argparse.ArgumentParser(description=__doc__, prog="facts")
    parser.add_argument("--json", action="store_true", help="напечатать факты")
    parser.add_argument(
        "--badges",
        type=Path,
        nargs="?",
        const=ROOT / ".github" / "badges",
        metavar="DIR",
        help="куда класть значки и факты (по умолчанию .github/badges)",
    )
    parser.add_argument("--render", action="store_true", help="переписать README")
    parser.add_argument("--check", action="store_true", help="гейт на маркеры README")
    args = parser.parse_args(argv)

    facts = build_facts()
    values = marker_values(facts)

    if args.json or not any((args.badges, args.render, args.check)):
        print(json.dumps(facts, ensure_ascii=False, indent=2))

    if args.badges:
        for path in write_badges(facts, args.badges):
            print(f"→ {path.relative_to(ROOT) if ROOT in path.parents else path}")

    text = README.read_text(encoding="utf-8")

    if args.render:
        updated = render(text, values)
        if updated != text:
            README.write_text(updated, encoding="utf-8")
            print("README обновлён")
        else:
            print("README уже совпадает с фактами")
        text = updated

    if args.check:
        problems = check(text, values)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            print(
                "\nЧисла в документации переписывает сборка: "
                "выполните `python scripts/facts.py --render`",
                file=sys.stderr,
            )
            return 1
        print(f"маркеров сверено: {len(values)}, расхождений нет")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
