"""Гейт на числа в документации.

Число, вписанное руками, устаревает молча: README уже расходился с
`.rules/bindings.json` через час после правки. Здесь проверяется третье
условие правила 127 — пропавший маркер роняет сборку, а не оставляет
последнее записанное значение выглядеть свежим.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import facts as facts_module
from glossary.loader import project_root


@pytest.fixture(scope="module")
def facts() -> dict[str, object]:
    """Факты, посчитанные из порождающих источников."""
    return facts_module.build_facts()


def test_facts_are_collected(facts: dict[str, object]):
    """Пустой сбор — ошибка входа, а не «фактов нет»."""
    assert facts["schema"] == facts_module.SCHEMA
    assert facts["repo"] == facts_module.REPO
    glossary = facts["glossary"]
    assert isinstance(glossary, dict)
    assert glossary["cards"] > 0, "карточек ноль — источник не прочитан"


def test_unmeasured_key_is_absent_not_zero(monkeypatch: pytest.MonkeyPatch):
    """Чего не измерили — того в выдаче нет.

    Ноль читался бы как измеренный ноль процентов, а это разные вещи.
    """
    monkeypatch.setattr(facts_module, "COVERAGE", Path("/нет/такого/coverage.xml"))
    assert "coverage_percent" not in facts_module.build_facts()


def test_readme_markers_match_sources(facts: dict[str, object]):
    """README совпадает с источниками, из которых числа порождены."""
    values = facts_module.marker_values(facts)
    text = facts_module.README.read_text(encoding="utf-8")
    problems = facts_module.check(text, values)
    assert not problems, "\n".join(problems)


def test_missing_marker_is_a_failure(facts: dict[str, object]):
    """Пропавший маркер — отказ, иначе сборке нечего переписывать."""
    values = facts_module.marker_values(facts)
    text = facts_module.README.read_text(encoding="utf-8")
    stripped = text.replace("<!--m:cards-->", "").replace("<!--/m:cards-->", "")
    problems = facts_module.check(stripped, values)
    assert any("cards" in p and "пропал" in p for p in problems)


def test_stale_number_is_a_failure(facts: dict[str, object]):
    """Разъехавшееся число — отказ, а не тихо устаревшая проза."""
    values = facts_module.marker_values(facts)
    text = facts_module.README.read_text(encoding="utf-8")
    spoiled = text.replace(
        "<!--m:cards-->" + values["cards"] + "<!--/m:cards-->",
        "<!--m:cards-->999999<!--/m:cards-->",
    )
    problems = facts_module.check(spoiled, values)
    assert any("cards" in p and "999999" in p for p in problems)


def test_render_repairs_a_stale_number(facts: dict[str, object]):
    """Сборка переписывает значение, а не только жалуется на него."""
    values = facts_module.marker_values(facts)
    spoiled = "текст <!--m:cards-->999999<!--/m:cards--> текст"
    repaired = facts_module.render(spoiled, values)
    assert f"<!--m:cards-->{values['cards']}<!--/m:cards-->" in repaired


def test_badges_are_shields_endpoints(facts: dict[str, object], tmp_path: Path):
    """Значки пригодны для shields.io, факты лежат рядом с ними."""
    written = facts_module.write_badges(facts, tmp_path)
    names = {path.name for path in written}
    assert "facts.json" in names, "потребитель забирает факты оттуда же, откуда значки"
    for path in written:
        if path.name == "facts.json":
            continue
        badge = json.loads(path.read_text(encoding="utf-8"))
        assert badge["schemaVersion"] == 1
        assert badge["label"] and badge["message"]


def test_badges_are_not_committed_to_main():
    """Производное, пересобираемое чаще изменений, в общей ветке не хранится."""
    ignored = (project_root() / ".gitignore").read_text(encoding="utf-8")
    assert ".github/badges/" in ignored
