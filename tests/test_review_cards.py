"""Отбор изменённых карточек для ревизора: сравнение по ``id``, а не по строкам."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import review_cards
from glossary.loader import project_root


def card(cid: str, summary: str = "s") -> dict[str, Any]:
    """Карточка с тем минимумом полей, который сравнивается."""
    return {"id": cid, "summary": {"ru": summary, "en": summary}}


def group(*cards: dict[str, Any]) -> str:
    """Текст файла группы — список карточек, как в ``data/cards/``."""
    return json.dumps(list(cards), ensure_ascii=False)


def test_new_and_edited_cards_are_found_unchanged_and_removed_are_not() -> None:
    before = review_cards.index(
        {"data/cards/a.json": group(card("x"), card("y"), card("gone"))}
    )
    after = review_cards.index(
        {
            "data/cards/a.json": group(card("x"), card("y", "правка")),
            "data/cards/b.json": group(card("z")),
        }
    )
    assert review_cards.changed(before, after) == [
        ("y", "изменена", "data/cards/a.json"),
        ("z", "новая", "data/cards/b.json"),
    ]


def test_card_moved_between_groups_unchanged_is_not_a_change() -> None:
    before = review_cards.index({"data/cards/a.json": group(card("x"))})
    after = review_cards.index({"data/cards/b.json": group(card("x"))})
    assert review_cards.changed(before, after) == []


def test_assembled_form_with_entries_is_read_too() -> None:
    text = json.dumps({"entries": [card("x")]})
    assert list(review_cards.index({"g.json": text})) == ["x"]


def test_render_names_the_cut() -> None:
    items = [(f"c{n}", "новая", "data/cards/a.json") for n in range(3)]
    text = review_cards.render(items, 2)
    assert "`c0`" in text
    assert "`c2`" not in text
    assert "…и ещё 1." in text


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 — аргументы наши
        ["git", *args],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Клон-подделка: основа с одной группой, голова с правкой и новой группой."""
    cards = tmp_path / "data" / "cards"
    cards.mkdir(parents=True)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.org")
    _git(tmp_path, "config", "user.name", "t")
    (cards / "a.json").write_text(group(card("x"), card("y")), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "основа")
    (cards / "a.json").write_text(group(card("x"), card("y", "др")), encoding="utf-8")
    (cards / "b.json").write_text(group(card("z")), encoding="utf-8")
    return tmp_path


def test_main_counts_and_writes_list(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out" / "cards.md"
    code = review_cards.main(["--base", "HEAD", "--root", str(repo), "-o", str(out)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "2"
    assert out.read_text(encoding="utf-8").splitlines() == [
        "- `y` (изменена) — `data/cards/a.json`",
        "- `z` (новая) — `data/cards/b.json`",
    ]


def test_unknown_base_is_not_run(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cards.md"
    code = review_cards.main(["--base", "deadbeef", "--root", str(repo), "-o", str(out)])
    assert code == review_cards.NOT_RUN
    assert "fetch-depth 0" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.live_surface
def test_live_tree_against_itself_has_no_changes() -> None:
    """Живая половина: дерево против своей же головы — изменений ноль.

    Рабочее дерево может нести незакоммиченную правку карточек, поэтому
    сравнивается разбор файлов головы с самим собой через ``git show HEAD``
    лишь тогда, когда дерево чистое.
    """
    root = project_root()
    if _git(root, "status", "--porcelain", "--", review_cards.CARDS):
        pytest.skip("в data/cards/ есть незакоммиченные правки")
    head = review_cards.read_head(root)
    base = review_cards.read_base(root, "HEAD", list(head))
    assert head
    assert review_cards.changed(review_cards.index(base), review_cards.index(head)) == []
