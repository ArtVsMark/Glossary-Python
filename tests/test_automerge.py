"""Автомерж: одно исключение GraphQL, названное поимённо, и REST для всего прочего.

Правило каталога 001 требует REST по умолчанию и называет закрытый список
операций без REST-эквивалента; включение авто-мержа стоит в этом списке первым.
Набор держит **форму исполнения** этого исключения: обращение к GraphQL в
дереве ровно одно, идентификатор изменения берётся обычным чтением по REST, а
отказ, спрятанный в успешном ответе, отличается от успеха.

Что мутация — та самая и что она законна, машина не судит: это утверждение о
том, чего REST не умеет, и живёт оно в CLAUDE.md, разделе «Работа с GitHub».
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml

import automerge
from glossary.loader import project_root

ROOT = project_root()
SCRIPT = ROOT / "scripts" / "automerge.py"
WORKFLOW = ROOT / ".github" / "workflows" / "automerge.yml"
TREES = ("src", "scripts")


def code_strings(source: str) -> list[str]:
    """Строковые литералы исполняемого кода, без докстрингов.

    Проверять присутствие подстроки по всему файлу нельзя: слово «GraphQL»
    стоит и в объяснениях, почему его тут почти нет. Отношение «модуль
    обращается по такому адресу» живёт в исполняемых литералах, а не в прозе
    (правило 166).
    """
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def modules() -> list[Path]:
    """Исходники дерева, кроме кэшей."""
    return [
        path
        for tree in TREES
        for path in sorted((ROOT / tree).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


# --------------------------------------------------------------------------- #
# Исключение одно, и оно названо
# --------------------------------------------------------------------------- #


def test_graphql_lives_in_exactly_one_module():
    """Список исключений закрыт: второй вызов — это уже не исключение."""
    users = [
        path.relative_to(ROOT)
        for path in modules()
        if any(
            "graphql" in text.lower()
            for text in code_strings(path.read_text(encoding="utf-8"))
        )
    ]
    assert users == [Path("scripts/automerge.py")], (
        "GraphQL обращается больше чем из одного места — список исключений "
        f"правила 001 перестал быть закрытым: {users}"
    )


def test_the_only_mutation_is_the_named_one():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "enablePullRequestAutoMerge" in automerge.MUTATION
    assert source.count("mutation(") == 1, "мутация в исключении должна быть одна"


def test_node_id_is_read_over_rest():
    """Читать идентификатор мутацией — платить триста за то, что REST даёт за одну."""
    assert automerge.REST == "https://api.github.com"
    assert "graphql" not in automerge.REST


def test_the_exception_is_named_in_the_project_charter():
    """Механизм без записи в своде — обещание (правило 001 требует «поимённо»)."""
    charter = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "enablePullRequestAutoMerge" in charter, (
        "исключение не названо в CLAUDE.md, разделе «Работа с GitHub»"
    )


def test_the_check_reads_code_and_not_prose():
    """Гейт проверяется тем, что он обязан отвергнуть и пропустить (правило 140)."""
    prose = '"""Про GraphQL сказано, что его почти нет."""\nurl = "/pulls"'
    assert not [t for t in code_strings(prose) if "graphql" in t.lower()]
    code = '"""Транспорт."""\nurl = "https://api.github.com/graphql"'
    assert [t for t in code_strings(code) if "graphql" in t.lower()]


# --------------------------------------------------------------------------- #
# Отказ, спрятанный в успешном ответе
# --------------------------------------------------------------------------- #


def test_graphql_error_is_not_a_success():
    """GraphQL отвечает кодом 200 и кладёт отказ в errors (правило 039)."""
    assert automerge.refusal({"data": {}}) is None
    assert automerge.refusal({"errors": []}) is None
    message = automerge.refusal({"errors": [{"message": "Auto-merge is not allowed"}]})
    assert message is not None and "Auto-merge" in message


def test_refusal_names_the_change_and_the_likely_cause(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(automerge, "node_id", lambda _: "PR_1")
    monkeypatch.setattr(
        automerge,
        "_call",
        lambda *_, **__: {"errors": [{"message": "Auto-merge is not allowed"}]},
    )
    with pytest.raises(automerge.RefusedError) as refused:
        automerge.arm(7)
    text = str(refused.value)
    assert "#7" in text, "находка обязана называть предмет (правило 158)"
    assert "Allow auto-merge" in text, "названа вероятная причина отказа"


def test_armed_change_reports_when(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(automerge, "node_id", lambda _: "PR_1")
    monkeypatch.setattr(
        automerge,
        "_call",
        lambda *_, **__: {
            "data": {
                "enablePullRequestAutoMerge": {
                    "pullRequest": {
                        "number": 7,
                        "autoMergeRequest": {"enabledAt": "2026-09-07T09:00:00Z"},
                    }
                }
            }
        },
    )
    assert automerge.arm(7) == "2026-09-07T09:00:00Z"


# --------------------------------------------------------------------------- #
# Исходы
# --------------------------------------------------------------------------- #


def test_missing_token_is_the_third_outcome(monkeypatch: pytest.MonkeyPatch, capsys):
    for name in automerge.TOKEN_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    assert automerge.main(["7"]) == 2
    error = capsys.readouterr().err
    assert "не отработало" in error
    for name in automerge.TOKEN_VARIABLES:
        assert name in error, "третий исход обязан назвать предмет"


def test_refusal_is_a_finding_not_a_breakdown(monkeypatch: pytest.MonkeyPatch, capsys):
    def refuse(_: int) -> str:
        raise automerge.RefusedError("#7 в очередь не поставлено: нельзя")

    monkeypatch.setattr(automerge, "arm", refuse)
    assert automerge.main(["7"]) == 1
    assert "#7" in capsys.readouterr().err


def test_success_says_who_merges(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(automerge, "arm", lambda _: "2026-09-07T09:00:00Z")
    assert automerge.main(["7"]) == 0
    assert "сливает площадка" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Прогон
# --------------------------------------------------------------------------- #


def workflow() -> dict[Any, Any]:
    """Разобранный прогон автомержа.

    Ключи разнородны: ``on`` разбирается YAML-ом как булево ``True`` — в YAML 1.1
    это одно из написаний истины, — поэтому тип ключа шире строки.
    """
    document: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return document


def triggers() -> dict[str, Any]:
    """Триггеры прогона.

    Ключ ``on`` разбирается YAML-ом как булево ``True``: в YAML 1.1 это одно из
    написаний истины. Читать его надо обоими способами.
    """
    document = workflow()
    found: dict[str, Any] = document.get("on") or document.get(True) or {}
    return found


def test_workflow_names_the_events_explicitly():
    """Умолчание площадки снятия черновика не включает (правило 104)."""
    events = triggers()
    assert "ready_for_review" in events["pull_request"]["types"]
    assert "workflow_dispatch" in events, "у автоматики обязана быть ручная кнопка"


def test_workflow_reacts_to_labels():
    """Сняли hold — изменение обязано встать в очередь, а не ждать нового толчка."""
    types = triggers()["pull_request"]["types"]
    assert "labeled" in types and "unlabeled" in types


def test_workflow_skips_drafts_and_held_changes():
    """Черновик согласия не выражает, а hold его отзывает: ни то, ни другое не ставят."""
    condition = str(workflow()["jobs"]["arm"]["if"])
    assert "draft" in condition
    assert "hold" in condition
