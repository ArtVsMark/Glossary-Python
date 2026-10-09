#!/usr/bin/env python3
"""Манифест семьи: что глоссарий отдаёт соседям — для семейного значка (#258).

Каталог правил (v1.11.0) собирает манифесты проектов семьи в сводку
``export/family.json``, и каждый проект сверяет по ней, на чём стоит. Манифест
лежит на ветке ``badges`` по адресу ``.github/badges/contracts.json``; форма —
контракт ``family`` 1.1 каталога (``scripts/family.py``):

* ``release`` — последний выпуск: тег и его коммит;
* ``gives`` — что проект отдаёт: ``glossary-form`` — форма карточки в выгрузке
  для грейдера (``glossary.delivery.FORM``). Номер читается оттуда, а не
  переписывается второй копией (правило 049): по нему грейдер окрашивает свой
  сегмент ``pairs``;
* ``takes`` — парных связей у глоссария нет: всё, что он берёт у семьи
  (действия каталога, номера ответа, договор фактов), сверка находит в дереве
  сама;
* ``skips`` — отказ от связи с издателем, с причиной.

Исходы: 0 — манифест записан; 2 — выпуска не прочитать (git не ответил).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

import version
from glossary.delivery import FORM

ROOT: Final = Path(__file__).resolve().parent.parent
NOT_RUN: Final = 2
FAMILY_SCHEMA: Final = "1.1"
"""Номер формата манифеста по контракту ``family`` каталога."""

PROJECT: Final = "ArtVsMark/Glossary-Python"
GIVES_FORM: Final = "glossary-form"
"""Имя контракта формы карточек — согласовано с ``takes`` грейдера (#258)."""

SKIPS: Final[dict[str, str]] = {
    "EPM": (
        "шагов механизмов глоссарий не берёт: его конвейер держат свои гейты "
        "scripts/check_*.py и действия каталога, а предмета, который они бы "
        "закрыли сверх этого, не названо"
    ),
}
"""Отказ от связи с издателем семьи. Без него ``EPM`` на значке красный."""

DEFAULT_OUT: Final = ROOT / ".github" / "badges" / "contracts.json"


def release() -> dict[str, str] | None:
    """Последний выпуск ``vX.Y.0`` и его коммит; ``None``, пока тегов нет.

    Raises:
        RuntimeError: тег есть, а коммит его не прочитан.
    """
    tag = version.latest_tag()
    if tag is None:
        return None
    sha = version.git("rev-list", "-n", "1", tag)
    if not sha:
        raise RuntimeError(f"коммит тега {tag} не прочитан")
    return {"tag": tag, "sha": sha}


def manifest(rel: dict[str, str] | None) -> dict[str, Any]:
    """Манифест глоссария по контракту ``family`` 1.1."""
    return {
        "schema": FAMILY_SCHEMA,
        "project": PROJECT,
        "release": rel,
        "gives": {GIVES_FORM: FORM},
        "takes": [],
        "skips": dict(SKIPS),
    }


def main(argv: list[str] | None = None) -> int:
    """Точка входа: записать манифест."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        rel = release()
    except RuntimeError as error:
        print(f"family_manifest: {error}", file=sys.stderr)
        return NOT_RUN
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest(rel), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"→ {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
