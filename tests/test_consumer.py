"""Вердикты по предложениям потребителя (#250).

Подделки показывают, что разбор устроен верно: исполненное узнаётся по данным,
точное решение сильнее образца, нерешённое — ``pending``, чужой файл отвергается.
Живая половина держит само дерево: файл решений читается, вердикты в нём из
допустимых, у отклонённого названа причина, у принятого — задача.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from glossary import consumer
from glossary.cli import EXIT_OK, EXIT_USAGE, main
from glossary.loader import project_root
from tests.factories import make_entry, make_glossary


def payload(*proposals: dict[str, Any]) -> dict[str, Any]:
    """Файл предложений с верной шапкой."""
    return {
        "schema": "1.0",
        "producer": consumer.PRODUCER,
        "generated_at": "2026-10-09T12:00:00+00:00",
        "examined": {"release": "v1.4.0"},
        "proposals": list(proposals),
    }


GLOSSARY = make_glossary(
    make_entry(id="abc", title="abc"),
    make_entry(id="OSError", title="OSError", aliases=("IOError",)),
    make_entry(id="AttributeError", title="AttributeError"),
)


def verdict(proposal: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> str:
    """Вердикт одного предложения на подделке глоссария."""
    _, [parsed] = consumer.read_proposals(payload(proposal))
    return str(consumer.verdict_of(parsed, GLOSSARY, decisions)["verdict"])


def test_existing_module_card_is_done_without_a_decision():
    assert (
        verdict({"slug": "module-card:abc", "kind": "module-card", "subject": "abc"}, {})
        == "done"
    )


def test_builtin_name_found_among_aliases_is_done():
    proposal = {
        "slug": "builtin-card:IOError",
        "kind": "builtin-card",
        "subject": "IOError",
    }
    assert verdict(proposal, {}) == "done"


def test_id_convention_is_done_once_every_card_is_renamed():
    cards = [{"id": "attributeerror", "name": "AttributeError"}]
    proposal = {
        "slug": "id-convention:x",
        "kind": "id-convention",
        "subject": "x",
        "evidence": {"cards": cards},
    }
    assert verdict(proposal, {}) == "done"
    stale = {**proposal, "evidence": {"cards": [{"id": "abc", "name": "AttributeError"}]}}
    assert verdict(stale, {}) == "pending", "старый id ещё жив — не исполнено"


def test_exact_decision_beats_the_pattern():
    decisions: dict[str, dict[str, Any]] = {
        "syntax-card:*": {"verdict": "accepted", "issue": 250},
        "syntax-card:tstring": {"verdict": "rejected", "why": "ещё не решили"},
    }
    tstring = {"slug": "syntax-card:tstring", "kind": "syntax-card", "subject": "tstring"}
    posonly = {"slug": "syntax-card:posonly", "kind": "syntax-card", "subject": "posonly"}
    assert verdict(tstring, decisions) == "rejected"
    assert verdict(posonly, decisions) == "accepted"


def test_undecided_and_unfinished_is_pending():
    assert (
        verdict({"slug": "syntax-card:new", "kind": "syntax-card", "subject": "new"}, {})
        == "pending"
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [({"producer": "someone/else"}, "издатель"), ({"schema": "2.0"}, "формат")],
)
def test_foreign_file_is_refused(change: dict[str, str], reason: str):
    with pytest.raises(consumer.ProposalsError, match=reason):
        consumer.read_proposals({**payload(), **change})


def test_collect_counts_every_verdict():
    answer = consumer.collect(
        payload(
            {"slug": "module-card:abc", "kind": "module-card", "subject": "abc"},
            {"slug": "syntax-card:new", "kind": "syntax-card", "subject": "new"},
        ),
        GLOSSARY,
        {},
    )
    assert answer["totals"] == {"done": 1, "accepted": 0, "rejected": 0, "pending": 1}
    assert answer["answers_to"]["examined"] == {"release": "v1.4.0"}
    assert len(answer["verdicts"]) == 2, "список не усекается"


def test_missing_file_is_the_third_outcome(tmp_path: Path, capsys):
    assert main(["verdicts", "--proposals", str(tmp_path / "нет.json")]) == EXIT_USAGE
    assert "не подключён" in capsys.readouterr().err


def test_command_writes_verdicts_and_names_pending(tmp_path: Path, capsys):
    source = tmp_path / "proposals.json"
    source.write_text(
        json.dumps(
            payload({"slug": "syntax-card:new", "kind": "syntax-card", "subject": "new"})
        ),
        encoding="utf-8",
    )
    decisions = tmp_path / "decisions.json"
    decisions.write_text('{"decisions": {}}', encoding="utf-8")
    out = tmp_path / "verdicts.json"
    code = main(
        [
            "verdicts",
            "--proposals",
            str(source),
            "--decisions",
            str(decisions),
            "-o",
            str(out),
        ]
    )
    assert code == EXIT_OK
    assert json.loads(out.read_text(encoding="utf-8"))["totals"]["pending"] == 1
    assert "без решения: syntax-card:new" in capsys.readouterr().err


@pytest.mark.live_surface
def test_decisions_file_of_the_tree_is_well_formed():
    path = project_root() / "data" / consumer.DECISIONS_FILE
    decisions = consumer.load_decisions(path)
    assert decisions, "файл решений пуст"
    for key, decision in decisions.items():
        assert decision["verdict"] in {"accepted", "rejected"}, key
        if decision["verdict"] == "rejected":
            assert decision.get("why"), f"{key}: у отклонённого нет причины"
        else:
            assert isinstance(decision.get("issue"), int), (
                f"{key}: у принятого нет задачи"
            )
