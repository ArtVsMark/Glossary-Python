#!/usr/bin/env python3
"""Красный прогон предварительной версии Python будит человека задачей.

ЗАЧЕМ (Glossary-Python#154). ``python-next.yml`` проверяет проект на следующей
версии Python и красен с 05.10 — этого не заметил никто. Его цвет виден только
значком, а значок не будит: его надо пойти и посмотреть. Задача будит —
площадка присылает о ней уведомление владельцу.

КАК. Задача одна, её опознают по метке ``python-next``:

* прогон красный, открытой задачи нет — завести её со ссылкой на прогон;
* прогон красный, задача уже открыта — молчать: тревога уже поднята, а
  ежедневный комментарий «всё ещё красное» стал бы шумом, который перестают
  читать;
* прогон зелёный, задача открыта — отписаться ссылкой на прогон и закрыть;
* прогон зелёный, задачи нет — молчать.

Отменённый или пропущенный прогон ответа о версии не дал — это третий исход,
а не «зелёное» и не «красное» (правило каталога 039).

Транспорт — REST тем же вызовом, что у ``scripts/automerge.py``: реализация
обращения к площадке в дереве одна.

Исходы: 0 — состояние задачи сведено с прогоном; 2 — не отработало.
"""

import argparse
import sys
import urllib.parse
from typing import Final, Literal

from automerge import REPOSITORY, REST, NotRunError, _call, _object

LABEL: Final = "python-next"
"""Метка, по которой задача-тревога находится среди остальных."""

NOT_RUN: Final = 2

OUTCOMES: Final = ("success", "failure", "cancelled", "skipped")
"""Исходы работы, как их называет ``needs.<работа>.result``."""

Action = Literal["open", "close", "keep", "none"]


def decide(outcome: str, alarm: int | None) -> Action:
    """Что сделать с задачей-тревогой.

    Args:
        outcome: Исход прогона: ``success`` или ``failure``.
        alarm: Номер открытой задачи; ``None`` — открытой нет.

    Returns:
        ``open`` — завести, ``close`` — закрыть, ``keep`` — тревога уже
        поднята, ``none`` — делать нечего.
    """
    if outcome == "failure":
        return "keep" if alarm is not None else "open"
    return "close" if alarm is not None else "none"


def open_alarm(labels: tuple[str, ...] = (LABEL,)) -> int | None:
    """Номер открытой задачи-тревоги с этими метками; ``None`` — её нет."""
    # Предел намеренный — одна запись (правило 212): вопрос «поднята ли тревога»,
    # и ответ на него даёт первая же открытая задача с меткой.
    query = urllib.parse.quote(",".join(labels), safe=",")
    url = f"{REST}/repos/{REPOSITORY}/issues?labels={query}&state=open&per_page=1"
    found = _call(url)
    if not isinstance(found, list):
        raise NotRunError(f"{url} ответил объектом там, где ждали список")
    return int(found[0]["number"]) if found else None


def undelivered(sent: dict[str, object], published: dict[str, object]) -> list[str]:
    """Чем опубликованная задача разошлась с отправленной (правило 188).

    Код 201 доказывает приём запроса, а не то, что задача годится в тревогу.
    Главное — метка: задачу без неё следующий прогон не найдёт и заведёт
    вторую, и так каждый день.

    Args:
        sent: Отправленные поля задачи.
        published: Задача, перечитанная у площадки.

    Returns:
        Расхождения словами; пусто — дошло как отправлено.
    """
    problems: list[str] = []
    labels = published.get("labels")
    names = {
        str(label.get("name")) if isinstance(label, dict) else str(label)
        for label in (labels if isinstance(labels, list) else [])
    }
    wanted = sent.get("labels")
    problems.extend(
        f"метки {label} нет — следующий прогон тревогу не найдёт и заведёт вторую"
        for label in (wanted if isinstance(wanted, list) else [])
        if str(label) not in names
    )
    problems.extend(
        f"поле {field} опубликовано не тем, что отправлено"
        for field in ("title", "body")
        if published.get(field) != sent[field]
    )
    return problems


