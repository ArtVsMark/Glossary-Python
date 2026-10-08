"""Журнал изменений: форма фрагментов и окно выпусков (правило каталога 108).

Подделки показывают, что окно меряется и перенос дословен. Живая половина —
что настоящий ``CHANGELOG.md`` в окно укладывается, а выпуск лежит в одном месте.
"""

from pathlib import Path

import pytest

import changelog

HEAD = "# История изменений\n\nШапка журнала.\n\n"


def journal(*releases: str, tail: str = "") -> str:
    """Журнал с разделом Unreleased и выпусками в заданном порядке."""
    parts = [HEAD, "## [Unreleased]\n\n- ещё не выпущено\n\n"]
    parts += [
        f"## [{v}] — 2026-10-0{i}\n\n- запись {v}\n\n" for i, v in enumerate(releases)
    ]
    if tail:
        parts.append(tail)
    return "".join(parts).rstrip("\n") + "\n"


def test_sections_split_without_loss():
    text = journal("1.2.0", "1.1.0", tail="## Ранняя история\n\nстарое\n")
    head, sections = changelog.split_sections(text)
    assert head + "".join(sections) == text
    assert head == HEAD


def test_window_holds_its_size():
    assert changelog.window_problems(journal("1.2.0", "1.1.0", "1.0.0"), "") == []


def test_release_beyond_the_window_is_a_finding():
    problems = changelog.window_problems(journal("1.3.0", "1.2.0", "1.1.0", "1.0.0"), "")
    assert len(problems) == 1
    assert "1.0.0" in problems[0] and "--rotate" in problems[0]


def test_release_in_both_places_is_a_finding():
    archive = changelog.ARCHIVE_HEAD + "\n## [1.0.0] — 2026-10-02\n\n- запись\n"
    problems = changelog.window_problems(journal("1.1.0", "1.0.0"), archive)
    assert problems == ["выпуск и в журнале, и в архиве: 1.0.0 — у раздела одно место"]


def test_rotation_moves_the_oldest_verbatim():
    text = journal(
        "1.3.0", "1.2.0", "1.1.0", "1.0.0", tail="## Ранняя история\n\nстарое\n"
    )
    new_journal, archive = changelog.rotate(text, "")
    assert changelog.versions(new_journal) == ["1.3.0", "1.2.0", "1.1.0"]
    assert changelog.versions(archive) == ["1.0.0"]
    _, sections = changelog.split_sections(text)
    for moved in sections[-2:]:
        assert moved.rstrip("\n") in archive
    assert "Ранняя история" not in new_journal
    assert changelog.window_problems(new_journal, archive) == []


def test_rotation_puts_newer_releases_on_top_of_the_archive():
    first, archive = changelog.rotate(journal("1.3.0", "1.2.0", "1.1.0", "1.0.0"), "")
    second, archive = changelog.rotate(
        journal("1.4.0", *changelog.versions(first)), archive
    )
    assert changelog.versions(second) == ["1.4.0", "1.3.0", "1.2.0"]
    assert changelog.versions(archive) == ["1.1.0", "1.0.0"]
    assert "\n\n\n" not in archive


def test_rotation_within_the_window_changes_nothing():
    text = journal("1.2.0", "1.1.0")
    assert changelog.rotate(text, "архив") == (text, "архив")


def test_missing_journal_is_not_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(changelog, "CHANGELOG", tmp_path / "нет.md")
    with pytest.raises(changelog.NotRunError):
        changelog.check_window()


def test_rotate_command_writes_both_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    log, archive = tmp_path / "CHANGELOG.md", tmp_path / "archive.md"
    log.write_text(journal("1.3.0", "1.2.0", "1.1.0", "1.0.0"), encoding="utf-8")
    monkeypatch.setattr(changelog, "CHANGELOG", log)
    monkeypatch.setattr(changelog, "ARCHIVE", archive)
    assert changelog.main(["--rotate"]) == 0
    assert "1.0.0" in capsys.readouterr().out
    assert changelog.versions(archive.read_text("utf-8")) == ["1.0.0"]
    assert changelog.main(["--rotate"]) == 0
    assert "нечего" in capsys.readouterr().out


@pytest.mark.live_surface
def test_live_journal_keeps_its_window():
    """Настоящий журнал укладывается в окно, и выпуск не лежит в двух местах."""
    assert changelog.check_window() == []
    assert changelog.versions(changelog.CHANGELOG.read_text("utf-8"))


def test_directory_description_and_its_twin_are_not_fragments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Описание каталога на двух языках — не запись: ``README.en`` не секция."""
    for name in ("README.md", "README.en.md"):
        (tmp_path / name).write_text("# Фрагменты\n", encoding="utf-8")
    (tmp_path / "x.added.md").write_text("запись (#1)\n", encoding="utf-8")
    monkeypatch.setattr(changelog, "FRAGMENTS", tmp_path)
    fragments, problems = changelog.read_fragments()
    assert problems == []
    assert len(fragments) == 1
