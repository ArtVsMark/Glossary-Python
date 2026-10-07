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

Исполнившийся пример сверяется ещё и с обещанным выводом (#125): комментарий
``# → …`` на строке с ``print`` или с вызовом функции, определённой в примере
(или отдельной строкой под такой строкой), называет, что будет напечатано,
и не напечатанное обещание — исход **вывод расходится**.
Склейка примеров прятала именно это: вызов, уехавший в тело чужой функции или
ветки ``else``, не падал, а просто молчал. Такие исходы считаются против
потолка ``OUTPUT_CEILING``, который движется только вниз.

Пример исполняется файлом, а не через ``-c``: ``multiprocessing`` в режимах
``spawn`` и ``forkserver`` (умолчание Linux с Python 3.14) заново импортирует
``__main__`` по пути, и пример с ``if __name__ == "__main__":`` должен работать
так же, как у учащегося.

ИЗОЛЯЦИЯ. Каждый пример — в своём временном каталоге, с пустым окружением,
``stdin`` из ``/dev/null``, в отдельной сессии процессов и со сроком. Сигналы,
которые примеры шлют группе своего процесса, до проверяющего не доходят.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **значение без печати.** ``x = 5 / 2  # → 2.5`` гейт не сверяет: строка
  ничего не печатает, а вычислять выражение ради сверки — уже интерпретатор;
* **словесное обещание.** ``# → большое число`` — пояснение, а не вывод: обещание
  с кириллицей, не найденное в выводе, гейт пропускает молча. Сверяется запись
  вывода: числа, списки, строки латиницей;
* **порядок.** Обещание найдено где-то в выводе блока — гейт не проверяет, что
  его напечатала именно эта строка;
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
import ast
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
FRAME: Final = re.compile(
    r'^  File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<scope>\S+))?', re.MULTILINE
)
MODULE_SCOPE: Final = "<module>"
"""Кадр верхнего уровня примера: пометку ставят на строку, которую видит читатель."""
EXCEPTION_LINE: Final = re.compile(r"^(?P<name>[A-Za-z_][\w.]*)(?::|$)")
NAME: Final = re.compile(r"[A-Za-z_][\w.]*")

OUTPUT_CEILING: Final = 50
"""Блоков, чей вывод расходится с обещанным. Опускается вместе с правкой карточек
(#125) и только вниз; на нуле превышение станет обычной находкой."""

ARROW: Final = "→"
ALTERNATIVES: Final = re.compile(r"\s+/\s+|,?\s+затем\s+|\s+then\s+")
"""Как карточки перечисляют вывод нескольких строк: «a 1 / b 2», «[1], затем [2]»."""
EXPLANATION: Final = re.compile(r"\s+(?:—|--)\s+")
CYRILLIC: Final = re.compile(r"[а-яё]", re.IGNORECASE)
CALL: Final = re.compile(r"^\s*(?:await\s+)?(?P<name>\w+)\(.*\)\s*$")
"""Строка — вызов функции и только он: ``show(a=1)``, ``await main()``."""

Outcome = Literal["ok", "intended", "environment", "finding", "mismatch"]


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


def _defined(code: str) -> set[str]:
    """Имена функций, определённых в самом примере."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef)
    return {node.name for node in ast.walk(tree) if isinstance(node, kinds)}


def _prints(source: str, defined: set[str]) -> bool:
    """Строка печатает: ``print(...)`` или вызов функции, определённой в примере.

    Вызов чужой функции — ``re.findall(...)  # → [...]`` — запись в духе REPL:
    комментарий называет значение, а не напечатанное, и сверять его не с чем.
    Вызов своей функции печатает — именно такой вызов и уезжал в тело соседней
    функции, молча переставая исполняться (#125).
    """
    if "print(" in source:
        return True
    call = CALL.match(source)
    return call is not None and call.group("name") in defined


def promises(code: str) -> list[tuple[int, str]]:
    """Обещанный вывод: ``(строка, текст)`` для ``# →`` у печатающей строки.

    Комментарий отдельной строкой относится к ближайшей строке кода над ним —
    так карточки записывают длинный вывод. Строка с пометкой ``→ ?`` зависит
    от окружения и не сверяется.
    """
    lines = code.splitlines()
    defined = _defined(code)
    found: list[tuple[int, str]] = []
    for row, remark in comments(code).items():
        if ARROW not in remark or ENVIRONMENT_MARK in remark:
            continue
        source = lines[row - 1].split("#", 1)[0]
        if not source.strip():
            above = row - 2
            while above >= 0 and (
                not lines[above].strip() or lines[above].lstrip().startswith("#")
            ):
                above -= 1
            source = lines[above].split("#", 1)[0] if above >= 0 else ""
        if _prints(source, defined):
            found.append((row, remark.split(ARROW, 1)[1].strip()))
    return found


def _squash(text: str) -> str:
    """Без пробельных знаков: «[0,1]» и «[0, 1]» — одно и то же обещание."""
    return re.sub(r"\s+", "", text)


def kept(fragment: str, output: str) -> bool | None:
    """Сдержано ли обещание: ``True``, ``False`` или ``None`` — сверять нечего.

    Обещание сравнивается без пробелов, без пояснения в скобках в конце, без
    кавычек вокруг строки и до многоточия («3.14159...»). Не найденное обещание
    с кириллицей — пояснение словами, а не запись вывода: ``None``.
    """
    variants = [fragment]
    if " (" in fragment:
        variants.append(fragment.split(" (", 1)[0])
    variants += [v[1:-1] for v in variants if v[:1] == v[-1:] and v[:1] in {"'", '"'}]
    flat = _squash(output)
    for variant in variants:
        cut = variant.rstrip()
        needle = _squash(cut.rstrip(".…") if cut.endswith(("...", "…")) else cut)
        if needle and needle in flat:
            return True
    return None if CYRILLIC.search(fragment) else False


def unmet(code: str, output: str) -> list[tuple[int, str]]:
    """Обещания, которых нет в напечатанном."""
    broken = []
    for row, text in promises(code):
        value = EXPLANATION.split(text, maxsplit=1)[0]
        parts = [part.strip() for part in ALTERNATIVES.split(value) if part.strip()]
        if any(kept(part, output) is False for part in parts):
            broken.append((row, text))
    return broken


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

    Строка — кадр верхнего уровня (``<module>``) в файле примера: исключение,
    поднятое внутри функции примера, помечают на строке вызова, а не в теле —
    ``print(deep(0))  # → RecursionError``. Кадра верхнего уровня нет — берётся
    последний кадр примера. Имя — первая строка после всех кадров, похожая на
    ``Имя: сообщение``: сообщение бывает многострочным, поэтому последняя строка
    вывода именем не считается.
    """
    every = list(FRAME.finditer(stderr))
    own = [m for m in every if m.group("file").endswith(path)]
    top = [m for m in own if m.group("scope") == MODULE_SCOPE]
    chosen = top or own
    line = int(chosen[-1].group("line")) if chosen else 0
    tail = stderr[every[-1].end() :] if every else stderr
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
        broken = unmet(code, done.stdout)
        if broken:
            row, text = broken[0]
            more = f" (и ещё {len(broken) - 1})" if len(broken) > 1 else ""
            return Result(
                entry_id, "mismatch", f"строка {row}: не напечатано «{text}»{more}"
            )
        return Result(entry_id, "ok")
    return classify(entry_id, code, done.stderr, timed_out=False)


def examples(data: Path) -> dict[str, str]:
    """Примеры карточек из собранного глоссария: метка блока → код.

    Блок исполняется сам по себе, в своём процессе (#125): пример, который
    держится на определении из соседнего, — находка, а не случайность склейки.
    Метка — ``id`` карточки, а у карточки с несколькими блоками ещё и номер.
    """
    payload = json.loads(data.read_text(encoding="utf-8"))
    codes: dict[str, str] = {}
    for entry in payload["entries"]:
        blocks = entry.get("examples") or []
        for number, block in enumerate(blocks, start=1):
            label = f"{entry['id']} · пример {number}" if len(blocks) > 1 else entry["id"]
            codes[label] = "\n".join(block) + "\n"
    return codes


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
    tally = dict.fromkeys(("ok", "intended", "environment", "finding", "mismatch"), 0)
    for result in results:
        tally[result.outcome] += 1
    found = [r for r in results if r.outcome == "finding"]
    summary = (
        f"примеров: {len(results)} · исполнились: {tally['ok']} · "
        f"намеренно: {tally['intended']} · окружение: {tally['environment']} · "
        f"находок: {tally['finding']} · вывод расходится: {tally['mismatch']} "
        f"(потолок {OUTPUT_CEILING})"
    )
    if found:
        print("пример падает не там, где обещает:", file=sys.stderr)
        for result in found:
            print(f"  • {result.entry_id}: {result.detail}", file=sys.stderr)
    mismatched = [r for r in results if r.outcome == "mismatch"]
    over = len(mismatched) > OUTPUT_CEILING
    if over:
        print(
            f"вывод расходится с обещанным в {len(mismatched)} блоках — больше "
            f"потолка {OUTPUT_CEILING}:",
            file=sys.stderr,
        )
        for result in mismatched:
            print(f"  • {result.entry_id}: {result.detail}", file=sys.stderr)
    if found or over:
        print(summary, file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