def body(version: str, run_url: str) -> str:
    """Текст новой задачи."""
    return (
        f"Прогон `python-next.yml` на Python {version} красный: {run_url}\n\n"
        "Это не дефект изменения — прогон слияния не держит. Это ответ на "
        f"вопрос «заработает ли проект на {version}», и сейчас он «нет».\n\n"
        "Что делать: открыть прогон, найти упавший шаг и решить — чинить "
        "код или карточку, либо назвать причину ждать выхода версии. "
        "Задача закроется сама, когда прогон позеленеет.\n\n"
        "Завёл `scripts/next_alarm.py` (#154)."
    )


def reconcile(outcome: str, version: str, run_url: str) -> str:
    """Свести задачу-тревогу python-next с исходом прогона.

    Args:
        outcome: Исход прогона: ``success`` или ``failure``.
        version: Проверяемая версия Python.
        run_url: Адрес прогона.

    Returns:
        Что сделано, словами.

    Raises:
        NotRunError: Обращение к площадке не состоялось.
    """
    return reconcile_alarm(
        outcome,
        labels=(LABEL,),
        title=f"Python {version}: прогон python-next красный",
        text=body(version, run_url),
        closing=f"Прогон на Python {version} позеленел: {run_url}",
    )


def reconcile_alarm(
    outcome: str, *, labels: tuple[str, ...], title: str, text: str, closing: str
) -> str:
    """Свести задачу-тревогу, найденную по меткам, с исходом прогона.

    Одна логика на все тревоги проекта: python-next и прогоны по расписанию
    (``scripts/schedule_alarm.py``) отличаются только метками и текстом.

    Args:
        outcome: Исход прогона: ``success`` или ``failure``.
        labels: Метки, по которым тревога находится.
        title: Заголовок новой задачи.
        text: Тело новой задачи.
        closing: Комментарий при закрытии.

    Returns:
        Что сделано, словами.

    Raises:
        NotRunError: Обращение к площадке не состоялось.
    """
    alarm = open_alarm(labels)
    action = decide(outcome, alarm)
    issues = f"{REST}/repos/{REPOSITORY}/issues"
    if action == "open":
        sent: dict[str, object] = {"title": title, "body": text, "labels": list(labels)}
        number = _object(_call(issues, sent), issues)["number"]
        # Перечитывается то, что лежит у площадки, а не ответ на запрос (188).
        published = _object(_call(f"{issues}/{number}"), f"{issues}/{number}")
        problems = undelivered(sent, published)
        if problems:
            raise NotRunError(
                f"задача #{number} заведена, но тревогой не годится: "
                + "; ".join(problems)
            )
        return f"заведена задача #{number}"
    if action == "close":
        _call(
            f"{issues}/{alarm}/comments",
            {"body": closing},
        )
        _call(f"{issues}/{alarm}", {"state": "closed"}, method="PATCH")
        state = _object(_call(f"{issues}/{alarm}"), f"{issues}/{alarm}").get("state")
        if state != "closed":
            raise NotRunError(f"задача #{alarm} после закрытия в состоянии {state!r}")
        return f"задача #{alarm} закрыта: прогон зелёный"
    if action == "keep":
        return f"тревога уже поднята задачей #{alarm} — молчу"
    return "прогон зелёный, тревоги нет"


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outcome", required=True, choices=OUTCOMES)
    parser.add_argument("--version", required=True, help="проверяемая версия")
    parser.add_argument("--run-url", required=True, help="адрес прогона")
    args = parser.parse_args(argv)

    if args.outcome not in ("success", "failure"):
        print(
            f"не отработало: исход прогона «{args.outcome}» ответа о Python "
            f"{args.version} не даёт — ни тревоги, ни отбоя",
            file=sys.stderr,
        )
        return NOT_RUN
    try:
        print(reconcile(args.outcome, args.version, args.run_url))
    except NotRunError as error:
        print(f"не отработало: {error}", file=sys.stderr)
        return NOT_RUN
    return 0


if __name__ == "__main__":
    sys.exit(main())
