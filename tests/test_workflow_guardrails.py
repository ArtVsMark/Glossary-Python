"""Сторожа конвейера.

Имя обязательной проверки живёт в настройке защиты ветки — вне дерева, вне
ревью и вне любого прогона. Разъезд настройки и дерева не производит красного,
он производит **ожидание**, неотличимое от «проверки ещё идут». Поэтому
совпадение держится тестом, а не памятью.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from glossary.loader import project_root

CI_PATH = project_root() / ".github" / "workflows" / "ci.yml"

REQUIRED_CHECK_NAME = "check PR"
"""Имя, записанное в ruleset «Protect main» как обязательная проверка.

Значение продублировано здесь намеренно: настройка недоступна из дерева, и
единственный способ поймать её расхождение с конвейером — сверять с эталоном,
который лежит рядом с конвейером.
"""

AGGREGATOR_JOB = "check-pr"


@pytest.fixture(scope="module")
def ci() -> dict[str, Any]:
    """Разобранный конвейер."""
    document: dict[str, Any] = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    return document


def test_ci_declares_jobs(ci: dict[str, Any]):
    """Пустой конвейер — ошибка входа, а не «сторожить нечего»."""
    assert ci["jobs"], "в ci.yml нет ни одной работы"


def test_required_check_exists_with_exact_name(ci: dict[str, Any]):
    """Обязательная проверка ровно одна и названа дословно как в настройке."""
    named = [
        job_id
        for job_id, job in ci["jobs"].items()
        if job.get("name") == REQUIRED_CHECK_NAME
    ]
    assert named == [AGGREGATOR_JOB], (
        f"обязательная проверка должна быть ровно одна с именем "
        f"{REQUIRED_CHECK_NAME!r}; найдено: {named}"
    )


def test_aggregator_reaches_a_verdict_on_any_outcome(ci: dict[str, Any]):
    """Без if: always() агрегатор пропускается, а пропуск засчитывается пройденным.

    Это вторая половина правила 168 и самая дорогая: в норме такой агрегатор
    зелёный и ничего не решает, а в аварии разрешает слияние.
    """
    condition = ci["jobs"][AGGREGATOR_JOB].get("if")
    assert condition == "always()", (
        "агрегатор обязан доходить до вердикта при любом исходе соседей: "
        f"ожидалось if: always(), получено {condition!r}"
    )


def test_aggregator_covers_every_other_job(ci: dict[str, Any]):
    """Работа, не попавшая в needs, проходит мимо гейта незамеченной."""
    jobs = set(ci["jobs"]) - {AGGREGATOR_JOB}
    covered = set(ci["jobs"][AGGREGATOR_JOB]["needs"])
    missing = sorted(jobs - covered)
    assert not missing, (
        "работы вне обязательной проверки — их падение не остановит слияние: "
        + ", ".join(missing)
    )
    assert not covered - jobs, "в needs указана несуществующая работа"


def test_matrix_job_names_never_match_the_required_name(ci: dict[str, Any]):
    """Имена ячеек матрицы меняются вместе с составом версий.

    Попав в список обязательных, такое имя ломает связь при первом же
    изменении матрицы — и ломает молча.
    """
    for job_id, job in ci["jobs"].items():
        if job_id == AGGREGATOR_JOB:
            continue
        name = str(job.get("name", ""))
        assert name != REQUIRED_CHECK_NAME, (
            f"работа {job_id} претендует на имя обязательной проверки"
        )


def test_aggregator_has_no_matrix(ci: dict[str, Any]):
    """У обязательной проверки одно имя, а матрица порождает несколько."""
    assert "strategy" not in ci["jobs"][AGGREGATOR_JOB], (
        "матрица у обязательной проверки даёт несколько имён вместо одного"
    )


def test_every_workflow_has_a_manual_button():
    """События теряются: у автоматики обязана быть ручная кнопка (правило 104)."""
    workflows = sorted((project_root() / ".github" / "workflows").glob("*.yml"))
    assert workflows, "прогонов не найдено — проверять нечего"
    without: list[str] = []
    for path in workflows:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        # `on` разбирается YAML-ом как булево True — это ключ расписания.
        triggers = document.get("on", document.get(True, {}))
        if "workflow_dispatch" not in triggers:
            without.append(path.name)
    assert not without, "прогоны без ручного запуска: " + ", ".join(without)
