"""Сторожа конвейера.

Имя обязательной проверки живёт в настройке защиты ветки — вне дерева, вне
ревью и вне любого прогона. Разъезд настройки и дерева не производит красного,
он производит **ожидание**, неотличимое от «проверки ещё идут». Поэтому
совпадение держится тестом, а не памятью.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from glossary.loader import project_root

WORKFLOWS = project_root() / ".github" / "workflows"
CI_PATH = WORKFLOWS / "ci.yml"
PAGES_PATH = WORKFLOWS / "pages.yml"

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


def test_cancelling_concurrency_group_names_the_commit(ci: dict[str, Any]):
    """Группа, отменяющая прогон, обязана называть проверяемый коммит.

    Без коммита в имени прогоны на разных коммитах одного изменения попадают в
    одну группу и вытесняют друг друга: результат обязательной проверки для
    актуальной головы не появляется вовсе, и слияние встаёт при зелёных
    проверках — отказ, который выглядит как «проверки ещё идут».
    """
    concurrency = ci["concurrency"]
    if not concurrency.get("cancel-in-progress"):
        return
    group = str(concurrency["group"])
    assert "head.sha" in group or "github.sha" in group, (
        "группа с отменой обязана включать коммит, а не только ссылку: " + group
    )


def test_pages_does_not_depend_on_an_out_of_tree_setting():
    """Публикация витрины не должна зависеть от переключателя в настройках.

    Репозиторий с выключенным Pages даёт «Get Pages site failed: Not Found»,
    и прогон краснеет молча: у него нет ни обязательного статуса, ни адресата.
    Красным он простоял четыре запуска подряд, пока бейдж в README утверждал,
    что витрина публикуется.
    """
    pages = yaml.safe_load(PAGES_PATH.read_text(encoding="utf-8"))
    steps = pages["jobs"]["deploy"]["steps"]
    configure = [s for s in steps if "configure-pages" in str(s.get("uses", ""))]
    assert configure, "шаг configure-pages не найден — публиковать нечем"
    assert configure[0].get("with", {}).get("enablement") is True, (
        "configure-pages обязан нести enablement: true, иначе прогон зависит "
        "от настройки, которой нет в дереве и которую никто не проверяет"
    )


def test_every_workflow_has_a_manual_button():
    """События теряются: у автоматики обязана быть ручная кнопка (правило 104)."""
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    assert workflows, "прогонов не найдено — проверять нечего"
    without: list[str] = []
    for path in workflows:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        # `on` разбирается YAML-ом как булево True — это ключ расписания.
        triggers = document.get("on", document.get(True, {}))
        if "workflow_dispatch" not in triggers:
            without.append(path.name)
    assert not without, "прогоны без ручного запуска: " + ", ".join(without)


BADGES_PATH = WORKFLOWS / "badges.yml"


@pytest.fixture(scope="module")
def badges() -> dict[str, Any]:
    """Разобранный публикующий прогон."""
    document: dict[str, Any] = yaml.safe_load(BADGES_PATH.read_text(encoding="utf-8"))
    return document


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def test_badges_publish_objections(badges: dict[str, Any]):
    """Обратный поток к источнику держится прогоном, а не обещанием.

    Замечания публикуются рядом со значками: список из четырёхсот
    идентификаторов, перенесённый руками, не выживает ни одной итерации.
    Если шаг исчезнет, потребитель будет читать вчерашний файл и не узнает
    об этом — поэтому шаг сторожится.
    """
    commands = " ".join(step.get("run", "") for step in _steps(badges))
    assert "glossary objections" in commands, (
        "badges.yml перестал собирать замечания — источнику нечего читать"
    )
    assert "objections.json" in commands


def test_badges_publish_completeness(badges: dict[str, Any]):
    """Полнота публикуется рядом с замечаниями.

    Она отвечает на другой вопрос — не «эту карточку поправить», а «эту
    карточку написать», — и без публикации остаётся числом в консоли,
    которое никто не увидит.
    """
    commands = " ".join(step.get("run", "") for step in _steps(badges))
    assert "glossary completeness" in commands
    assert "completeness-report.json" in commands


def test_badges_publish_facts_next_to_objections(badges: dict[str, Any]):
    """Оба контракта уезжают одним прогоном и лежат в одном месте."""
    commands = " ".join(step.get("run", "") for step in _steps(badges))
    assert "facts.py --badges" in commands
    assert ".github/badges" in commands


def _versions(workflow: dict[str, Any], job: str) -> list[str]:
    return [str(v) for v in workflow["jobs"][job]["strategy"]["matrix"]["python-version"]]


def test_badges_publish_what_changed_between_versions(badges: dict[str, Any]):
    """Разность версий публикуется, иначе её никто не увидит."""
    commands = " ".join(step.get("run", "") for step in _steps(badges))
    assert "whatsnew.py" in commands
    assert "whatsnew.json" in commands


def test_inventory_is_taken_on_every_tested_version(
    ci: dict[str, Any], badges: dict[str, Any]
):
    """Инвентарь снимается ровно на тех версиях, на которых мы проверяемся.

    Разойдись эти списки — и мы либо мерили бы полноту на версии, которую не
    тестируем, либо молча теряли бы разность между соседними: пропуск версии
    в середине превращает «что появилось в 3.13» в «что появилось за две
    версии», и результат выглядит правдоподобно.
    """
    assert _versions(badges, "inventory") == _versions(ci, "tests")


def test_preview_version_never_blocks_publication(badges: dict[str, Any]):
    """Предварительная версия своё падение показывает, но публикацию не роняет.

    Release candidate — не то, ради чего останавливают выпуск. Но зависимость
    объявлена: публикация дожидается результата, иначе гонка отдала бы
    whatsnew.json без предварительной версии через раз.
    """
    preview = badges["jobs"]["preview"]
    assert preview["continue-on-error"] is True
    assert "preview" in badges["jobs"]["publish"]["needs"]


def test_prerelease_is_allowed_only_where_it_is_expected(badges: dict[str, Any]):
    """Обязательная матрица не должна тихо переехать на release candidate."""
    required = _steps({"jobs": {"inventory": badges["jobs"]["inventory"]}})
    assert not [s for s in required if s.get("with", {}).get("allow-prereleases")]
    preview = _steps({"jobs": {"preview": badges["jobs"]["preview"]}})
    assert [s for s in preview if s.get("with", {}).get("allow-prereleases")]


def _published_by_workflow(workflow: dict[str, Any]) -> set[str]:
    """Имена файлов, которые прогон кладёт в каталог значков сам."""
    written: set[str] = set()
    for step in _steps(workflow):
        for match in re.finditer(r"\.github/badges/([\w.-]+)\.json", step.get("run", "")):
            written.add(match.group(1))
    return written


def test_contract_names_never_collide_with_badge_names(badges: dict[str, Any]):
    """Контракт не смеет называться так же, как значок.

    Это уже случилось: файл полноты глоссария опубликовали под именем
    `coverage.json`, где лежит shields-эндпоинт покрытия кода тестами. Файл
    затёрся, значок соседа сломался, прогон остался зелёным — потому что
    записать файл поверх другого ошибкой не является.

    Слово «покрытие» в экосистеме занято тестами; полнота глоссария — другое
    число, и имя у неё другое.

    Сверка идёт с заповедником имён, а не со списком записанного: значок
    покрытия появляется только при наличии ``coverage.xml``, и сторож,
    смотрящий на результат прогона, пропустил бы столкновение там, где отчёта
    о покрытии нет. Ровно это он и сделал при первой проверке красным.
    """
    facts = pytest.importorskip("facts")
    collisions = set(facts.BADGE_NAMES) & _published_by_workflow(badges)
    assert not collisions, "прогон пишет поверх значка: " + ", ".join(sorted(collisions))


def test_test_coverage_badge_survives_publication(badges: dict[str, Any]):
    """Значок покрытия тестами — стандартный, его читают снаружи."""
    assert "coverage" not in _published_by_workflow(badges)


def test_badge_namespace_covers_everything_written():
    """Заповедник имён не должен отставать от того, что пишется.

    Иначе новый значок появится вне списка, и сторож перестанет видеть
    столкновение с ним — тихо, потому что сравнивать будет не с чем.
    """
    facts = pytest.importorskip("facts")
    with tempfile.TemporaryDirectory() as tmp:
        written = {
            path.stem for path in facts.write_badges(facts.build_facts(), Path(tmp))
        }
    assert written - {"facts"} <= set(facts.BADGE_NAMES)
