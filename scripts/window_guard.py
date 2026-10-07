#!/usr/bin/env python3
r"""Сторож окна: две формы действия отвергаются ДО вызова инструмента.

Правила каталога 012 и 013 живут в агентском окне, а не в дереве: к моменту
прогона конвейера толчок уже состоялся, а файл уже записан. Поэтому их машинная
половина стоит перед инструментом — хуком ``PreToolUse`` из
``.claude/settings.json``, который отдаёт сюда команду оболочки.

* **012 — в чужую ветку не пушат.** Чья ветка, машине не видно; видно другое:
  имя ветки в команде ``git push`` не совпадает с текущей головой. Промах
  пальцем, строка из прошлой смены, имя соседней задачи дают одно наблюдаемое —
  содержимое уезжает не туда, куда смотрит окно. ``git push`` без имени,
  ``HEAD:<ветка>`` и удаление ссылок не трогаются: там цель названа осознанно.
* **013 — код с экранированием пишут файлом, а не heredoc'ом.** Heredoc без
  кавычек в разделителе раскрывает в теле ``\`` и ``$``: ``\n`` превращается
  в перевод строки, и записанный код ломается молча. Отвергается тело с
  обратной косой чертой под разделителем без кавычек — ``<<'EOF'`` проходит.

ЧЕГО СТОРОЖ НЕ ВИДИТ: намерение. Толчок в чужую ветку под её же текущим именем
(окно переключилось на чужую ветку) — законная форма, и он её пропустит.

Грамматика — младшей версии: хук стартует системным ``python3`` окна, которое
бывает ниже планки проекта, пока ``.venv`` не собран.

Вход: JSON события PreToolUse на stdin. Исходы ``main`` — коды дерева (0 —
пропустить, 1 — отвергнуть с причиной в stderr, 2 — событие не разобрано);
на выходе они переводятся в протокол хука таблицей ``HOOK_CODE``.
"""

import json
import re
import shlex
import subprocess
import sys
from typing import Final

PASSED: Final = 0
REJECTED: Final = 1
NOT_RUN: Final = 2
"""Исходы — кодами дерева, как у остальных гейтов: 2 значит «не отработало»."""

HOOK_CODE: Final = {PASSED: 0, REJECTED: 2, NOT_RUN: 1}
"""Перевод на протокол хука, где 2 — «отвергнуть», а 1 — неблокирующая ошибка.

«Не разобрал» не отвергает: ложный отказ ломает окно, а пропуск оставляет
правило там, где оно было. Но и за «нарушений нет» он себя не выдаёт.
"""

GIT_TIMEOUT: Final = 10

SEPARATORS: Final = re.compile(r"&&|\|\||[;|\n()]")
HEREDOC: Final = re.compile(
    r"<<-?[ \t]*(?P<quote>['\"]?)(?P<word>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)"
)
WITH_VALUE: Final = frozenset(
    {"--repo", "-o", "--push-option", "--exec", "--receive-pack"}
)
GLOBAL_WITH_VALUE: Final = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
)
DELETES: Final = frozenset({"--delete", "-d"})
REDIRECT: Final = re.compile(r"^\d*[<>]")
"""``2>&1``, ``>log``, ``<in`` — перенаправление, а не имя ветки."""
LEADING: Final = frozenset(
    {"do", "then", "else", "if", "while", "until", "!", "time", "{"}
)


def without_heredoc_bodies(command: str) -> str:
    """Команда без тел heredoc: текст внутри них — данные, а не действия."""
    lines = command.split("\n")
    kept: list[str] = []
    ending: list[str] = []
    for line in lines:
        if ending:
            if line.strip() == ending[0]:
                ending.pop(0)
            continue
        kept.append(line)
        ending.extend(match.group("word") for match in HEREDOC.finditer(line))
    return "\n".join(kept)


