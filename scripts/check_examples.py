#!/usr/bin/env python3
"""Пример карточки исполняется — или его падение названо в самом примере.

Правило ``example-compiles`` проверяет разбор, а не поведение: пример с
``Pt(1, 2)`` до определения ``Pt`` компилируется и падает при первом же запуске
у учащегося. С #76 карточки наши, и поведение примера — тоже наша забота (#82).

Исход примера — один из четырёх:

* **исполнился** — код возврата ноль;
* **намеренно** — упал на строке, комментарий которой называет поднятое
  исключение или его базовый класс: ``print(b'a' + 'b')   # → TypeError``.
  Так карточки показывают ловушку, и это соглашение уже живёт в данных;
* **окружение** — упал (или не уложился в срок) на строке с пометкой ``→ ?``:
  результат зависит от платформы, прав или терминала, и карточка это говорит;
* **находка** — всё остальное.

Пример исполняется файлом, а не через ``-c``: ``multiprocessing`` в режимах
``spawn`` и ``forkserver`` (умолчание Linux с Python 3.14) заново импортирует
``__main__`` по пути, и пример с ``if __name__ == "__main__":`` должен работать
так же, как у учащегося.

ИЗОЛЯЦИЯ. Каждый пример — в своём временном каталоге, с пустым окружением,
``stdin`` из ``/dev/null``, в отдельной сессии процессов и со сроком. Сигналы,
которые примеры шлют группе своего процесса, до проверяющего не доходят.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **верность вывода.** Комментарий ``# → 2.5`` гейт не сверяет с напечатанным:
  он видит падение, а не значение;
* **пометку ``→ ?`` не по делу.** Строка, помеченная зависящей от окружения,
  освобождена от требования — гейт не судит, честна ли пометка;
* **сеть.** Пример, ходящий в сеть, падает в изолированном прогоне и
  становится находкой — так и задумано: в примере для учащегося сети нет.

Запуск::

    python scripts/check_examples.py              # гейт по data/glossary.json
    python scripts/check_examples.py --data FILE  # то же по другому файлу

Исходы: 0 — находок нет; 1 — есть находки; 2 — проверка не отработала.
"""

import argparse
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

