"""Тесты гейта исполнения примеров: подделки и живая половина.

Подделки показывают, что исходы различаются верно — «исполнился», «намеренно»,
«окружение», «находка». Живая половина держит потолок находок на дереве: он
движется только вниз, и гейт встанет в CI, когда опустится до нуля (#82).
"""

import json
import sys
from pathlib import Path
from typing import Final

import pytest
import yaml

import check_examples as gate

CEILING: Final = 0
"""Находок на дереве сейчас. Опускается вместе с правкой карточек (#82)."""


def outcome(code: str) -> gate.Result:
    return gate.execute("sample", code)


# --------------------------- подделки ---------------------------


def test_clean_example_runs():
    assert outcome("print(1 + 1)   # → 2\n").outcome == "ok"


def test_named_exception_is_intended():
    """Ловушка, показанная примером, — не находка."""
    result = outcome("print(1)\nprint(b'a' + 'b')   # → TypeError\n")
    assert (result.outcome, result.detail) == ("intended", "строка 2: TypeError")


def test_base_class_in_the_comment_covers_the_subclass():
    """Обещан OSError — упал FileNotFoundError: это то же обещание."""
    result = outcome("open('нет.txt')   # → OSError, файла нет\n")
    assert result.outcome == "intended"


def test_dotted_name_is_recognised():
    code = "import json\njson.loads('{')   # → json.JSONDecodeError\n"
    assert outcome(code).outcome == "intended"


def test_wrong_exception_named_is_a_finding():
    """Обещано одно, упало другое — карточка учит неправде."""
    result = outcome("int('x')   # → TypeError\n")
    assert result.outcome == "finding"
    assert "ValueError" in result.detail


def test_unmarked_failure_is_a_finding():
    result = outcome("x = 1\nprint(y)\n")
    assert (result.outcome, result.detail) == ("finding", "строка 2: NameError")


def test_hash_inside_a_string_is_not_a_comment():
    """Решётка в строке не делает строку помеченной."""
    result = outcome("print('# → NameError', y)\n")
    assert result.outcome == "finding"


def test_environment_mark_excuses_the_line():
    result = outcome("open('/нет/такого')   # → ? только Unix: зависит от системы\n")
    assert result.outcome == "environment"


def test_environment_mark_elsewhere_does_not_excuse_the_line():
    code = "print(1)   # → ? зависит от системы\nprint(y)\n"
    assert outcome(code).outcome == "finding"


def test_timeout_without_mark_is_a_finding(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gate, "TIMEOUT", 0.5)
    result = outcome("import time\ntime.sleep(5)\n")
    assert result.outcome == "finding"


def test_timeout_with_mark_is_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gate, "TIMEOUT", 0.5)
    result = outcome("import time\ntime.sleep(5)   # → ? ждёт терминала\n")
    assert result.outcome == "environment"


def test_example_does_not_see_the_checker_environment(monkeypatch: pytest.MonkeyPatch):
    """Пустое окружение: пример не узнаёт ничего о машине проверяющего."""
    monkeypatch.setenv("SECRET_FOR_TEST", "x")
    code = "import os\nprint(os.environ['SECRET_FOR_TEST'])\n"
    assert outcome(code).outcome == "finding"


def test_multiline_message_does_not_hide_the_name():
    """Сообщение в несколько строк: имя берётся сразу после кадров."""
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "/tmp/x/example.py", line 3, in <module>\n'
        "    print(Perm(5))\n"
        "ValueError: <flag 'Perm'> invalid value 5\n"
        "    given 0b0 101\n"
        "  allowed 0b0 011\n"
    )
    assert gate.failure(stderr, gate.FILENAME) == (3, "ValueError")


def test_failure_inside_a_function_is_marked_at_the_call():
    """Пометку ставят на строку вызова, которую видит читатель, а не в тело."""
    code = "def deep(n):\n    return deep(n + 1)\nprint(deep(0))  # → RecursionError\n"
    assert outcome(code).outcome == "intended"


def test_call_line_without_mark_is_a_finding_even_if_body_is_marked():
    code = "def f():\n    return 1 / 0  # → ZeroDivisionError\nf()\n"
    result = outcome(code)
    assert (result.outcome, result.detail) == ("finding", "строка 3: ZeroDivisionError")


def test_lineage_of_unknown_name_is_the_name_itself():
    assert gate.lineage("MyOwnError") == {"MyOwnError"}


# --------------------------- обещанный вывод ---------------------------


def test_kept_promise_is_ok():
    assert outcome("print([0,1])  # → [0, 1]\n").outcome == "ok"


