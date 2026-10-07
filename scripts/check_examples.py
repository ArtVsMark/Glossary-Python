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

ВЕРСИИ PYTHON (#154). Примеры исполняются на 3.14, а карточка обещает работу
с версии ``added`` до ``removed``. Ключ ``--python`` исполняет примеры другим
интерпретатором, а гейт сам остаётся на своём: так один и тот же закон
проверяется на всей матрице. На версии V пропускаются карточки, которых в ней
нет (``added`` позже V или ``removed`` не позже V), и блоки с первой строкой
``# Python 3.N+``, где 3.N новее V, — пример показывает поведение новее самой
возможности. Всё остальное обязано вести себя так, как обещано.

У карточки удалённого (#164) есть и жизнь после удаления: замена и ошибка
импорта на новой версии. Блок с пометкой ``# Python 3.N+``, где 3.N не раньше
``removed``, описывает именно её — сама возможность к этой версии уже исчезла,
— поэтому граница ``removed`` его не отсекает. Пометка раньше ``removed``
по-прежнему живёт внутри окна карточки.

Запуск::

    python scripts/check_examples.py              # гейт по data/glossary.json
    python scripts/check_examples.py --data FILE  # то же по другому файлу
    python scripts/check_examples.py --python python3.11  # примеры на 3.11

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
REQUIRES: Final = re.compile(r"^#\s*Python\s+(\d+)\.(\d+)\+")
"""Первая строка блока, требующего версию новее карточки: ``# Python 3.12+``."""
EXCEPTION_LINE: Final = re.compile(r"^(?P<name>[A-Za-z_][\w.]*)(?::|$)")
NAME: Final = re.compile(r"[A-Za-z_][\w.]*")

OUTPUT_CEILING: Final = 0
"""Блоков, чей вывод расходится с обещанным. Опускается вместе с правкой карточек
(#125) и только вниз; на нуле превышение станет обычной находкой."""

ARROW: Final = "→"
ALTERNATIVES: Final = re.compile(r"\s+/\s+|,?\s+затем\s+|\s+then\s+")
"""Как карточки перечисляют вывод нескольких строк: «a 1 / b 2», «[1], затем [2]»."""
EXPLANATION: Final = re.compile(r"\s+(?:—|--)\s+")
CYRILLIC: Final = re.compile(r"[а-яё]", re.IGNORECASE)
TRAILING_NOTE: Final = re.compile(r"\s*\([^()]*\)\s*$")
"""Пояснение в скобках в конце обещания: «False True (falsy / truthy)»."""
EXCEPTION_NAME: Final = re.compile(
    r"^[A-Z]\w*(?:Error|Exception|Warning|Exit|Interrupt|Iteration)\b"
)
IMPORT: Final = re.compile(r"^\s*(?:import\s|from\s+\S+\s+import\s)")
"""Строка импорта: обещание под ней ничего не обещает о выводе."""
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


def orphaned(code: str) -> list[int]:
    """Строки ``# →``, над которыми нет кода, — обещание без того, что обещает.

    Так обещание отрывалось от своего ``print`` при разбиении примера на блоки
    (#125): строка уходила первой в следующий блок, под импорт, и гейт её не
    сверял — сверять было не с чем. Под ней прятались неверные обещания.
    """
    lines = code.splitlines()
    rows = []
    for row, remark in comments(code).items():
        if (
            not remark.lstrip("# ").startswith(ARROW)
            or lines[row - 1].split("#", 1)[0].strip()
        ):
            continue
        above = row - 2
        while above >= 0 and (
            not lines[above].strip() or lines[above].lstrip().startswith("#")
        ):
            above -= 1
        if above < 0 or IMPORT.match(lines[above]):
            rows.append(row)
    return rows


def _squash(text: str) -> str:
    """Без пробельных знаков: «[0,1]» и «[0, 1]» — одно и то же обещание."""
    return re.sub(r"\s+", "", text)


def kept(fragment: str, output: str) -> bool | None:
    """Сдержано ли обещание: ``True``, ``False`` или ``None`` — сверять нечего.

    Обещание сравнивается без пробелов, без пояснения в скобках в конце, без
    кавычек вокруг строки и до многоточия («3.14159...»). Не найденное обещание
    с кириллицей в самой записи — пояснение словами, а не запись вывода: ``None``.
    Кириллица только в скобках словесным обещание не делает: в «100 33 20 (без
    деления на 0)» запись — числа, и сверять их есть с чем.
    """
    core = fragment.split(" (", 1)[0] if " (" in fragment else fragment
    variants = [fragment, core] if core != fragment else [fragment]
    variants += [v[1:-1] for v in variants if v[:1] == v[-1:] and v[:1] in {"'", '"'}]
    flat = _squash(output)
    for variant in variants:
        cut = variant.rstrip()
        needle = _squash(cut.rstrip(".…") if cut.endswith(("...", "…")) else cut)
        if needle and needle in flat:
            return True
    return None if CYRILLIC.search(core) else False


def _guarded(code: str) -> set[int]:
    """Строки тел ``try``: исключение там — ожидаемый исход, а не молчание."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    rows: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try | ast.TryStar):
            for stmt in node.body:
                rows.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return rows


def unmet(code: str, output: str) -> list[tuple[int, str]]:
    """Обещания, которых нет в напечатанном.

    Пояснение в скобках отрезается до деления на части: косая черта внутри
    него — «(falsy / truthy)» — не перечисление вывода. Имя исключения у строки
    в теле ``try`` — запись ловушки (``print(s.__secret)  # → AttributeError``),
    а не обещание печати: строка до печати не доходит.
    """
    guarded = _guarded(code)
    broken = []
    for row, text in promises(code):
        value = EXPLANATION.split(text, maxsplit=1)[0]
        value = TRAILING_NOTE.sub("", value) or value
        if row in guarded and EXCEPTION_NAME.match(value):
            continue
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
    lost = orphaned(code)
    if lost:
        return Result(
            entry_id, "mismatch", f"строка {lost[0]}: обещание «# →» без кода над ним"
        )
    with tempfile.TemporaryDirectory(prefix="example-") as tmp:
        path = Path(tmp) / FILENAME
        path.write_text(code, encoding="utf-8")
        env = {"PATH": os.defpath, "HOME": tmp, "LANG": "C.UTF-8", "TZ": "UTC"}
        try:
            # Код примера — наш собственный, из data/cards/, а не чужой ввод;
            # исполняется изолированно — ради этого гейт и заведён.
            done = subprocess.run(  # noqa: S603
                [INTERPRETER[0], "-I", "-X", "utf8", FILENAME],
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


INTERPRETER: list[str] = [sys.executable]
"""Чем исполняются примеры; ``--python`` подменяет его на прогон всей матрицы."""


def version_of(python: str) -> tuple[int, int]:
    """Версия интерпретатора ``major.minor``."""
    done = subprocess.run(  # noqa: S603 — интерпретатор назван владельцем прогона
        [python, "-I", "-c", "import sys; print(*sys.version_info[:2])"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=TIMEOUT,
        check=True,
    )
    major, minor = done.stdout.split()
    return int(major), int(minor)


def _version(text: str) -> tuple[int, int]:
    """Версия поля карточки: ``<3.0`` раньше любой 3.x."""
    if text.startswith("<"):
        return (2, 7)
    major, minor = text.split(".")
    return int(major), int(minor)


def applicable(
    entry: dict[str, object], block: list[str], version: tuple[int, int]
) -> bool:
    """Обещает ли карточка, что этот блок работает на версии ``version``.

    Блок с пометкой не раньше ``removed`` — жизнь после удаления, и граница
    ``removed`` к нему не применяется.
    """
    added, removed = str(entry.get("added") or ""), str(entry.get("removed") or "")
    if added and _version(added) > version:
        return False
    marked = REQUIRES.match(block[0]) if block else None
    since = (int(marked[1]), int(marked[2])) if marked else None
    if since and since > version:
        return False
    after_removal = bool(removed) and since is not None and since >= _version(removed)
    return not removed or after_removal or _version(removed) > version


def examples(data: Path, version: tuple[int, int] | None = None) -> dict[str, str]:
    """Примеры карточек из собранного глоссария: метка блока → код.

    Блок исполняется сам по себе, в своём процессе (#125): пример, который
    держится на определении из соседнего, — находка, а не случайность склейки.
    Метка — ``id`` карточки, а у карточки с несколькими блоками ещё и номер.

    Версия по умолчанию — интерпретатора, который запустил гейт, а не «все
    блоки»: карточка 3.15 на 3.14 не обещает ничего, и прогон её там — ложная
    находка. Умолчание «все» однажды так и сработало: живая половина набора
    краснела на первой же карточке новее планки.
    """
    if version is None:
        version = (sys.version_info.major, sys.version_info.minor)
    payload = json.loads(data.read_text(encoding="utf-8"))
    codes: dict[str, str] = {}
    for entry in payload["entries"]:
        blocks = entry.get("examples") or []
        for number, block in enumerate(blocks, start=1):
            if not applicable(entry, block, version):
                continue
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
    parser.add_argument(
        "--python", default=None, metavar="PATH", help="интерпретатор для примеров"
    )
    args = parser.parse_args(argv)

    if not args.data.exists():
        print(f"проверка не отработала: файла {args.data} нет", file=sys.stderr)
        return NOT_RUN
    version = (sys.version_info.major, sys.version_info.minor)
    if args.python:
        try:
            version = version_of(args.python)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            print(
                f"проверка не отработала: интерпретатор {args.python}: {error}",
                file=sys.stderr,
            )
            return NOT_RUN
        INTERPRETER[0] = args.python
        print(f"примеры исполняет Python {version[0]}.{version[1]} ({args.python})")
    codes = examples(args.data, version)
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
