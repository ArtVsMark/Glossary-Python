"""Сторожа конвейера.

Имя обязательной проверки живёт в настройке защиты ветки — вне дерева, вне
ревью и вне любого прогона. Разъезд настройки и дерева не производит красного,
он производит **ожидание**, неотличимое от «проверки ещё идут». Поэтому
совпадение держится тестом, а не памятью.
"""

from __future__ import annotations

import json
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


def _triggers(path: Path) -> dict[str, Any]:
    """Триггеры прогона.

    Ключ ``on`` разбирается YAML-ом как булево ``True``: в YAML 1.1 это одно из
    написаний истины. Читать его надо обоими способами, иначе сторож молча
    решит, что триггеров нет вовсе.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    triggers: dict[str, Any] = document.get("on", document.get(True, {}))
    return triggers


READY_FOR_REVIEW = "ready_for_review"


def pull_request_types_problem(name: str, triggers: dict[str, Any]) -> str | None:
    """Что не так с набором событий ``pull_request``; ``None`` — всё в порядке.

    Вынесено функцией, чтобы сторожа можно было прогнать по предмету, который
    он ОБЯЗАН отвергнуть, а не только по зелёному дереву (правило 140).

    Args:
        name: Имя прогона — оно попадает в текст находки (правило 158).
        triggers: Разобранное значение ключа ``on``.

    Returns:
        Готовая находка либо ``None``.
    """
    if "pull_request" not in triggers:
        return None
    spec = triggers["pull_request"]
    if not isinstance(spec, dict) or not spec.get("types"):
        return (
            f"{name}: прогон отвечает на pull_request, но набор событий не назван. "
            "Умолчание площадки — opened, synchronize, reopened — не включает "
            f"{READY_FOR_REVIEW}"
        )
    if READY_FOR_REVIEW not in spec["types"]:
        return (
            f"{name}: в наборе событий нет {READY_FOR_REVIEW} — снятие черновика "
            "останется без проверок"
        )
    return None


def test_pull_request_event_types_are_named_explicitly():
    """Умолчание площадки не включает снятие черновика (правило 104).

    Типы по умолчанию — ``opened``, ``synchronize``, ``reopened``. Изменение,
    открытое черновиком, проверок при готовности не получает, и добудиться их
    можно только отправкой коммита — то есть пустышкой ради перезапуска,
    которая остаётся в истории навсегда.

    Вторая причина назвать набор явно: пропуск черновиков (``if:
    !github.event.pull_request.draft``) — обычный приём, и вместе с умолчанием
    он оставляет изменение БЕЗ ЕДИНОЙ проверки: ни при создании, ни при
    готовности. Отказ при этом выглядит не красным, а ожиданием.
    """
    problems = [
        problem
        for path in sorted(WORKFLOWS.glob("*.yml"))
        if (problem := pull_request_types_problem(path.name, _triggers(path)))
    ]
    assert not problems, "\n".join(problems)


def test_workflow_reacting_to_pull_request_exists():
    """У сторожа должен быть предмет: проверять нечего — это не сторож (075)."""
    reacting = [
        path.name
        for path in sorted(WORKFLOWS.glob("*.yml"))
        if "pull_request" in _triggers(path)
    ]
    assert reacting, "ни один прогон не отвечает на pull_request"


def test_types_left_to_the_default_are_rejected():
    """Предмет, который сторож обязан отвергнуть: `pull_request:` без набора."""
    assert pull_request_types_problem("ci.yml", {"pull_request": None})
    assert pull_request_types_problem("ci.yml", {"pull_request": {}})


def test_types_without_ready_for_review_are_rejected():
    problem = pull_request_types_problem(
        "ci.yml", {"pull_request": {"types": ["opened", "synchronize"]}}
    )
    assert problem and READY_FOR_REVIEW in problem


def test_workflow_without_pull_request_is_not_a_problem():
    """Прогон по расписанию про черновики ничего не обязан знать."""
    assert pull_request_types_problem("badges.yml", {"schedule": [], "push": {}}) is None


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


# --------------------------------------------------------------------------- #
# Комплексная задача ведётся пересчётом, а не прозой (правило каталога 028)
# --------------------------------------------------------------------------- #

INBOX_PATH = WORKFLOWS / "rules-inbox.yml"


@pytest.mark.live_surface
def test_complex_task_is_recomputed_not_hand_edited():
    """Состояние задачи «Входящие» выводится, а не правится руками.

    Правило 028 требует у комплексной задачи чек-лист — потому что состояние,
    записанное прозой, приходится вычислять чтением и сверкой с историей. Здесь
    вычислять нечего: тело задачи пересобирает действие каталога из
    ``.rules/bindings.json`` по расписанию, и руками его никто не трогает.

    Утверждение держится тем, что прогон существует, ходит сам и имеет право
    писать задачи. Без любого из трёх ответ «пересчитывается» был бы обещанием.
    """
    assert INBOX_PATH.exists(), f"прогона входящих нет: {INBOX_PATH}"
    document = yaml.safe_load(INBOX_PATH.read_text(encoding="utf-8"))
    triggers = document.get("on", document.get(True, {}))
    assert "schedule" in triggers, (
        "у прогона входящих нет расписания: тело задачи перестало бы "
        "пересчитываться, и состояние снова пришлось бы вести прозой"
    )
    assert document["permissions"].get("issues") == "write", (
        "прогону входящих нечем писать задачу — пересчёт был бы обещанием"
    )


# --------------------------------------------------------------------------- #
# След отказа лежит в сводке прогона, а не только в логах (правило 151)
# --------------------------------------------------------------------------- #

AGGREGATOR = re.compile(
    r"- name: Свести вердикты обязательных работ.*?python3 - <<'PY'\n"
    r"(?P<body>.*?)\n\s+PY",
    re.DOTALL,
)
INDENT = 10
"""Насколько встроенный разбор отступлен внутри YAML."""


def aggregator_source() -> str:
    """Тело агрегатора, вынутое из прогона.

    Копия здесь не заводится намеренно: она разошлась бы с оригиналом первой же
    правкой, и набор стерёг бы текст, которого в конвейере уже нет.

    Returns:
        Исходник встроенного разбора; пустая строка — его в прогоне нет.
    """
    found = AGGREGATOR.search(CI_PATH.read_text(encoding="utf-8"))
    if found is None:
        return ""
    return "\n".join(line[INDENT:] for line in found.group("body").splitlines())


def verdict(
    needs: dict[str, Any], report: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, str]:
    """Прогнать агрегатор и вернуть код возврата со следом в сводке.

    Args:
        needs: Исходы обязательных работ.
        report: Файл сводки прогона.
        monkeypatch: Подмена окружения на время прогона.

    Returns:
        Пара «код возврата, что легло в сводку».
    """
    monkeypatch.setenv("NEEDS", json.dumps(needs))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(report))
    source = compile(aggregator_source(), "<агрегатор>", "exec")
    code = 0
    try:
        # S102: исполняется собственный конвейер проекта, вынутый из ci.yml, —
        # копия его текста в наборе разошлась бы с оригиналом (правило 090).
        exec(source, {"__name__": "__main__"})  # noqa: S102
    except SystemExit as stop:
        code = 1 if stop.code else 0
    return code, report.read_text(encoding="utf-8") if report.exists() else ""


@pytest.mark.live_surface
def test_aggregator_is_embedded_in_the_pipeline():
    """У гейта есть предмет: разбора нет — стеречь нечего (правило 075)."""
    assert aggregator_source(), "встроенного разбора в ci.yml не нашлось"


def test_failure_names_the_job_in_the_run_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Тот самый предмет: чинящий узнаёт виновную работу, не открывая логов."""
    code, written = verdict(
        {"tests": {"result": "failure"}, "data": {"result": "success"}},
        tmp_path / "summary.md",
        monkeypatch,
    )
    assert code == 1
    assert "не прошли" in written
    assert "`tests` | failure" in written, "сводка не называет виновную работу"


def test_skipped_job_is_a_failure_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Пропущенное засчитывать за пройденное нельзя — ради этого if: always()."""
    code, written = verdict(
        {"tests": {"result": "skipped"}}, tmp_path / "summary.md", monkeypatch
    )
    assert code == 1
    assert "skipped" in written


def test_green_run_also_leaves_a_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """След пишется всегда: сводка, появляющаяся лишь на красном, — сигнал сама."""
    code, written = verdict(
        {"tests": {"result": "success"}}, tmp_path / "summary.md", monkeypatch
    )
    assert code == 0
    assert "Всё зелено" in written


def test_empty_needs_says_so_in_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Пустой вход — ошибка входа, и в сводке это видно (правило 075)."""
    code, written = verdict({}, tmp_path / "summary.md", monkeypatch)
    assert code == 1
    assert "не отработал" in written