def test_swallowed_call_is_a_mismatch():
    """Вызов, уехавший в тело функции, не падает — он молчит (#125)."""
    code = "def show():\n    print('a')\n    show()  # → a\n"
    result = outcome(code)
    assert (result.outcome, result.detail) == ("mismatch", "строка 3: не напечатано «a»")


def test_comment_line_belongs_to_the_print_above():
    assert gate.promises("print(1)\n# → 1\n") == [(2, "1")]


def test_value_without_print_is_not_a_promise():
    assert gate.promises("x = 5 / 2  # → 2.5\n") == []


def test_environment_mark_is_not_checked():
    assert gate.promises("import os\nprint(os.getpid())  # → ? номер процесса\n") == []


@pytest.mark.parametrize(
    ("promise", "output"),
    [
        ("a 1 / b 2", "a 1\nb 2\n"),
        ("[1, 2], затем [3, 4]", "[1, 2]\n[3, 4]\n"),
        ("'a'", "a\n"),
        ("3.14159...", "3.141592653589793\n"),
        ("False (bool != int при type())", "False\n"),
        ("10 — сумма", "10\n"),
    ],
)
def test_promise_spellings_are_understood(promise: str, output: str):
    assert gate.unmet(f"print(0)  # → {promise}\n", output) == []


def test_slash_inside_the_note_is_not_a_list():
    assert gate.unmet("print(0)  # → False True (falsy / truthy)\n", "False True\n") == []


def test_cyrillic_note_does_not_hide_a_wrong_record():
    """Запись — числа; кириллица лишь в пояснении, и расхождение видно."""
    code = "print(0)  # → 100 33 20 (без деления на 0)\n"
    assert gate.unmet(code, "20\n") == [(1, "100 33 20 (без деления на 0)")]


def test_exception_inside_try_is_a_trap_not_output():
    code = "try:\n    print(s.x)  # → AttributeError\nexcept AttributeError:\n    pass\n"
    assert gate.unmet(code, "") == []


def test_exception_name_outside_try_is_still_checked():
    code = "print(type(e).__name__)  # → ExecError\n"
    assert gate.unmet(code, "RuntimeError\n") == [(1, "ExecError")]


def test_words_are_an_explanation_not_output():
    """Словесное обещание сверять не с чем — оно не находка."""
    assert (
        gate.unmet(
            "print(2 ** 100)  # → большое число\n", "1267650600228229401496703205376\n"
        )
        == []
    )


def test_mismatches_over_the_ceiling_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(gate, "OUTPUT_CEILING", 0)
    data = write(tmp_path / "g.json", {"a": [["print(1)  # → 2"]]})
    assert gate.main(["--data", str(data)]) == 1


def test_mismatches_under_the_ceiling_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(gate, "OUTPUT_CEILING", 1)
    data = write(tmp_path / "g.json", {"a": [["print(1)  # → 2"]]})
    assert gate.main(["--data", str(data)]) == 0


# --------------------------- точка входа ---------------------------


def write(path: Path, examples: dict[str, list[list[str]]]) -> Path:
    entries = [{"id": key, "examples": blocks} for key, blocks in examples.items()]
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def test_main_reports_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    data = write(tmp_path / "g.json", {"a": [["print(1)"]], "b": [["print(y)"]]})
    assert gate.main(["--data", str(data)]) == 1
    assert "b: строка 1: NameError" in capsys.readouterr().err


def test_main_is_clean(tmp_path: Path):
    data = write(tmp_path / "g.json", {"a": [["print(1)"]]})
    assert gate.main(["--data", str(data)]) == 0


