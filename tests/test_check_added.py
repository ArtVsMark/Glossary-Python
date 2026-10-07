"""Сверка поля ``added`` с замером языка по снимкам инвентаря."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import check_added
from glossary.loader import project_root


def dump(version: str, *qualnames: str) -> dict[str, Any]:
    """Выгрузка инвентаря одной версии."""
    return {
        "python_version": version,
        "items": [
            {"qualname": name, "module": "m", "kind": "function"} for name in qualnames
        ],
    }


def card(cid: str, added: str, title: str | None = None) -> dict[str, Any]:
    """Карточка с тем минимумом полей, который читает сверка."""
    name = title or cid
    return {"id": cid, "added": added, "title": {"ru": name, "en": name}}


SNAPSHOTS = [
    dump("3.12", "old.f", "mid.g"),
    dump("3.11", "old.f"),
    dump("3.13", "old.f", "mid.g", "new.h"),
]
"""Порядок перепутан намеренно: младшая версия определяется сортировкой."""


@pytest.mark.parametrize(
    ("cid", "added"),
    [("old.f", "<3.0"), ("old.f", "3.11"), ("mid.g", "3.12"), ("new.h", "3.13")],
)
def test_added_matching_the_measurement_passes(cid: str, added: str):
    assert check_added.findings([card(cid, added)], SNAPSHOTS) == []


@pytest.mark.parametrize(
    ("cid", "added", "seen"),
    [("mid.g", "3.11", "3.12"), ("mid.g", "3.13", "3.12"), ("new.h", "<3.0", "3.13")],
)
def test_added_against_the_measurement_is_a_finding(cid: str, added: str, seen: str):
    assert check_added.findings([card(cid, added)], SNAPSHOTS) == [
        check_added.Finding(cid, added, seen)
    ]


def test_title_is_matched_without_call_parentheses():
    entry = card("some-slug", "3.11", title="mid.g()")
    assert check_added.findings([entry], SNAPSHOTS) == [
        check_added.Finding("some-slug", "3.11", "3.12")
    ]


def test_card_outside_the_inventory_is_skipped():
    assert check_added.findings([card("concept", "3.13")], SNAPSHOTS) == []


def test_name_seen_later_than_it_appeared_is_excused():
    late = next(iter(check_added.SEEN_LATER))
    snapshots = [dump("3.11"), dump("3.13", late)]
    assert check_added.findings([card(late, "3.12")], snapshots) == []


def test_one_snapshot_is_not_a_verdict(tmp_path: Path):
    path = tmp_path / "inventory-3.14.json"
    path.write_text(json.dumps(dump("3.14", "old.f")), encoding="utf-8")
    assert check_added.main([str(path)]) == check_added.NOT_RUN


def test_findings_fail_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    paths = []
    for snapshot in SNAPSHOTS:
        path = tmp_path / f"inventory-{snapshot['python_version']}.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        paths.append(str(path))
    data = tmp_path / "glossary.json"
    data.write_text(json.dumps([card("mid.g", "3.11")]), encoding="utf-8")
    assert check_added.main([*paths, "--data", str(data)]) == 1
    assert "mid.g: added 3.11, а впервые видно в 3.12" in capsys.readouterr().out


@pytest.mark.live_surface
def test_matrix_run_checks_the_cards():
    """Прогон значков сверяет карточки со снимками, которые сам же снял."""
    workflow = project_root() / ".github" / "workflows" / "badges.yml"
    jobs = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]
    runs = [
        str(step.get("run", "")) for job in jobs.values() for step in job.get("steps", [])
    ]
    assert any(
        "scripts/check_added.py" in run and "inventory/inventory-*.json" in run
        for run in runs
    )


@pytest.mark.live_surface
def test_excused_names_exist_in_the_cards():
    """Оправдание без карточки — мёртвая строка, которая заглушит будущую находку."""
    raw = json.loads(
        (project_root() / "data" / "glossary.json").read_text(encoding="utf-8")
    )
    entries = raw["entries"] if isinstance(raw, dict) else raw
    known = {name for entry in entries for name in check_added.names(entry)}
    assert set(check_added.SEEN_LATER) <= known
