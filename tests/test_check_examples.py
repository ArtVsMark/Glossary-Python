"""Тесты гейта исполнения примеров: подделки и живая половина.

Подделки показывают, что исходы различаются верно — «исполнился», «намеренно»,
«окружение», «находка». Живая половина держит потолок находок на дереве: он
движется только вниз, и гейт встанет в CI, когда опустится до нуля (#82).
"""

import json
from pathlib import Path
from typing import Final

import pytest

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
