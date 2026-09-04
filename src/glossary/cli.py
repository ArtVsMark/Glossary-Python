"""Командный интерфейс ``glossary``.

Реализован на ``argparse`` из стандартной библиотеки: у пакета нет
runtime-зависимостей, поэтому его можно запускать в любом окружении с Python,
в том числе в минимальном CI-контейнере.

Коды возврата:
    0 — успех;
    1 — проверка не пройдена (ошибки валидации или расхождение витрины);
    2 — некорректные аргументы или повреждённые данные.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TextIO

from glossary import __version__
from glossary.errors import GlossaryError
from glossary.exporters import EXPORTERS, get_exporter
from glossary.loader import default_data_path, load_glossary, project_root
from glossary.validation import Severity, ValidationConfig, validate

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["build_parser", "main"]

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_USAGE: Final = 2

DEFAULT_SHOWCASE: Final = "python_glossary.html"

# ``ValidationConfig`` объявлен со ``slots=True``: обращение к полю через класс
# вернуло бы дескриптор слота, а не значение по умолчанию. Берём его с экземпляра.
_DEFAULTS: Final = ValidationConfig()


def build_parser() -> argparse.ArgumentParser:
    """Собрать разбор аргументов со всеми подкомандами."""
    parser = argparse.ArgumentParser(
        prog="glossary",
        description="Валидация, сборка и экспорт глоссария Python.",
    )
    parser.add_argument("--version", action="version", version=f"glossary {__version__}")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="PATH",
        help="путь к файлу данных (по умолчанию data/glossary.json)",
    )

    # Тот же флаг доступен и после подкоманды: `glossary validate --data ...`
    # читается привычнее, чем `glossary --data ... validate`. Значение по
    # умолчанию SUPPRESS не создаёт атрибут, если флаг не указан, — поэтому
    # вариант, записанный до подкоманды, не затирается.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--data",
        type=Path,
        default=argparse.SUPPRESS,
        metavar="PATH",
        help="путь к файлу данных (по умолчанию data/glossary.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True, metavar="КОМАНДА")

    p_validate = sub.add_parser(
        "validate", help="проверить данные по правилам качества", parents=[common]
    )
    p_validate.add_argument(
        "--strict",
        action="store_true",
        help="считать предупреждения ошибками",
    )
    p_validate.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="формат отчёта (по умолчанию text)",
    )
    p_validate.add_argument(
        "--min-description",
        type=int,
        default=_DEFAULTS.min_description,
        metavar="N",
        help="минимальная длина описания в символах",
    )
    p_validate.set_defaults(handler=_cmd_validate)

    p_build = sub.add_parser(
        "build", help="собрать HTML-витрину из данных", parents=[common]
    )
    p_build.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=f"куда записать витрину (по умолчанию {DEFAULT_SHOWCASE} в корне)",
    )
    p_build.add_argument(
        "--check",
        action="store_true",
        help="не записывать файл, а проверить, что он совпадает со сборкой",
    )
    p_build.set_defaults(handler=_cmd_build)

    p_export = sub.add_parser(
        "export", help="экспортировать глоссарий в другой формат", parents=[common]
    )
    p_export.add_argument(
        "-f",
        "--format",
        choices=EXPORTERS,
        required=True,
        help="формат экспорта",
    )
    p_export.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="файл результата (по умолчанию — stdout)",
    )
    p_export.set_defaults(handler=_cmd_export)

    p_stats = sub.add_parser(
        "stats", help="показать статистику по глоссарию", parents=[common]
    )
    p_stats.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="формат вывода (по умолчанию text)",
    )
    p_stats.set_defaults(handler=_cmd_stats)

    return parser


# --------------------------------------------------------------------------- #
# Обработчики команд
# --------------------------------------------------------------------------- #


def _cmd_validate(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    glossary = load_glossary(args.data)
    config = ValidationConfig(min_description=args.min_description)
    report = validate(glossary, config=config)

    if args.format == "json":
        payload = {
            "ok": report.ok,
            "total": len(glossary),
            "issues": [
                {
                    "severity": i.severity.value,
                    "rule": i.rule,
                    "entry_id": i.entry_id,
                    "message": i.message,
                }
                for i in report.issues
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=out)
    else:
        for issue in report.issues:
            stream = err if issue.severity is Severity.ERROR else out
            print(issue.format(), file=stream)
        print(
            f"\nПроверено карточек: {len(glossary)} · "
            f"ошибок: {len(report.errors)} · предупреждений: {len(report.warnings)}",
            file=out,
        )
        if report.issues:
            print("Сводка по правилам:", file=out)
            for rule, count in sorted(report.by_rule().items()):
                print(f"  {count:4d}  {rule}", file=out)

    if report.errors:
        return EXIT_FAILED
    if args.strict and report.warnings:
        print("Режим --strict: предупреждения считаются ошибками.", file=err)
        return EXIT_FAILED
    return EXIT_OK


def _cmd_build(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    glossary = load_glossary(args.data)
    rendered = get_exporter("html").render(glossary)
    target: Path = args.output or (project_root() / DEFAULT_SHOWCASE)

    if args.check:
        if not target.exists():
            print(f"Витрина не найдена: {target}", file=err)
            return EXIT_FAILED
        if target.read_text(encoding="utf-8") == rendered:
            print(f"Витрина актуальна: {target}", file=out)
            return EXIT_OK
        print(
            f"Витрина {target} расходится с данными. "
            "Выполните `glossary build` и закоммитьте результат.",
            file=err,
        )
        return EXIT_FAILED

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print(f"Собрано {len(glossary)} карточек → {target}", file=out)
    return EXIT_OK


def _cmd_export(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    glossary = load_glossary(args.data)
    rendered = get_exporter(args.format).render(glossary)
    if args.output is None:
        out.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Экспортировано {len(glossary)} карточек → {args.output}", file=out)
    return EXIT_OK


def _cmd_stats(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    glossary = load_glossary(args.data)
    stats = glossary.stats()

    if args.format == "json":
        payload = {
            "total": stats.total,
            "groups": dict(stats.groups),
            "color_groups": dict(stats.color_groups),
            "versioned": stats.versioned,
            "avg_description": round(stats.avg_description, 1),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=out)
        return EXIT_OK

    print(f"Карточек:            {stats.total}", file=out)
    print(f"Разделов:            {len(stats.groups)}", file=out)
    print(f"Цветовых групп:      {len(stats.color_groups)}", file=out)
    print(f"С маркером версии:   {stats.versioned}", file=out)
    print(f"Средняя длина опис.: {stats.avg_description:.0f} символов", file=out)
    print("\nРазделы:", file=out)
    for group, count in stats.groups.most_common():
        print(f"  {count:4d}  {group}", file=out)
    return EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Точка входа CLI.

    Потоки вывода передаются параметрами, чтобы тесты могли перехватывать вывод
    без подмены глобального ``sys.stdout``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    stdout = out if out is not None else sys.stdout
    stderr = err if err is not None else sys.stderr

    if getattr(args, "data", None) is None:
        args.data = default_data_path()

    try:
        result: int = args.handler(args, stdout, stderr)
    except GlossaryError as exc:
        print(f"Ошибка: {exc}", file=stderr)
        return EXIT_USAGE
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
