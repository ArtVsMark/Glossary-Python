#!/usr/bin/env python3
"""Красный прогон по расписанию доходит до человека задачей (правило 142).

ЗАЧЕМ. Прогоны по расписанию — CI раз в сутки, значки и факты, входящие
каталога — не прикреплены ни к какому изменению. Их красное видно только на
вкладке прогонов, а туда никто не ходит: такая проверка отличается от
незапущенной лишь счётом за машинное время. Замер, с которого начался
python-next (#154), — две недели красного, которых не заметил никто.

КАК. Прогон ``schedule-alarm.yml`` будится завершением сторожимых прогонов и,
если тот запускался по расписанию, сводит его исход с задачей-тревогой — той
же логикой, что у python-next (``scripts/next_alarm.py``): одна задача на
прогон, найденная по меткам; красное заводит её, повторное красное молчит,
зелёное закрывает. Отменённый или пропущенный прогон ответа не дал — третий
исход, площадку не трогает.

Метка прогона — по имени файла, а не по ``name``: имя прогона значков содержит
запятые, а запятая в запросе списка задач разделяет метки.

Исходы: 0 — тревога сведена с прогоном; 2 — не отработало.
"""

import argparse
import sys
from pathlib import PurePosixPath
from typing import Final

from automerge import NotRunError
from next_alarm import reconcile_alarm

NOT_RUN: Final = 2

LABEL: Final = "schedule-alarm"
"""Общая метка тревог по расписанию: по ней их видно все разом."""

VERDICTS: Final = {"success": "success", "failure": "failure", "timed_out": "failure"}
"""Исход площадки → ответ о прогоне; прочие исходы ответа не дают."""


def workflow_label(path: str) -> str:
    """Метка прогона по его файлу: ``.github/workflows/ci.yml`` → ``расписание: ci``."""
    return f"расписание: {PurePosixPath(path).stem}"


def text(name: str, run_url: str) -> str:
    """Тело новой задачи."""
    return (
        f"Прогон «{name}» по расписанию красный: {run_url}\n\n"
        "Прогон по расписанию не прикреплён к изменению, и его красное иначе "
        "видно только на вкладке прогонов, куда не ходит никто (правило "
        "каталога 142).\n\n"
        "Что делать: открыть прогон, найти упавший шаг и починить — либо "
        "назвать здесь, почему ждать. Задача закроется сама, когда прогон по "
        "расписанию позеленеет.\n\n"
        "Завёл `scripts/schedule_alarm.py`."
    )


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="имя прогона")
    parser.add_argument("--path", required=True, help="файл прогона")
    parser.add_argument("--conclusion", required=True, help="исход по площадке")
    parser.add_argument("--run-url", required=True, help="адрес прогона")
    args = parser.parse_args(argv)

    outcome = VERDICTS.get(args.conclusion)
    if outcome is None:
        print(
            f"не отработало: исход «{args.conclusion}» прогона «{args.name}» "
            "ответа не даёт — ни тревоги, ни отбоя",
            file=sys.stderr,
        )
        return NOT_RUN
    try:
        print(
            reconcile_alarm(
                outcome,
                labels=(LABEL, workflow_label(args.path)),
                title=f"Прогон по расписанию «{args.name}» красный",
                text=text(args.name, args.run_url),
                closing=f"Прогон «{args.name}» по расписанию позеленел: {args.run_url}",
            )
        )
    except NotRunError as error:
        print(f"не отработало: {error}", file=sys.stderr)
        return NOT_RUN
    return 0


if __name__ == "__main__":
    sys.exit(main())
