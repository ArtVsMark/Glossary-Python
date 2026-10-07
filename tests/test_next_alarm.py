"""Тесты тревоги о предварительной версии: подделки и живая половина.

Подделки подменяют обращение к площадке и показывают, что задача заводится,
молчит и закрывается ровно тогда, когда должна. Живая половина держит то, что
прогон ``python-next.yml`` действительно зовёт тревогу и имеет право писать
задачи (#154).
"""

from typing import Any

import pytest
import yaml

import next_alarm
from automerge import NotRunError
from glossary.loader import project_root

RUN = "https://github.com/o/r/actions/runs/1"


class Platform:
    """Подделка площадки: открытые задачи, журнал запросов и то, что она хранит.

    ``drop_label`` воспроизводит тихую порчу: задача создана, код успешный,
    а метки у неё нет.
    """

    def __init__(self, alarm: int | None, *, drop_label: bool = False) -> None:
        self.alarm = alarm
        self.drop_label = drop_label
        self.stored: dict[str, Any] = {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str | None = None,
    ) -> Any:
        verb = method or ("GET" if payload is None else "POST")
        self.calls.append((verb, url, payload))
        if verb == "GET" and "?" in url:
            return [{"number": self.alarm}] if self.alarm else []
        if verb == "GET":
            return self.stored
        if url.endswith("/issues"):
            sent = payload or {}
            names = [] if self.drop_label else sent["labels"]
            self.stored = {**sent, "number": 77, "labels": [{"name": n} for n in names]}
            return self.stored
        if verb == "PATCH":
            self.stored = {**self.stored, **(payload or {})}
        return {}


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Platform:
    fake = Platform(getattr(request, "param", None))
    monkeypatch.setattr(next_alarm, "_call", fake)
    return fake


@pytest.mark.parametrize(
    ("outcome", "alarm", "action"),
    [
        ("failure", None, "open"),
        ("failure", 5, "keep"),
        ("success", 5, "close"),
        ("success", None, "none"),
    ],
)
def test_decide(outcome: str, alarm: int | None, action: str):
    assert next_alarm.decide(outcome, alarm) == action


def test_red_without_alarm_opens_one_labelled_issue(platform: Platform):
    said = next_alarm.reconcile("failure", "3.15", RUN)
    assert "#77" in said
    posts = [c for c in platform.calls if c[0] == "POST"]
    assert len(posts) == 1
    assert platform.calls[-1] == ("GET", posts[0][1] + "/77", None), "перечитано"
    payload = posts[0][2] or {}
    assert payload["labels"] == [next_alarm.LABEL]
    assert "3.15" in payload["title"] and RUN in payload["body"]


@pytest.mark.parametrize("platform", [5], indirect=True)
def test_red_with_alarm_stays_silent(platform: Platform):
    """Ежедневное «всё ещё красное» — шум, который перестают читать."""
    assert "#5" in next_alarm.reconcile("failure", "3.15", RUN)
    assert [c[0] for c in platform.calls] == ["GET"]


@pytest.mark.parametrize("platform", [5], indirect=True)
def test_green_closes_the_alarm_with_the_run(platform: Platform):
    next_alarm.reconcile("success", "3.15", RUN)
    verbs = [(c[0], c[1].rsplit("/", 2)[-2:]) for c in platform.calls]
    assert verbs[1] == ("POST", ["5", "comments"])
    assert verbs[2][0] == "PATCH" and platform.calls[2][2] == {"state": "closed"}
    assert verbs[3][0] == "GET", "закрытие перечитано"
    assert RUN in str(platform.calls[1][2])


def test_green_without_alarm_does_nothing(platform: Platform):
    next_alarm.reconcile("success", "3.15", RUN)
    assert [c[0] for c in platform.calls] == ["GET"]


@pytest.mark.parametrize("outcome", ["cancelled", "skipped"])
def test_no_answer_is_the_third_outcome(outcome: str, platform: Platform, capsys):
    argv = ["--outcome", outcome, "--version", "3.15", "--run-url", RUN]
    assert next_alarm.main(argv) == next_alarm.NOT_RUN
    assert outcome in capsys.readouterr().err
    assert platform.calls == [], "без ответа о версии площадку не трогают"


def test_platform_refusal_is_the_third_outcome(monkeypatch: pytest.MonkeyPatch, capsys):
    def refuse(*_: Any, **__: Any) -> Any:
        raise NotRunError("403 Forbidden")

    monkeypatch.setattr(next_alarm, "_call", refuse)
    argv = ["--outcome", "failure", "--version", "3.15", "--run-url", RUN]
    assert next_alarm.main(argv) == next_alarm.NOT_RUN
    assert "403" in capsys.readouterr().err


@pytest.mark.usefixtures("platform")
def test_main_reports_what_it_did(capsys):
    argv = ["--outcome", "failure", "--version", "3.15", "--run-url", RUN]
    assert next_alarm.main(argv) == 0
    assert "#77" in capsys.readouterr().out


@pytest.mark.live_surface
def test_python_next_raises_the_alarm():
    """Тревога — работа прогона на main, с правом писать задачи."""
    path = project_root() / ".github" / "workflows" / "python-next.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["alarm"]
    assert job["needs"] == "tests" or job["needs"] == ["tests"]
    assert "always()" in job["if"] and "refs/heads/main" in job["if"]
    assert job["permissions"]["issues"] == "write"
    runs = " ".join(str(step.get("run", "")) for step in job["steps"])
    assert "scripts/next_alarm.py" in runs and "needs.tests.result" in runs


def test_label_dropped_by_the_platform_is_not_a_success(monkeypatch: pytest.MonkeyPatch):
    """Без метки задача не найдётся завтра — и тревога заведётся второй (188)."""
    monkeypatch.setattr(next_alarm, "_call", Platform(None, drop_label=True))
    with pytest.raises(NotRunError, match="метки"):
        next_alarm.reconcile("failure", "3.15", RUN)


def test_rewritten_text_is_named():
    sent: dict[str, object] = {"title": "t", "body": "b", "labels": ["python-next"]}
    published: dict[str, object] = {
        "title": "t",
        "body": "b — изменено",
        "labels": [{"name": "python-next"}],
    }
    assert next_alarm.undelivered(sent, published) == [
        "поле body опубликовано не тем, что отправлено"
    ]
    assert next_alarm.undelivered(sent, {**published, "body": "b"}) == []


class StuckPlatform(Platform):
    """Площадка, принявшая закрытие кодом успеха и не закрывшая задачу."""

    def __call__(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str | None = None,
    ) -> Any:
        if method == "PATCH":
            self.calls.append(("PATCH", url, payload))
            return {}
        return super().__call__(url, payload, method=method)


def test_close_that_did_not_close_is_not_a_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(next_alarm, "_call", StuckPlatform(5))
    with pytest.raises(NotRunError, match="после закрытия"):
        next_alarm.reconcile("success", "3.15", RUN)
