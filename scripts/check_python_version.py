#!/usr/bin/env python3
"""Код конвейера исполняется на объявленной версии Python, а не на случайной.

Правило каталога 217: переезд на версию языка сделан, когда на ней исполняется
всё, а не когда объявлена планка. После перехода на 3.14 (Glossary-Python#53)
две работы — постановка в очередь (``automerge.yml:arm``) и сводка вердиктов
(``ci.yml:check-pr``) — звали python раньше ``setup-python``, то есть системным
python раннера, и ни одна проверка этого не спрашивала (Glossary-Python#69).

Образец — ``scripts/check_python_version.py`` каталога правил; разбор здесь
свой, по YAML, а не по строкам: дерево и так держит разобранные прогоны в
наборах, а построчный разбор отступов — третья реализация одного предмета.

ЧТО ПРОВЕРЯЕТСЯ, по каждой работе каждого прогона:

* **python раньше setup-python** — шаг ``run`` зовёт python, pip, pytest, ruff
  или mypy, а установки выше него в той же работе нет;
* **версия не числом** — ``python-version`` не сводится к числам: выражение,
  кроме ссылки на матрицу из чисел, или файл версии — сверять не с чем;
* **ниже планки** — версия меньше ``requires-python`` (её читает
  ``scripts/python_floor.py``). Исключение одно и названо: работы ЗАМЕРА
  языка (``MEASUREMENT``) — они меряют младшие версии по замыслу;
* **предварительная не впереди** — шаг с ``allow-prereleases`` на версии не
  выше проверяемых ничего не спрашивает о следующей (правило 051);
* **окно ниже планки** — гейт запущен интерпретатором младше планки: «чисто
  локально» снято не на той поверхности (037).

Исходы: 0 — чисто; 1 — находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Final, NamedTuple

import yaml

import python_floor

ROOT: Final = Path(__file__).resolve().parent.parent
WORKFLOWS: Final = ROOT / ".github" / "workflows"
NOT_RUN: Final = 2

SETUP: Final = "actions/setup-python"
CALL_RE: Final = re.compile(r"(?<![\w./-])(python3?|pip3?|pytest|ruff|mypy)(?![\w-])")
"""Вызов интерпретатора или инструмента, который он исполняет."""

MATRIX_RE: Final = re.compile(r"^\$\{\{\s*matrix\.([\w-]+)\s*\}\}$")
NUMBER_RE: Final = re.compile(r"^(\d+)\.(\d+)$")

MEASUREMENT: Final = {
    ("badges.yml", "inventory"): "замер языка на версиях ниже планки — по замыслу",
    ("badges.yml", "preview"): "замер языка на предварительной версии",
}
"""Работы замера языка: их версии — предмет измерения, а не обещание проекта."""


class Setup(NamedTuple):
    """Шаг установки Python в работе.

    Attributes:
        versions: Версии, которые шаг ставит; пусто — числом не названы.
        preview: Объявлен ли ``allow-prereleases``.
    """

    versions: tuple[tuple[int, int], ...]
    preview: bool


def _numbers(value: str, matrix: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    """Версии, к которым сводится значение ``python-version``; пусто — не сводится."""
    found = MATRIX_RE.match(value)
    raw = [str(v) for v in matrix.get(found.group(1), [])] if found else [value]
    out: list[tuple[int, int]] = []
    for item in raw:
        number = NUMBER_RE.match(item.strip())
        if number is None:
            return ()
        out.append((int(number.group(1)), int(number.group(2))))
    return tuple(out)


def job_findings(
    workflow: str, name: str, job: dict[str, Any], floor: tuple[int, int]
) -> tuple[list[str], list[Setup]]:
    """Находки одной работы и её шаги установки.

    Args:
        workflow: Имя файла прогона — попадает в текст находки.
        name: Имя работы.
        job: Разобранное тело работы.
        floor: Планка проекта.

    Returns:
        Находки и шаги установки по порядку.
    """
    where = f".github/workflows/{workflow}: работа {name}"
    matrix = job.get("strategy", {}).get("matrix", {}) or {}
    problems: list[str] = []
    setups: list[Setup] = []
    for step in job.get("steps", []):
        uses = str(step.get("uses", ""))
        if uses.startswith(SETUP):
            spec = step.get("with", {}) or {}
            versions = _numbers(str(spec.get("python-version", "")), matrix)
            if not versions:
                problems.append(
                    f"{where}: setup-python без числа в python-version — версию "
                    "не с чем сверить с планкой, и ниже неё она пройдёт молча"
                )
            setups.append(Setup(versions, bool(spec.get("allow-prereleases"))))
            continue
        if not setups and CALL_RE.search(str(step.get("run", ""))):
            problems.append(
                f"{where}: зовёт python раньше setup-python — код исполняется "
                "системным python раннера, а не версией планки (217)"
            )
            break
    if (workflow, name) not in MEASUREMENT:
        low = sorted(
            {v for s in setups if not s.preview for v in s.versions if v < floor}
        )
        problems.extend(
            f"{where}: гоняет {a}.{b}, а планка >={floor[0]}.{floor[1]} — "
            "конвейер проверяет версию, которую проект не обещает"
            for a, b in low
        )
    return problems, setups


def findings(
    workflows: dict[str, dict[str, Any]],
    floor: tuple[int, int],
    window: tuple[int, int],
) -> list[str]:
    """Все находки по прогонам и окну.

    Args:
        workflows: Имя файла прогона → разобранный прогон.
        floor: Планка проекта.
        window: Версия интерпретатора, которым запущен гейт.

    Returns:
        Готовые к печати находки.
    """
    problems: list[str] = []
    checked: set[tuple[int, int]] = set()
    previews: list[tuple[str, tuple[int, int]]] = []
    for workflow, document in sorted(workflows.items()):
        for name, job in (document.get("jobs") or {}).items():
            found, setups = job_findings(workflow, name, job, floor)
            problems.extend(found)
            measured = (workflow, name) in MEASUREMENT
            for setup in setups:
                if setup.preview and not measured:
                    previews.extend((workflow, v) for v in setup.versions)
                elif not measured:
                    checked.update(setup.versions)
    top = max(checked, default=floor)
    problems.extend(
        f".github/workflows/{workflow}: предварительная {a}.{b} не выше "
        f"проверяемой {top[0]}.{top[1]} — она ничего не спрашивает о следующей "
        "версии, а выглядит так, будто спрашивает (051)"
        for workflow, (a, b) in previews
        if (a, b) <= top
    )
    if window < floor:
        problems.append(
            f"гейт запущен на {window[0]}.{window[1]}, а планка "
            f">={floor[0]}.{floor[1]}: «чисто локально» снято ниже объявленной "
            "поверхности (037)"
        )
    return problems


def main(root: Path = ROOT) -> int:
    """Точка входа."""
    pyproject = root / "pyproject.toml"
    try:
        floor = python_floor.floor(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError) as refusal:
        print(
            f"проверка не отработала: планка из {pyproject}: {refusal}", file=sys.stderr
        )
        return NOT_RUN
    folder = root / ".github" / "workflows"
    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for path in sorted(folder.glob("*.yml"))
    }
    if not workflows:
        print(
            f"проверка не отработала: в {folder} нет прогонов — сверять нечего, "
            "и зеленеть на пустоте нельзя (075)",
            file=sys.stderr,
        )
        return NOT_RUN

    window = (sys.version_info.major, sys.version_info.minor)
    problems = findings(workflows, floor, window)
    if problems:
        print("объявленная версия Python разошлась с фактической:", file=sys.stderr)
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        return 1
    print(
        f"версии сходятся: планка >={floor[0]}.{floor[1]}, прогонов {len(workflows)}, "
        f"работ замера {len(MEASUREMENT)}, окно {window[0]}.{window[1]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