ROOT: Final = Path(__file__).resolve().parent.parent
DATA: Final = "data/glossary.json"

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «находок нет» — примеры не исполняли."""

TIMEOUT: Final = 10.0
"""Срок одного примера в секундах. Пример для учащегося мгновенен; дольше —
значит ждёт ввода, сети или терминала."""

WORKERS: Final = 8
"""Сколько примеров исполняется одновременно: каждый — отдельный процесс."""

ENVIRONMENT_MARK: Final = "→ ?"
"""Пометка строки, чей результат зависит от платформы, прав или терминала."""

FILENAME: Final = "example.py"
FRAME: Final = re.compile(r'^  File "(?P<file>[^"]+)", line (?P<line>\d+)', re.MULTILINE)
EXCEPTION_LINE: Final = re.compile(r"^(?P<name>[A-Za-z_][\w.]*)(?::|$)")
NAME: Final = re.compile(r"[A-Za-z_][\w.]*")

Outcome = Literal["ok", "intended", "environment", "finding"]


@dataclass(frozen=True, slots=True)
class Result:
    """Исход одного примера."""

    entry_id: str
    outcome: Outcome
    detail: str = ""


def comments(code: str) -> dict[int, str]:
    """Комментарий каждой строки примера по номеру строки.

    Разбор токенами, а не поиском ``#``: решётка внутри строки — не комментарий.
    Непарсящийся пример даёт пустой словарь: его судит ``example-compiles``.
    """
    found: dict[int, str] = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.COMMENT:
                found[token.start[0]] = token.string
    except tokenize.TokenError, IndentationError, SyntaxError:
        return {}
    return found


def lineage(name: str) -> set[str]:
    """Имена исключения и всех его базовых классов, коротко и полностью.

    Имя из трассировки разрешается в класс импортом; не разрешилось (класс
    объявлен в самом примере) — остаётся само имя.
    """
    module, _, attr = name.rpartition(".")
    obj: object = None
    try:
        obj = getattr(importlib.import_module(module or "builtins"), attr)
    except ImportError, AttributeError, ValueError:
        obj = None
    if isinstance(obj, type):
        names = {cls.__name__ for cls in obj.__mro__}
        names |= {f"{cls.__module__}.{cls.__qualname__}" for cls in obj.__mro__}
        return names
    return {name, attr}


def failure(stderr: str, path: str) -> tuple[int, str]:
    """Строка примера, на которой он упал, и имя исключения.

    Строка — последний кадр трассировки в файле примера; имя — первая строка
    после кадров, похожая на ``Имя: сообщение``. Сообщение бывает многострочным,
    поэтому последняя строка вывода именем не считается.
    """
    frames = [m for m in FRAME.finditer(stderr) if m.group("file").endswith(path)]
    line = int(frames[-1].group("line")) if frames else 0
    tail = stderr[frames[-1].end() :] if frames else stderr
    for text in tail.splitlines():
        if text.startswith(" ") or not text:
            continue
        match = EXCEPTION_LINE.match(text)
        if match:
            return line, match.group("name")
    return line, ""


def classify(entry_id: str, code: str, stderr: str, timed_out: bool) -> Result:
    """Отнести неудачный запуск к одному из исходов."""
    remarks = comments(code)
    if timed_out:
        if ENVIRONMENT_MARK in code:
            return Result(entry_id, "environment", "не уложился в срок")
        return Result(entry_id, "finding", f"не уложился в {TIMEOUT:.0f} с")
    line, name = failure(stderr, FILENAME)
    remark = remarks.get(line, "")
    if ENVIRONMENT_MARK in remark:
        return Result(entry_id, "environment", f"строка {line}: {name}")
    named = {token.rsplit(".", 1)[-1] for token in NAME.findall(remark)}
    named |= set(NAME.findall(remark))
    if name and named & lineage(name):
        return Result(entry_id, "intended", f"строка {line}: {name}")
    where = f"строка {line}" if line else "вне кода примера"
    return Result(entry_id, "finding", f"{where}: {name or 'ненулевой код возврата'}")


def execute(entry_id: str, code: str) -> Result:
    """Исполнить пример в изоляции и отнести исход."""
    with tempfile.TemporaryDirectory(prefix="example-") as tmp:
        path = Path(tmp) / FILENAME
        path.write_text(code, encoding="utf-8")
        env = {"PATH": os.defpath, "HOME": tmp, "LANG": "C.UTF-8", "TZ": "UTC"}
        try:
            # Код примера — наш собственный, из data/cards/, а не чужой ввод;
            # исполняется изолированно — ради этого гейт и заведён.
            done = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-X", "utf8", FILENAME],
                cwd=tmp,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
                start_new_session=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return classify(entry_id, code, "", timed_out=True)
    if done.returncode == 0:
        return Result(entry_id, "ok")
    return classify(entry_id, code, done.stderr, timed_out=False)


def examples(data: Path) -> dict[str, str]:
    """Примеры карточек из собранного глоссария: ``id`` → код."""
    payload = json.loads(data.read_text(encoding="utf-8"))
    return {
        entry["id"]: "\n".join(entry["examples"]) + "\n"
        for entry in payload["entries"]
        if entry.get("examples")
    }


def check(codes: dict[str, str]) -> list[Result]:
    """Исполнить все примеры; порядок результата — порядок карточек."""
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(lambda item: execute(*item), codes.items()))


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / DATA)
    args = parser.parse_args(argv)

    if not args.data.exists():
        print(f"проверка не отработала: файла {args.data} нет", file=sys.stderr)
        return NOT_RUN
    codes = examples(args.data)
    if not codes:
        print(
            f"проверка не отработала: в {args.data} нет ни одного примера — "
            "исполнять нечего",
            file=sys.stderr,
        )
        return NOT_RUN

    results = check(codes)
    tally = dict.fromkeys(("ok", "intended", "environment", "finding"), 0)
    for result in results:
        tally[result.outcome] += 1
    found = [r for r in results if r.outcome == "finding"]
    summary = (
        f"примеров: {len(results)} · исполнились: {tally['ok']} · "
        f"намеренно: {tally['intended']} · окружение: {tally['environment']} · "
        f"находок: {tally['finding']}"
    )
    if found:
        print("пример падает не там, где обещает:", file=sys.stderr)
        for result in found:
            print(f"  • {result.entry_id}: {result.detail}", file=sys.stderr)
        print(summary, file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
