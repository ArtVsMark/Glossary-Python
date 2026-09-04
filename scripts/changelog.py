"""Журнал изменений собирается из фрагментов, а не пишется в общий файл.

Строка в общем ``CHANGELOG.md`` стоит конфликта на каждом параллельном
изменении, а конфликтный PR остаётся **вовсе без проверок**: прогон идёт по
merge-коммиту, которого при конфликте не существует, и пустой список проверок
читается как «CI сломался» (правила каталога 030 и 010).

Форма фрагмента повторяет конвенцию соседнего проекта
(``ArtVsMark/Stepik-Python-Grader``) намеренно: две реализации одного алгоритма
разошлись бы на первой же правке, а общего места для такого инструмента в
экосистеме пока нет.

Имя файла::

    changelog.d/<slug>.<секция>.md

``slug`` — что угодно уникальное, обычно имя ветки без префикса. Секция — одна
из ``added``, ``changed``, ``fixed``, ``removed``, ``internal``. Внутри — одна
строка текста: без ведущего дефиса и без имени секции, их подставит сборка.

Запуск::

    python scripts/changelog.py --check     # форма фрагментов (гейт)
    python scripts/changelog.py --preview   # как соберётся, ничего не меняя
    python scripts/changelog.py --collect   # перенести в [Unreleased] и удалить
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
FRAGMENTS: Final = ROOT / "changelog.d"
CHANGELOG: Final = ROOT / "CHANGELOG.md"

SECTIONS: Final[dict[str, str]] = {
    "added": "Добавлено",
    "changed": "Изменено",
    "fixed": "Исправлено",
    "removed": "Удалено",
    "internal": "Внутреннее",
}
"""Секции журнала в порядке вывода. Ключ — суффикс имени файла."""

UNRELEASED: Final = "## [Unreleased]"
NAME: Final = re.compile(r"^(?P<slug>[a-z0-9][a-z0-9-]*)\.(?P<section>[a-z]+)\.md$")


@dataclass(frozen=True, slots=True)
class Fragment:
    """Одна запись журнала, лежащая отдельным файлом."""

    path: Path
    slug: str
    section: str
    text: str

    @property
    def line(self) -> str:
        """Запись в том виде, в каком она попадёт в журнал."""
        return f"- {self.text}"


def read_fragments() -> tuple[list[Fragment], list[str]]:
    """Прочитать фрагменты и собрать замечания к их форме.

    Returns:
        Пара «фрагменты, замечания». Замечания непустые — форма нарушена.
    """
    problems: list[str] = []
    fragments: list[Fragment] = []
    if not FRAGMENTS.is_dir():
        return fragments, [f"каталог {FRAGMENTS.name} отсутствует — класть записи некуда"]

    for path in sorted(FRAGMENTS.iterdir()):
        if path.name == "README.md" or path.name.startswith("."):
            continue
        match = NAME.match(path.name)
        if match is None:
            problems.append(
                f"{path.name}: имя не по форме <slug>.<секция>.md, "
                f"секции: {', '.join(SECTIONS)}"
            )
            continue
        section = match.group("section")
        if section not in SECTIONS:
            problems.append(
                f"{path.name}: секция {section!r} неизвестна; "
                f"допустимы {', '.join(SECTIONS)}"
            )
            continue

        lines = [ln.strip() for ln in path.read_text("utf-8").splitlines() if ln.strip()]
        if not lines:
            problems.append(f"{path.name}: пустой фрагмент — записи нет")
            continue
        if len(lines) > 1:
            problems.append(f"{path.name}: {len(lines)} строк, а запись — одна")
            continue
        text = lines[0]
        if text.startswith("-"):
            problems.append(f"{path.name}: ведущий дефис подставит сборка, убери его")
            continue
        fragments.append(Fragment(path, match.group("slug"), section, text))

    return fragments, problems


def render(fragments: list[Fragment]) -> str:
    """Собрать текст для раздела ``[Unreleased]``."""
    blocks: list[str] = []
    for section, title in SECTIONS.items():
        lines = sorted(f.line for f in fragments if f.section == section)
        if lines:
            blocks.append(f"### {title}\n\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def collect(fragments: list[Fragment]) -> int:
    """Перенести фрагменты в ``[Unreleased]`` и удалить их файлы."""
    body = render(fragments)
    text = CHANGELOG.read_text("utf-8")
    if UNRELEASED not in text:
        print(f"в {CHANGELOG.name} нет раздела {UNRELEASED}", file=sys.stderr)
        return 1
    head, _, tail = text.partition(UNRELEASED)
    CHANGELOG.write_text(f"{head}{UNRELEASED}\n\n{body}\n{tail}", encoding="utf-8")
    for fragment in fragments:
        fragment.path.unlink()
    print(f"перенесено записей: {len(fragments)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 1, если форма фрагментов нарушена."""
    parser = argparse.ArgumentParser(description="Журнал изменений из фрагментов")
    parser.add_argument("--check", action="store_true", help="проверить форму записей")
    parser.add_argument("--preview", action="store_true", help="показать сборку")
    parser.add_argument("--collect", action="store_true", help="перенести в журнал")
    args = parser.parse_args(argv)

    fragments, problems = read_fragments()
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nФорма записи: changelog.d/<slug>.<секция>.md, одна строка внутри. "
            f"Секции: {', '.join(SECTIONS)}.",
            file=sys.stderr,
        )
        return 1

    if args.check or not any((args.preview, args.collect)):
        print(f"фрагментов: {len(fragments)}, замечаний нет")
    if args.preview:
        print(render(fragments) or "(фрагментов нет)")
    if args.collect:
        if not fragments:
            print("переносить нечего")
            return 0
        return collect(fragments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