def test_each_block_runs_on_its_own(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Блок, держащийся на определении из соседнего, — находка с номером (#125)."""
    data = write(tmp_path / "g.json", {"a": [["x = 1", "print(x)"], ["print(x)"]]})
    assert gate.main(["--data", str(data)]) == 1
    assert "a · пример 2: строка 1: NameError" in capsys.readouterr().err


def test_missing_data_is_the_third_outcome(tmp_path: Path, capsys):
    absent = tmp_path / "нет.json"
    assert gate.main(["--data", str(absent)]) == gate.NOT_RUN
    assert str(absent) in capsys.readouterr().err, "третий исход называет предмет"


def test_no_examples_is_the_third_outcome(tmp_path: Path):
    data = write(tmp_path / "g.json", {"a": []})
    assert gate.main(["--data", str(data)]) == gate.NOT_RUN


# --------------------------- живая половина ---------------------------


@pytest.mark.live_surface
def test_findings_on_the_tree_do_not_grow():
    """Храповик: находок на дереве не больше потолка.

    Только верхняя граница, без требования равенства: часть находок зависит от
    машины (сеть, терминал), и в прогоне CI их может оказаться меньше. Потолок
    опускается руками вместе с правкой карточек (#82).
    """
    results = gate.check(gate.examples(gate.ROOT / gate.DATA))
    found = sorted(r.entry_id for r in results if r.outcome == "finding")
    assert len(found) <= CEILING, f"находок стало больше потолка {CEILING}: {found}"
    mismatched = sorted(r.entry_id for r in results if r.outcome == "mismatch")
    assert len(mismatched) <= gate.OUTPUT_CEILING, (
        f"вывод расходится в {len(mismatched)} блоках — больше потолка: {mismatched}"
    )


@pytest.mark.parametrize(
    "code",
    [
        "# → 3\nprint(3)\n",
        "import math\n# → 3.14\nprint(math.pi)\n",
        "from math import pi\n\n# → 3.14\n",
    ],
)
def test_promise_without_code_above_is_orphaned(code: str):
    assert gate.orphaned(code)


@pytest.mark.parametrize(
    "code",
    [
        "print(3)\n# → 3\n",
        "import math\nprint(math.pi)  # → 3.141592653589793\n",
        "x = 1\n# комментарий\n# → 1\n",
        "# Десятичное → другие\nprint(bin(2))  # → 0b10\n",
        "# age = int(input())  # → преобразование в int\nprint(1)\n",
    ],
)
def test_promise_under_its_code_is_not_orphaned(code: str):
    assert gate.orphaned(code) == []


def test_orphaned_promise_is_a_mismatch_without_running():
    result = gate.execute("card", "import math\n# → 3\nprint(3)\n")
    assert result.outcome == "mismatch"
    assert "без кода над ним" in result.detail


# --------------------------- версии Python (#154) ---------------------------


@pytest.mark.parametrize(
    ("entry", "block", "version", "expected"),
    [
        ({"added": "<3.0"}, ["print(1)"], (3, 11), True),
        ({"added": "3.12"}, ["print(1)"], (3, 11), False),
        ({"added": "3.12"}, ["print(1)"], (3, 12), True),
        ({"added": "3.0", "removed": "3.13"}, ["print(1)"], (3, 12), True),
        ({"added": "3.0", "removed": "3.13"}, ["print(1)"], (3, 13), False),
        ({"added": "3.0"}, ["# Python 3.12+", "print(1)"], (3, 11), False),
        ({"added": "3.0"}, ["# Python 3.12+", "print(1)"], (3, 12), True),
        ({"added": "3.0"}, ["# Python 3.13+ (на Windows — 3.12+)"], (3, 12), False),
        ({}, [], (3, 11), True),
        # Удалённое (#164): блок без пометки живёт до removed,
        ({"added": "3.0", "removed": "3.12"}, ["import imp"], (3, 11), True),
        ({"added": "3.0", "removed": "3.12"}, ["import imp"], (3, 12), False),
        # пометка не раньше removed — жизнь после удаления,
        ({"added": "3.0", "removed": "3.12"}, ["# Python 3.12+"], (3, 13), True),
        ({"added": "3.0", "removed": "3.12"}, ["# Python 3.12+"], (3, 11), False),
        # пометка раньше removed — внутри окна карточки.
        ({"added": "3.0", "removed": "3.17"}, ["# Python 3.12+"], (3, 13), True),
        ({"added": "3.0", "removed": "3.17"}, ["# Python 3.12+"], (3, 17), False),
    ],
)
def test_applicable_follows_the_card_promise(
    entry: dict[str, object], block: list[str], version: tuple[int, int], expected: bool
):
    assert gate.applicable(entry, block, version) is expected


def test_marker_only_on_the_first_line():
    """Пометка в середине блока — комментарий, а не обещание версии."""
    assert gate.applicable({}, ["x = 1", "# Python 3.99+"], (3, 11))


def test_examples_skip_what_the_version_does_not_promise(tmp_path: Path):
    entries = [
        {
            "id": "old",
            "added": "3.0",
            "examples": [["print(1)"], ["# Python 3.13+", "print(2)"]],
        },
        {"id": "new", "added": "3.13", "examples": [["print(3)"]]},
    ]
    data = tmp_path / "g.json"
    data.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    assert list(gate.examples(data, (3, 12))) == ["old · пример 1"]
    assert len(gate.examples(data, (3, 13))) == 3
    assert len(gate.examples(data)) == 3, "без версии — версия интерпретатора гейта"


def test_default_version_is_the_running_interpreter(tmp_path: Path):
    """Карточка новее интерпретатора не исполняется и без явной версии."""
    future = f"{sys.version_info.major}.{sys.version_info.minor + 1}"
    entries = [{"id": "future", "added": future, "examples": [["print(1)"]]}]
    data = tmp_path / "g.json"
    data.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    assert gate.examples(data) == {}


def test_version_of_reads_the_interpreter():
    assert gate.version_of(sys.executable) == sys.version_info[:2]


def test_main_runs_examples_with_the_named_interpreter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(gate, "INTERPRETER", [sys.executable])
    data = write(tmp_path / "g.json", {"a": [["print(1)  # → 1"]]})
    assert gate.main(["--data", str(data), "--python", sys.executable]) == 0
    major, minor = sys.version_info[:2]
    assert f"Python {major}.{minor}" in capsys.readouterr().out


def test_unknown_interpreter_is_the_third_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(gate, "INTERPRETER", list(gate.INTERPRETER))
    data = write(tmp_path / "g.json", {"a": [["print(1)"]]})
    absent = str(tmp_path / "нет-python")
    assert gate.main(["--data", str(data), "--python", absent]) == gate.NOT_RUN
    assert absent in capsys.readouterr().err, "третий исход называет интерпретатор"


@pytest.mark.live_surface
def test_ci_runs_examples_on_every_promised_version():
    """Младшие версии исполняет ci.yml, следующую — python-next.yml (#154)."""
    workflows = gate.ROOT / ".github" / "workflows"
    ci = yaml.safe_load((workflows / "ci.yml").read_text(encoding="utf-8"))
    job = ci["jobs"]["examples"]
    versions = {str(v) for v in job["strategy"]["matrix"]["python-version"]}
    assert {"3.11", "3.12", "3.13"} <= versions
    runs = " ".join(str(step.get("run", "")) for step in job["steps"])
    assert "check_examples.py" in runs and "--python" in runs
    assert "examples" in ci["jobs"]["check-pr"]["needs"], "матрица держит слияние"
    nxt = (workflows / "python-next.yml").read_text(encoding="utf-8")
    assert "scripts/check_examples.py" in nxt


# --------------------------- устаревание (#154) ---------------------------

DEPRECATED_CALL = (
    "import builtins, warnings\n"
    "old = getattr(builtins, 'Deprecation' + 'Warning')\n"
    "warnings.warn('old', old)\n"
    "print(1)\n"
)
"""Предупреждение без имени в тексте: блок, назвавший его, — намеренный показ."""


def test_deprecation_warning_is_noticed():
    assert outcome(DEPRECATED_CALL).warned
    assert not outcome("print(1)\n").warned


def test_warning_from_library_code_is_shown_too():
    """Без фильтра always предупреждение не из __main__ молчит."""
    code = (
        "import warnings\n"
        "def lib():\n"
        "    warnings.warn('old', getattr(__builtins__, 'Deprecation' + 'Warning'))\n"
        "lib()\n"
    )
    assert outcome(code).warned


def _entries(tmp_path: Path, **card: object) -> Path:
    entry = {"id": "c", "examples": [["print(1)"]], **card}
    data = tmp_path / "g.json"
    data.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    return data


@pytest.mark.parametrize(
    ("card", "silent"),
    [
        ({}, ["c"]),
        ({"deprecated": "3.12"}, []),
        ({"deprecated": "3.99"}, ["c"]),
        ({"examples": [["print(1)  # → 1 — DeprecationWarning у этой формы"]]}, []),
    ],
)
def test_unrecorded_deprecation(
    tmp_path: Path, card: dict[str, object], silent: list[str]
):
    data = _entries(tmp_path, **card)
    warned = [gate.Result("c", "ok", warned=True)]
    assert [r.entry_id for r in gate.unrecorded(data, warned, (3, 14))] == silent


def test_block_naming_the_warning_is_an_intended_demo(tmp_path: Path):
    """Карточка модуля warnings показывает DeprecationWarning намеренно."""
    shown = ["import warnings", "warnings.warn('old', DeprecationWarning)"]
    data = write(tmp_path / "g.json", {"a": [shown]})
    assert gate.main(["--data", str(data)]) == 0


def test_main_fails_on_unrecorded_deprecation(tmp_path: Path, capsys):
    data = write(tmp_path / "g.json", {"a": [DEPRECATED_CALL.splitlines()]})
    assert gate.main(["--data", str(data)]) == 1
    assert "DeprecationWarning" in capsys.readouterr().err
