"""Машинные авторы освобождаются от гейтов связи и журнала поимённо."""

from pathlib import Path

import pytest

import check_pr_link
import machine_authors


def test_bot_alone_is_exempt():
    """Изменение одного бота освобождено, и причина названа."""
    reason = machine_authors.exemption(["dependabot[bot]", "dependabot[bot]"])
    assert reason is not None and "dependabot[bot]" in reason


@pytest.mark.parametrize(
    "authors",
    [[], [""], ["ArtVsMark"], ["dependabot[bot]", "ArtVsMark"], ["renovate[bot]"]],
)
def test_human_or_unknown_author_is_not_exempt(authors: list[str]):
    """Человек рядом с ботом, пустота или незнакомый бот — гейт в силе."""
    assert machine_authors.exemption(authors) is None


def test_link_gate_lets_the_bot_through(monkeypatch: pytest.MonkeyPatch):
    """Гейт связи пропускает изменение бота без тела-ответа."""
    monkeypatch.setenv("PR_BODY", "Bumps actions/checkout from 4 to 7.")
    monkeypatch.setenv("PR_AUTHOR", "dependabot[bot]")
    assert check_pr_link.main([]) == 0


def test_link_gate_still_asks_a_human(monkeypatch: pytest.MonkeyPatch):
    """Тот же текст от человека — отказ: освобождение именное."""
    monkeypatch.setenv("PR_BODY", "Bumps actions/checkout from 4 to 7.")
    monkeypatch.setenv("PR_AUTHOR", "ArtVsMark")
    assert check_pr_link.main([]) == 1


@pytest.mark.live_surface
def test_ci_passes_the_author_to_the_link_gate():
    """Живая половина: прогон передаёт гейту автора изменения."""
    ci = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    text = ci.read_text(encoding="utf-8")
    assert (
        f"{check_pr_link.AUTHOR_ENV}: ${{{{ github.event.pull_request.user.login }}}}"
        in text
    )
