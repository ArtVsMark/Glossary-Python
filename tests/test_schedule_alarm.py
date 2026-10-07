"""Тесты тревоги по расписанию: подделки и живая половина (правило 142).

Подделки показывают, что исход площадки переводится в ответ верно и что
третий исход площадку не трогает. Живая половина держит главное: ни один
прогон с расписанием не остался без адресата.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

import schedule_alarm
from glossary.loader import project_root

WORKFLOWS = project_root() / ".github" / "workflows"
RUN = "https://github.com/o/r/actions/runs/1"
OWN_ALARM = {"python-next.yml": "работа alarm в самом прогоне (#163)"}
"""Прогоны со своей тревогой — сторож им не нужен."""


def _load(path: Path) -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _triggers(document: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML читает ключ «on» как True.
    found: dict[str, Any] = document.get("on") or document.get(True) or {}
    return found


def test_label_comes_from_the_file_not_the_name():
    """Имя прогона значков содержит запятые, а запятая делит метки в запросе."""
    assert (
        schedule_alarm.workflow_label(".github/workflows/badges.yml")
        == "расписание: badges"
    )


@pytest.mark.parametrize(
    "conclusion", ["cancelled", "skipped", "neutral", "action_required"]
)
def test_no_answer_is_the_third_outcome(
    conclusion: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    called: list[object] = []
    monkeypatch.setattr(
        schedule_alarm, "reconcile_alarm", lambda *a, **_: called.append(a)
    )
    argv = [
        "--name",
        "CI",
        "--path",
        "ci.yml",
        "--conclusion",
        conclusion,
        "--run-url",
        RUN,
    ]
    assert schedule_alarm.main(argv) == schedule_alarm.NOT_RUN
    assert conclusion in capsys.readouterr().err
    assert called == [], "без ответа о прогоне площадку не трогают"


@pytest.mark.parametrize(
    ("conclusion", "outcome"),
    [("success", "success"), ("failure", "failure"), ("timed_out", "failure")],
)
def test_conclusion_becomes_the_outcome(
    conclusion: str, outcome: str, monkeypatch: pytest.MonkeyPatch
):
    seen: dict[str, Any] = {}

    def fake(given: str, **kwargs: Any) -> str:
        seen.update(kwargs, outcome=given)
        return "ok"

    monkeypatch.setattr(schedule_alarm, "reconcile_alarm", fake)
    argv = [
        "--name",
        "Значки, факты",
        "--path",
        ".github/workflows/badges.yml",
        "--conclusion",
        conclusion,
        "--run-url",
        RUN,
    ]
    assert schedule_alarm.main(argv) == 0
    assert seen["outcome"] == outcome
    assert seen["labels"] == ("schedule-alarm", "расписание: badges")
    assert RUN in seen["text"] and "Значки, факты" in seen["title"]


@pytest.mark.live_surface
def test_every_scheduled_workflow_has_an_addressee():
    """Прогон с расписанием либо сторожится, либо держит свою тревогу."""
    watcher = _load(WORKFLOWS / "schedule-alarm.yml")
    watched = set(_triggers(watcher)["workflow_run"]["workflows"])
    names = {path.name: str(_load(path)["name"]) for path in WORKFLOWS.glob("*.yml")}
    scheduled = {
        path.name
        for path in WORKFLOWS.glob("*.yml")
        if "schedule" in _triggers(_load(path))
    }
    orphans = sorted(
        f for f in scheduled if f not in OWN_ALARM and names[f] not in watched
    )
    assert not orphans, (
        f"красное этих прогонов по расписанию не дойдёт ни до кого: {orphans}"
    )
    assert watched <= set(names.values()), "сторож ждёт прогон, которого нет"
    assert "alarm" in _load(WORKFLOWS / "python-next.yml")["jobs"]
    job = watcher["jobs"]["alarm"]
    assert "schedule" in job["if"]
    runs = " ".join(str(step.get("run", "")) for step in job["steps"])
    assert "scripts/schedule_alarm.py" in runs
