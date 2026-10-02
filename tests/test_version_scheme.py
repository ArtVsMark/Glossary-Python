"""Версия по схеме семьи: тег ``vX.Y.0`` плюс принятые изменения.

Разбор проверяется на подделанной истории: что номер изменения находится в
обеих формах темы, склейки и следы механизмов не считаются, а без тега ответ —
третий исход, а не правдоподобное число.
"""

from __future__ import annotations

import pytest

import version as version_module


def test_change_numbers_come_from_both_subject_forms():
    """Уплотнение и обычное слияние ведут к одному множеству номеров."""
    lines = [
        "ci: Bump actions/setup-python from 6 to 7 (#8)",
        "Merge pull request #50 from ArtVsMark/claude/facts-contract-1-2",
        "feat(facts): facts.json отвечает договору (#50)",
        "fix: внутренний коммит ветки",
    ]
    assert version_module.pr_numbers(lines) == {"8", "50"}


@pytest.mark.parametrize(
    ("subject", "counted"),
    [
        ("chore(ci): обновить значки, факты, замечания и полноту [skip ci]", False),
        ("Merge branch 'main' of github.com:ArtVsMark/Glossary-Python", False),
        ("Merge remote-tracking branch 'origin/main'", False),
        ("build: настроить тулинг разработки", True),
    ],
)
def test_unnumbered_commit_is_counted_unless_mechanism_or_sync(
    subject: str, counted: bool
):
    """Прямой толчок реален; след механизма и склейка — нет."""
    assert version_module.countable_unnumbered(subject) is counted


def test_accepted_changes_do_not_double_count(monkeypatch: pytest.MonkeyPatch):
    """Изменение, попавшее в историю дважды, считается один раз."""
    whole = [
        "Merge pull request #12 from x",
        "feat: работа (#12)",
        "fix: внутренний коммит ветки",
        "docs: прямой толчок",
    ]
    first_parent_lines = ["Merge pull request #12 from x", "docs: прямой толчок"]

    def fake(_: str, *, first_parent: bool = False) -> list[str]:
        return first_parent_lines if first_parent else whole

    monkeypatch.setattr(version_module, "subjects", fake)
    assert version_module.accepted_since("v0.1.0..HEAD") == 2


@pytest.mark.parametrize(
    ("tag", "valid"),
    [("v0.1.0", True), ("v1.6.0", True), ("v1.0.1", False), ("v1.0.0-rc", False)],
)
def test_release_tag_is_strictly_x_y_zero(tag: str, valid: bool):
    """Патч-тегов схема не знает: тег выпуска — только ``vX.Y.0``."""
    assert bool(version_module.TAG_RE.match(tag)) is valid


def test_version_is_tag_plus_accepted(monkeypatch: pytest.MonkeyPatch):
    """Полная версия — выпуск тега и число принятых после него."""
    monkeypatch.setattr(version_module, "latest_tag", lambda: "v0.1.0")
    monkeypatch.setattr(version_module, "accepted_since", lambda _: 41)
    assert version_module.version() == version_module.Version("v0.1.0", "0.1", "0.1.41")


def test_no_tag_is_the_third_outcome(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Без тега — исход 2 и слова, а не «0.1.0»."""
    monkeypatch.setattr(version_module, "latest_tag", lambda: None)
    assert version_module.main([]) == version_module.NOT_RUN
    assert "тега выпуска" in capsys.readouterr().err


def test_release_flag_prints_x_y(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """``--release`` отвечает выпуском, без счётчика."""
    tagged = version_module.Version("v0.1.0", "0.1", "0.1.41")
    monkeypatch.setattr(version_module, "version", lambda: tagged)
    assert version_module.main(["--release"]) == 0
    assert capsys.readouterr().out.strip() == "0.1"
