"""Гейт на числа в документации.

Число, вписанное руками, устаревает молча: README уже расходился с
`.rules/bindings.json` через час после правки. Здесь проверяется третье
условие правила 127 — пропавший маркер роняет сборку, а не оставляет
последнее записанное значение выглядеть свежим.

Размеченных файлов больше одного, и это меняет форму проверки: каждый несёт
своё подмножество чисел, поэтому «маркер пропал» считается по всем файлам
сразу, а «значение разъехалось» — по каждому отдельно, с именем файла в
сообщении.
"""

import json
import re
from pathlib import Path

import pytest

import facts as facts_module
import version as version_module
from glossary import contracts
from glossary.loader import project_root


@pytest.fixture(scope="module")
def facts() -> dict[str, object]:
    """Факты, посчитанные из порождающих источников."""
    return facts_module.build_facts()


def test_facts_are_collected(facts: dict[str, object]):
    """Пустой сбор — ошибка входа, а не «фактов нет»."""
    assert facts["schema"] == facts_module.FACTS_SCHEMA
    assert facts["producer"] == contracts.PRODUCER
    glossary = facts["glossary"]
    assert isinstance(glossary, dict)
    assert glossary["cards"] > 0, "карточек ноль — источник не прочитан"


def test_unmeasured_key_is_absent_not_zero(monkeypatch: pytest.MonkeyPatch):
    """Чего не измерили — того в выдаче нет.

    Ноль читался бы как измеренный ноль процентов, а это разные вещи.
    """
    monkeypatch.setattr(facts_module, "COVERAGE", Path("/нет/такого/coverage.xml"))
    assert "coverage_percent" not in facts_module.build_facts()


def test_contract_minimum_is_present(facts: dict[str, object]):
    """Обязательный минимум договора 1.3: без него витрина файл не читает."""
    assert facts["repo"] == contracts.PRODUCER
    assert re.fullmatch(r"[0-9a-f]{40}", str(facts["commit"])), "нужен полный SHA"
    ci = facts["ci"]
    assert isinstance(ci, dict)
    workflow = project_root() / ".github" / "workflows" / ci["workflow"]
    assert workflow.exists(), "статус спрашивают у прогона, которого нет"


INDICATORS = ("version", "release", "tests", "python", "checks_per_pr")
"""Показатели договора, у которых значение или причина есть всегда.

Покрытия здесь нет: без отчёта оно «не измерено», а не «предмета нет», и его
отсутствие проверяет ``test_unmeasured_key_is_absent_not_zero``.
"""


@pytest.mark.parametrize("indicator", INDICATORS)
def test_every_indicator_has_value_or_reason(facts: dict[str, object], indicator: str):
    """Третьего нет: пустой показатель снаружи неотличим от «не дошли»."""
    reasons = facts.get("none", {})
    assert isinstance(reasons, dict)
    has_value = indicator in facts
    has_reason = bool(reasons.get(indicator))
    assert has_value != has_reason, f"{indicator}: значение и причина — ровно одно"


def test_checks_name_the_required_one(facts: dict[str, object]):
    """Перечень проверок взят из прогона: обязательная проверка в нём есть."""
    checks = facts["checks_per_pr"]
    assert isinstance(checks, dict)
    assert checks["count"] == len(checks["names"])
    assert "check PR" in checks["names"]


def test_matrix_expands_into_one_check_per_value():
    """Площадка ставит по проверке на значение матрицы и подставляет его в имя."""
    job = {
        "name": "Тесты (Python ${{ matrix.python-version }})",
        "strategy": {"matrix": {"python-version": ["3.11", "3.12"]}},
    }
    assert facts_module._job_names("tests", job) == [
        "Тесты (Python 3.11)",
        "Тесты (Python 3.12)",
    ]
    assert facts_module._job_names("lint", {}) == ["lint"]


def test_second_matrix_axis_is_refused_not_miscounted():
    """Две оси без разбора комбинаций дали бы неверное число — отказ честнее."""
    job = {"strategy": {"matrix": {"python-version": ["3.11"], "os": ["a", "b"]}}}
    with pytest.raises(ValueError, match="матрица"):
        facts_module._job_names("tests", job)


def test_tests_are_counted_from_sources(facts: dict[str, object]):
    """Модулей столько, сколько файлов собирает pytest; функций не меньше."""
    tests = facts["tests"]
    assert isinstance(tests, dict)
    modules = list((project_root() / "tests").glob("test_*.py"))
    assert tests["modules"] == len(modules)
    assert tests["functions"] >= tests["modules"]


