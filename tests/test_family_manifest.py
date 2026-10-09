"""Манифест семьи: форма контракта ``family`` 1.1 и номер формы из выгрузки."""

import json
from pathlib import Path

import pytest

import family_manifest
import version
from glossary.delivery import FORM

FORM_KEYS = {"schema": str, "project": str, "gives": dict, "takes": list}
"""Ключи манифеста и их тип — как их судит ``family.изъян_формы`` каталога."""


def test_manifest_has_the_family_form() -> None:
    doc = family_manifest.manifest({"tag": "v1.4.0", "sha": "a" * 40})
    for key, kind in FORM_KEYS.items():
        assert isinstance(doc[key], kind), key
    assert doc["schema"].split(".")[0] == "1"
    assert doc["release"] == {"tag": "v1.4.0", "sha": "a" * 40}
    assert all(reason.strip() for reason in doc["skips"].values())


def test_form_number_is_read_not_copied() -> None:
    """Номер формы — тот, что отдаёт выгрузка, а не вторая копия (049)."""
    assert family_manifest.manifest(None)["gives"] == {"glossary-form": FORM}


def test_no_release_yet_is_null_not_invented(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(version, "latest_tag", lambda: None)
    out = tmp_path / "contracts.json"
    assert family_manifest.main(["-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["release"] is None


def test_unreadable_tag_commit_is_not_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(version, "latest_tag", lambda: "v9.9.0")
    monkeypatch.setattr(version, "git", lambda *_: None)
    out = tmp_path / "contracts.json"
    assert family_manifest.main(["-o", str(out)]) == family_manifest.NOT_RUN
    assert not out.exists()


@pytest.mark.live_surface
def test_live_release_is_a_tag_of_this_tree() -> None:
    """Живая половина: выпуск манифеста — настоящий тег дерева и его коммит."""
    rel = family_manifest.release()
    if rel is None:
        pytest.skip("клон без тегов — выпуска не видно")
    assert version.TAG_RE.match(rel["tag"])
    assert len(rel["sha"]) == 40