def unsafe_heredoc(command: str) -> str | None:
    """Разделитель heredoc без кавычек при обратной косой черте в теле (013)."""
    lines = command.split("\n")
    for number, line in enumerate(lines):
        for match in HEREDOC.finditer(line):
            if match.group("quote"):
                continue
            word = match.group("word")
            body: list[str] = []
            for rest in lines[number + 1 :]:
                if rest.strip() == word:
                    break
                body.append(rest)
            if any("\\" in row for row in body):
                return word
    return None


def _git_arguments(words: list[str]) -> list[str] | None:
    """Аргументы подкоманды git без ведущих слов оболочки и глобальных флагов."""
    while words and (words[0] in LEADING or "=" in words[0].split("/")[0]):
        words = words[1:]
    if not words or words[0] != "git":
        return None
    rest = words[1:]
    while rest and rest[0].startswith("-"):
        flag, rest = rest[0], rest[1:]
        if flag in GLOBAL_WITH_VALUE and rest:
            rest = rest[1:]
    return rest


def _positional(args: list[str]) -> list[str]:
    """Позиционные аргументы ``git push``: без флагов и перенаправлений."""
    positional: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in WITH_VALUE:
            skip = True
        elif not arg.startswith("-") and not REDIRECT.match(arg):
            positional.append(arg)
    return positional


def push_targets(command: str) -> list[str]:
    """Имена веток, которые команды ``git push`` называют явно."""
    targets: list[str] = []
    for chunk in SEPARATORS.split(without_heredoc_bodies(command)):
        try:
            words = shlex.split(chunk)
        except ValueError:
            continue
        rest = _git_arguments(words)
        if not rest or rest[0] != "push" or DELETES & set(rest):
            continue
        # Первый позиционный — удалённый репозиторий, дальше refspec'и.
        for refspec in _positional(rest[1:])[1:]:
            source, _, destination = refspec.lstrip("+").partition(":")
            if refspec.startswith(":") or source == "HEAD":
                continue
            targets.append((destination or source).removeprefix("refs/heads/"))
    return targets


def current_branch() -> str | None:
    """Текущая голова окна; ``None`` — git не ответил или голова отделена."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607 — git ищется в PATH
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except OSError:
        return None
    except subprocess.TimeoutExpired:
        return None
    name = done.stdout.strip()
    return name if done.returncode == 0 and name != "HEAD" else None


def verdict(command: str, branch: str | None) -> str | None:
    """Причина отказа или ``None``, если команда проходит."""
    word = unsafe_heredoc(command)
    if word is not None:
        return (
            f"heredoc <<{word} без кавычек раскроет в теле «\\» и «$»: код с "
            f"экранированием пишут файлом или под <<'{word}' (правило каталога 013)"
        )
    if branch is None:
        return None
    foreign = [target for target in push_targets(command) if target != branch]
    if foreign:
        return (
            f"толчок в {foreign[0]!r}, а окно стоит на {branch!r}: в чужую ветку не "
            "пушат — переключитесь на неё или толкните текущую (правило каталога 012)"
        )
    return None


def _not_run(why: str) -> int:
    """Назвать, почему сторож не смотрел, и пропустить команду."""
    print(f"сторож окна не разобрал событие: {why}", file=sys.stderr)
    return NOT_RUN


def main(stdin: str) -> int:
    """Точка входа хука: событие PreToolUse на входе, исход — код возврата."""
    try:
        event = json.loads(stdin)
        command = event["tool_input"]["command"]
    except ValueError:
        return _not_run("событие не JSON")
    except LookupError:
        return _not_run("в событии нет tool_input.command")
    except TypeError:
        return _not_run("событие не объект")
    if not isinstance(command, str):
        return _not_run("команда не строка")
    needs_branch = "push" in command
    reason = verdict(command, current_branch() if needs_branch else None)
    if reason is None:
        return PASSED
    print(reason, file=sys.stderr)
    return REJECTED


if __name__ == "__main__":
    sys.exit(HOOK_CODE[main(sys.stdin.read())])
