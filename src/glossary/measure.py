"""Замер языка: инвентарь интерпретатора, на котором запущен, — в файл.

Это единственная точка входа пакета, которая исполняется **ниже планки**.
Планка проекта — 3.14, и весь остальной код пишется в её стиле. Замер же
обязан работать на каждой версии матрицы ``inventory`` в ``badges.yml``
(сейчас с 3.11): разность соседних снимков отвечает на «что появилось в
языке», и младшая версия — такая же точка измерения, как старшая.

Поэтому граница проведена импортами, а не договорённостью. Запуск::

    PYTHONPATH=src python -m glossary.measure -o inventory/inventory-3.11.json

загружает только цепочку замера — ``glossary``, ``glossary._version``,
``glossary.measure``, ``glossary.inventory``, ``glossary.contracts`` — и
ничего больше: пакетный ``__init__`` отдаёт остальное лениво (PEP 562).
Цепочка держит грамматику младшей версии замера и ``from __future__ import
annotations``; остальной пакет — нет. Обе половины стережёт
``tests/test_measured_versions.py``.

Исходы: 0 — инвентарь записан.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glossary import contracts, inventory

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main", "render"]


def render(snapshot: inventory.Inventory) -> str:
    """Снимок языка как документ контракта наружу.

    Args:
        snapshot: Инвентарь одной версии интерпретатора.

    Returns:
        JSON с общей шапкой контрактов и переводом строки в конце.
    """
    payload = {
        **contracts.envelope(inventory.SCHEMA_OF),
        "python_version": snapshot.python_version,
        "count": len(snapshot),
        "items": [
            {"qualname": item.qualname, "module": item.module, "kind": item.kind}
            for item in snapshot
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write(snapshot: inventory.Inventory, output: Path | None) -> str | None:
    """Записать снимок в файл или вернуть его текстом.

    Args:
        snapshot: Инвентарь одной версии.
        output: Файл результата; ``None`` — не писать, вернуть текст.

    Returns:
        Текст снимка, если файл не задан, иначе ``None``.
    """
    rendered = render(snapshot)
    if output is None:
        return rendered
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа замера.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(prog="glossary.measure", description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="файл результата (по умолчанию — stdout)",
    )
    args = parser.parse_args(argv)

    snapshot = inventory.build_inventory()
    text = write(snapshot, args.output)
    if text is not None:
        sys.stdout.write(text)
    else:
        sys.stdout.write(
            f"Инвентарь Python {snapshot.python_version}: "
            f"{len(snapshot)} сущностей → {args.output}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
