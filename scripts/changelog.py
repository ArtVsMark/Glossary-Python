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
    python scripts/changelog.py --rotate    # вынести старые выпуски в архив

Окно (правило каталога 108). Журнал держит ``WINDOW`` последних выпусков;
что старше, переезжает в ``docs/changelog-archive.md`` **дословно**. Перенос
делает ``--rotate``, а не рука: машина не сокращает и не пересказывает, поэтому
дословность держится построением, а не вниманием. Предел держит ``--check``.
"""

import argparse
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «замечаний нет» — их не искали."""


class NotRunError(RuntimeError):
    """Смотреть негде: предмета проверки не существует (правила 039, 075)."""


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

ARCHIVE: Final = ROOT / "docs" / "changelog-archive.md"

WINDOW: Final = 3
"""Сколько выпусков живёт в журнале. Число — как у соседа: три последних MINOR."""

ARCHIVE_HEAD: Final = (
    "# Архив журнала изменений\n\n"
    "Выпуски, вышедшие за окно `CHANGELOG.md`, — дословно, новые сверху. "
    "Переносит их `python scripts/changelog.py --rotate`, руками сюда не пишут.\n"
)

UNRELEASED: Final = "## [Unreleased]"
SECTION: Final = re.compile(r"^## ", re.MULTILINE)
VERSION: Final = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\]", re.MULTILINE)
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
        # Не находка, а третий исход: смотреть негде. Возвращать это замечанием
        # значило бы сказать «форма нарушена» там, где формы нет вовсе.
        raise NotRunError(
            f"каталога {FRAGMENTS} нет — класть записи некуда и проверять нечего"
        )

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


def split_sections(text: str) -> tuple[str, list[str]]:
    """Разрезать документ на шапку и разделы второго уровня, ничего не теряя."""
    starts = [match.start() for match in SECTION.finditer(text)]
    if not starts:
        return text, []
    bounds = itertools.pairwise([*starts, len(text)])
    return text[: starts[0]], [text[a:b] for a, b in bounds]


def versions(text: str) -> list[str]:
    """Версии выпусков, названные заголовками разделов, сверху вниз."""
    return [match.group("version") for match in VERSION.finditer(text)]


def window_problems(changelog: str, archive: str, window: int = WINDOW) -> list[str]:
    """Замечания к окну журнала: лишние выпуски и выпуск в двух местах сразу."""
    problems: list[str] = []
    kept = versions(changelog)
    if len(kept) > window:
        problems.append(
            f"CHANGELOG.md держит выпусков {len(kept)} при окне {window}: "
            f"{', '.join(kept[window:])} — в архив командой "
            "python scripts/changelog.py --rotate"
        )
    twice = sorted(set(kept) & set(versions(archive)))
    if twice:
        problems.append(
            f"выпуск и в журнале, и в архиве: {', '.join(twice)} — у раздела одно место"
        )
    return problems


def rotate(changelog: str, archive: str, window: int = WINDOW) -> tuple[str, str]:
    """Вынести всё, что ниже ``window``-го выпуска, в архив дословно.

    Вместе с выпусками уезжает и то, что лежит под ними (например, «Ранняя
    история»): оно старше любого выпуска в окне.

    Returns:
        Новые тексты журнала и архива; без лишних выпусков — прежние.
    """
    head, sections = split_sections(changelog)
    releases = [i for i, section in enumerate(sections) if VERSION.match(section)]
    if len(releases) <= window:
        return changelog, archive
    border = releases[window]
    kept, moved = sections[:border], sections[border:]
    archive_head, archived = split_sections(archive or ARCHIVE_HEAD)
    # Разделы расходятся пустой строкой; последний раздел файла её не несёт.
    moved_text = "".join(moved).rstrip("\n") + "\n"
    if archived:
        moved_text += "\n"
    archive_head = archive_head.rstrip("\n") + "\n\n"
    new_changelog = (head + "".join(kept)).rstrip("\n") + "\n"
    return new_changelog, archive_head + moved_text + "".join(archived)


def _read(path: Path) -> str:
    """Текст файла; отсутствующий архив — пустой, а не ошибка: его ещё не было."""
    return path.read_text("utf-8") if path.exists() else ""


def check_window() -> list[str]:
    """Окно живого журнала против его архива."""
    if not CHANGELOG.exists():
        raise NotRunError(f"журнала {CHANGELOG} нет — окно мерить не у чего")
    return window_problems(_read(CHANGELOG), _read(ARCHIVE))


def run_rotation() -> int:
    """Вынести выпуски за окном в архив и назвать, что уехало."""
    changelog, archive = _read(CHANGELOG), _read(ARCHIVE)
    new_changelog, new_archive = rotate(changelog, archive)
    if new_changelog == changelog:
        print(f"выпусков в окне не больше {WINDOW} — переносить нечего")
        return 0
    moved = [v for v in versions(changelog) if v not in versions(new_changelog)]
    CHANGELOG.write_text(new_changelog, encoding="utf-8")
    ARCHIVE.write_text(new_archive, encoding="utf-8")
    print(f"в архив уехали выпуски: {', '.join(moved)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 1, если форма фрагментов нарушена."""
    parser = argparse.ArgumentParser(description="Журнал изменений из фрагментов")
    parser.add_argument("--check", action="store_true", help="проверить форму записей")
    parser.add_argument("--preview", action="store_true", help="показать сборку")
    parser.add_argument("--collect", action="store_true", help="перенести в журнал")
    parser.add_argument("--rotate", action="store_true", help="старые выпуски — в архив")
    args = parser.parse_args(argv)

    if args.rotate:
        return run_rotation()
    try:
        fragments, problems = read_fragments()
        if args.check or not any((args.preview, args.collect)):
            problems += check_window()
    except NotRunError as refusal:
        print(f"проверка не отработала: {refusal}", file=sys.stderr)
        return NOT_RUN
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