def test_python_section_and_old_name_share_one_source(facts: dict[str, object]):
    """Прежнее имя не удалено и не расходится с новым."""
    python = facts["python"]
    assert isinstance(python, dict)
    assert python["supported"] == facts["python_versions"]
    assert python["os"], "ОС прогона тестов не названа"
    assert python["experimental"], "предварительная версия не названа"
    assert not set(python["experimental"]) & set(python["supported"])


def test_platform_names_the_commit(monkeypatch: pytest.MonkeyPatch):
    """В прогоне коммит называет площадка, а не checkout."""
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    assert facts_module._commit() == "a" * 40


def test_first_tag_lifts_the_reason(monkeypatch: pytest.MonkeyPatch):
    """Причина «выпуска нет» снимается первым тегом, без правки кода."""
    tagged = version_module.Version("v0.1.0", "0.1", "0.1.41")
    monkeypatch.setattr(version_module, "version", lambda: tagged)
    built = facts_module.build_facts()
    assert built["release"] == "0.1", "договор 1.3: выпуск — серия X.Y, а не тег"
    assert built["version"] == "0.1.41"
    assert built["version"].startswith(built["release"] + ".")
    assert "none" not in built


def test_untagged_clone_gives_reasons_not_numbers(monkeypatch: pytest.MonkeyPatch):
    """Без тега версия недостоверна: причина, а не правдоподобное «0.1.N»."""
    monkeypatch.setattr(version_module, "version", lambda: None)
    built = facts_module.build_facts()
    assert "version" not in built and "release" not in built
    assert set(built["none"]) == {"version", "release"}


def test_release_and_version_badges_follow_the_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Значок выпуска говорит «X.Y», значок версии — полную версию."""
    tagged = version_module.Version("v0.1.0", "0.1", "0.1.41")
    monkeypatch.setattr(version_module, "version", lambda: tagged)
    facts_module.write_badges(facts_module.build_facts(), tmp_path)
    release = json.loads((tmp_path / "release.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert (release["message"], current["message"]) == ("0.1", "0.1.41")


def test_git_refusal_is_the_third_outcome(monkeypatch: pytest.MonkeyPatch):
    """Git не ответил — факты не посчитаны, а не «расхождение»."""

    def refuse(*_: str) -> str:
        raise OSError("git не найден")

    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(facts_module, "_git", refuse)
    assert facts_module.main(["--json"]) == facts_module.NOT_RUN


@pytest.fixture(scope="module")
def texts() -> dict[str, str]:
    """Содержимое всех размеченных файлов репозитория."""
    return {p.name: p.read_text(encoding="utf-8") for p in facts_module.MARKED}


def test_every_marked_file_is_read(texts: dict[str, str]):
    """Пустой набор файлов дал бы зелёный гейт без единой проверки."""
    assert texts, "ни один размеченный файл не прочитан"
    assert {"README.md", "CLAUDE.md"} <= texts.keys()


def test_markers_match_sources(facts: dict[str, object], texts: dict[str, str]):
    """Документация совпадает с источниками, из которых числа порождены."""
    values = facts_module.marker_values(facts)
    problems = facts_module.check(texts, values)
    assert not problems, "\n".join(problems)


def test_missing_marker_is_a_failure(facts: dict[str, object], texts: dict[str, str]):
    """Пропавший маркер — отказ, иначе сборке нечего переписывать."""
    values = facts_module.marker_values(facts)
    stripped = {
        name: text.replace("<!--m:cards-->", "").replace("<!--/m:cards-->", "")
        for name, text in texts.items()
    }
    problems = facts_module.check(stripped, values)
    assert any("cards" in p and "не стоит ни в одном файле" in p for p in problems)


def test_marker_surviving_in_another_file_is_not_a_failure(
    facts: dict[str, object], texts: dict[str, str]
):
    """Файл несёт своё подмножество чисел — отсутствие в одном не отказ."""
    values = facts_module.marker_values(facts)
    problems = facts_module.check({"README.md": texts["README.md"]}, values)
    assert not any("cards" in p for p in problems)


def test_stale_number_in_any_file_is_a_failure(facts: dict[str, object]):
    """Разъехавшееся число — отказ, а не тихо устаревшая проза; файл назван."""
    values = facts_module.marker_values(facts)
    spoiled = {"CLAUDE.md": "<!--m:cards-->999999<!--/m:cards-->"}
    problems = facts_module.check(spoiled, values)
    assert any("cards" in p and "999999" in p and "CLAUDE.md" in p for p in problems)


def test_unknown_marker_is_a_failure():
    """Маркер без факта — обещание, которое сборке нечем выполнить."""
    text = "<!--m:invented-->7<!--/m:invented-->"
    problems = facts_module.check({"README.md": text}, {})
    assert any("invented" in p and "фактов для него нет" in p for p in problems)


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
