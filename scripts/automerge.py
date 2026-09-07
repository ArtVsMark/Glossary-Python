#!/usr/bin/env python3
"""Поставить изменение в очередь слияния площадки. Один вызов GraphQL, и он назван.

ТРАНСПОРТ — REST, И ИСКЛЮЧЕНИЕ ОДНО. Правило каталога 001 требует REST по
умолчанию: одна операция GraphQL стоит около трёхсот единиц часовой квоты
против одной у REST, а счётчик считает попытки, а не успехи. Оно же называет
закрытый список операций, у которых REST-эквивалента **нет вовсе**, и включение
авто-мержа стоит в списке первым — мутация ``enablePullRequestAutoMerge``.

Поэтому здесь ровно два обращения, и они разные:

* **REST** читает изменение и берёт его ``node_id`` — это обычный ``GET``,
  и делать его через GraphQL значило бы платить триста за единицу;
* **GraphQL** вызывается один раз и только ради мутации, у которой нет REST.

Форма списка исключений держится ``tests/test_automerge.py``: обращений к
GraphQL в дереве ровно одно, и оно названо в CLAUDE.md, разделе «Работа с
GitHub».

ПОЧЕМУ РОДНОЙ АВТОМЕРЖ, А НЕ СВОЯ ОЧЕРЕДЬ. Единообразие с соседними проектами:
у `Engineering-Incidents-Playbook` это сделано так же и той же мутацией. Своя
очередь на REST здесь была написана и отвергнута — она давала два лишних
свойства (не сливать на красную общую ветку, печатать остаток квоты) ценой
четырёхсот строк своего кода и второго механизма на ту же работу.

ЧТО ЭТОТ СКРИПТ НЕ ДЕЛАЕТ. Он не сливает и не ждёт. Он ставит изменение в
очередь площадки и выходит; сливает площадка, когда обязательные проверки
позеленели и конфликта нет. Ни повторов, ни опроса, ни расхода квоты на
ожидание.

ГРАНИЦА, КОТОРУЮ НЕ ЗАКРЫТЬ ОТСЮДА. Настройка репозитория «Allow auto-merge»
живёт вне дерева, и у ``GITHUB_TOKEN`` нет прав её включить. Пока она
выключена, мутация отвечает отказом — и он печатается словами, а не молчит.

Исходы: 0 — поставлено в очередь; 1 — площадка отказала; 2 — не отработало.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Final

REST: Final = "https://api.github.com"
GRAPHQL: Final = "https://api.github.com/graphql"
REPOSITORY: Final = os.environ.get("GITHUB_REPOSITORY", "ArtVsMark/Glossary-Python")
TOKEN_VARIABLES: Final = ("GITHUB_TOKEN", "GH_TOKEN")

MERGE_METHOD: Final = "MERGE"
"""Объединяющий коммит — тем же способом, каким ведётся история репозитория."""

TIMEOUT: Final = 30
"""Дедлайн на запрос: зависнуть можно до первой строки ответа (правило 100)."""

MUTATION: Final = """
mutation($pullRequestId: ID!, $method: PullRequestMergeMethod!) {
  enablePullRequestAutoMerge(
    input: {pullRequestId: $pullRequestId, mergeMethod: $method}
  ) {
    pullRequest { number autoMergeRequest { enabledAt } }
  }
}
"""
"""Единственная мутация репозитория. REST-эквивалента у неё нет (правило 001)."""


class RefusedError(RuntimeError):
    """Площадка отказала: находка с названным предметом, а не поломка."""


class NotRunError(RuntimeError):
    """Обращение не состоялось: третий исход (правило 039)."""


def _token() -> str:
    """Токен из окружения.

    Returns:
        Значение первой найденной переменной.

    Raises:
        NotRunError: Ни одна переменная не задана — предмет назван поимённо.
    """
    for name in TOKEN_VARIABLES:
        value = os.environ.get(name)
        if value:
            return value
    raise NotRunError(
        f"нет токена: ни одна из переменных {', '.join(TOKEN_VARIABLES)} не "
        "задана — обращаться к площадке нечем"
    )


def _call(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Один запрос к площадке.

    Args:
        url: Полный адрес.
        payload: Тело; ``None`` — обычное чтение.

    Returns:
        Разобранный ответ.

    Raises:
        NotRunError: Обращение не состоялось.
    """
    request = urllib.request.Request(  # noqa: S310 — адрес собран из констант
        url,
        method="GET" if payload is None else "POST",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            # Диагностика начинается с ФАКТА о квоте, а не с гипотезы о причинах
            # (правило 017): остаток печатается у каждого ответа, и запрос его
            # ничего не стоит — он приходит заголовком вместе с ответом.
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                limit = response.headers.get("x-ratelimit-limit")
                print(f"  квота: осталось {remaining} из {limit} ({url})")
            answer: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return answer
    except urllib.error.HTTPError as error:
        raise NotRunError(
            f"{url} отвергнут площадкой: {error.code} {error.reason}"
        ) from error
    except OSError as error:
        raise NotRunError(f"{url} не состоялся: {error}") from error


def node_id(number: int) -> str:
    """Идентификатор изменения — обычным чтением по REST.

    Читать его мутацией было бы платой в триста единиц квоты за то, что REST
    отдаёт за одну (правило 001).

    Args:
        number: Номер изменения.

    Returns:
        Идентификатор узла.

    Raises:
        NotRunError: Ответ не содержит идентификатора.
    """
    answer = _call(f"{REST}/repos/{REPOSITORY}/pulls/{number}")
    identifier = answer.get("node_id")
    if not identifier:
        raise NotRunError(f"у изменения #{number} нет node_id — форма ответа изменилась")
    return str(identifier)


def refusal(answer: dict[str, Any]) -> str | None:
    """Отказ, спрятанный в успешном ответе GraphQL; ``None`` — отказа нет.

    GraphQL отвечает кодом 200 и кладёт отказ в поле ``errors``. Читать только
    код состояния значило бы считать отказ успехом — ровно тот случай, ради
    которого у проверки заводится третий исход (правило 039).

    Args:
        answer: Разобранный ответ.

    Returns:
        Сообщение об отказе либо ``None``.
    """
    errors = answer.get("errors")
    if not errors:
        return None
    return "; ".join(str(error.get("message", error)) for error in errors)


def arm(number: int) -> str:
    """Поставить изменение в очередь площадки.

    Args:
        number: Номер изменения.

    Returns:
        Отметка времени постановки в очередь.

    Raises:
        RefusedError: Площадка отказала — например, автомерж выключен в настройках.
        NotRunError: Обращение не состоялось.
    """
    answer = _call(
        GRAPHQL,
        {
            "query": MUTATION,
            "variables": {"pullRequestId": node_id(number), "method": MERGE_METHOD},
        },
    )
    message = refusal(answer)
    if message is not None:
        raise RefusedError(
            f"#{number} в очередь не поставлено: {message}. Чаще всего это "
            "выключенная настройка репозитория «Allow auto-merge» — включить "
            "её из прогона нельзя, у GITHUB_TOKEN нет прав на настройки"
        )
    request = (
        answer.get("data", {}).get("enablePullRequestAutoMerge", {}).get("pullRequest")
    )
    enabled = (request or {}).get("autoMergeRequest", {}).get("enabledAt")
    return str(enabled or "без отметки времени")


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("number", type=int, help="номер изменения")
    args = parser.parse_args(argv)

    try:
        enabled = arm(args.number)
    except RefusedError as error:
        print(str(error), file=sys.stderr)
        return 1
    except NotRunError as error:
        print(f"не отработало: {error}", file=sys.stderr)
        return 2

    print(f"#{args.number} поставлено в очередь площадки: {enabled}")
    print("сливает площадка, когда обязательные проверки позеленели")
    return 0


if __name__ == "__main__":
    sys.exit(main())
