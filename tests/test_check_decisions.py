"""Запись решения называет отвергнутое: правило каталога 161.

Набор держит две разные вещи. **Разбор** — чистая функция над текстом, и её
проверяют предметом, который она обязана отвергнуть: записью без обязательной
части. **Утверждение о живом документе** — что планка не отстала от него —
проверяется отдельно и своими словами (правило 146).

Планка тут особая: она освобождает, а не ограничивает, и потому у неё своя
беда. Отставшая планка тихо освобождает переименованную запись, и требование
перестаёт действовать там, где уже действовало. Этот случай прогоняется явно.
"""

import json
import subprocess
from pathlib import Path

import pytest

import check_decisions as decisions
from glossary.loader import project_root

BASELINE_PATH = project_root() / decisions.BASELINE

WHOLE = """# Документ

## Принятые решения

### Решение с отвергнутым

**Стало.** Так.

**Отвергнуто.** Иначе, потому что дорого.

## Другой раздел
"""

WITHOUT = """# Документ

## Принятые решения

### Решение без отвергнутого

**Стало.** Так.
"""

TWO = """# Документ

## Принятые решения

### Первое

**Отвергнуто.** Иначе.

### Второе

**Стало.** Так.
"""


# --------------------------------------------------------------------------- #
# Разбор записей
# --------------------------------------------------------------------------- #


def test_entry_without_the_required_part_is_a_finding():
    problems = decisions.findings(WITHOUT, set())
    assert len(problems) == 1
    assert "Решение без отвергнутого" in problems[0]
    assert decisions.DOCUMENT in problems[0], "находка называет адрес (правило 158)"


def test_whole_entry_is_silent():
    assert decisions.findings(WHOLE, set()) == []


def test_only_the_incomplete_entry_is_found():
    problems = decisions.findings(TWO, set())
    assert len(problems) == 1
    assert "Второе" in problems[0]


def test_exemption_silences_the_finding():
    assert decisions.findings(WITHOUT, {"Решение без отвергнутого"}) == []


def test_entry_ends_at_the_next_heading():
    """Часть соседней записи не считается своей: иначе одна закрывала бы все."""
    written = decisions.decisions(TWO)
    assert decisions.REQUIRED in written["Первое"]
    assert decisions.REQUIRED not in written["Второе"]


def test_section_of_another_document_is_not_read():
    assert decisions.decisions("# Пусто\n\n## Другое\n\n### Запись\n") == {}


def test_document_without_the_section_has_no_entries():
    assert decisions.decisions("# Пусто\n") == {}


# --------------------------------------------------------------------------- #
# Планка не отстаёт от документа
# --------------------------------------------------------------------------- #


def test_exemption_for_a_missing_entry_is_a_finding():
    """Переименовали запись — освобождение стало тихой дырой."""
    problems = decisions.stale_exemptions(TWO, {"Такой записи нет"})
    assert len(problems) == 1
    assert "нет вовсе" in problems[0]


def test_exemption_that_gained_the_part_is_a_finding():
    """Часть появилась — освобождение пора снять, планка движется вниз."""
    problems = decisions.stale_exemptions(TWO, {"Первое"})
    assert len(problems) == 1
    assert "пора снять" in problems[0]


def test_exemption_still_needed_is_silent():
    assert decisions.stale_exemptions(TWO, {"Второе"}) == []


# --------------------------------------------------------------------------- #
# Исходы команды
# --------------------------------------------------------------------------- #


def test_missing_document_is_the_third_outcome(tmp_path: Path, capsys):
    assert decisions.main(["--root", str(tmp_path)]) == decisions.NOT_RUN
    error = capsys.readouterr().err
    assert "не отработала" in error
    assert decisions.DOCUMENT in error, "третий исход обязан назвать предмет (158)"


def test_document_without_decisions_is_the_third_outcome(tmp_path: Path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / decisions.DOCUMENT).write_text("# Пусто\n", encoding="utf-8")
    assert decisions.main(["--root", str(tmp_path)]) == decisions.NOT_RUN
    assert "записей решений не найдено" in capsys.readouterr().err


def test_findings_return_one(tmp_path: Path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / decisions.DOCUMENT).write_text(WITHOUT, encoding="utf-8")
    assert decisions.main(["--root", str(tmp_path)]) == 1
    assert "неполна или стёрта" in capsys.readouterr().err


def test_clean_tree_returns_zero(tmp_path: Path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / decisions.DOCUMENT).write_text(WHOLE, encoding="utf-8")
    assert decisions.main(["--root", str(tmp_path)]) == 0
    assert "записей решений: 1" in capsys.readouterr().out


def test_missing_baseline_exempts_nobody(tmp_path: Path):
    assert decisions.load_baseline(tmp_path) == set()


# --------------------------------------------------------------------------- #
# Утверждения о живом документе (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_repository_keeps_a_decision_record():
    """У гейта есть предмет: записей нет — стеречь нечего (правило 075)."""
    text = (project_root() / decisions.DOCUMENT).read_text(encoding="utf-8")
    assert decisions.decisions(text), "раздел решений пуст — гейт держал бы пустоту"


@pytest.mark.live_surface
def test_every_decision_of_the_repository_complies():
    text = (project_root() / decisions.DOCUMENT).read_text(encoding="utf-8")
    exempt = decisions.load_baseline(project_root())
    problems = decisions.findings(text, exempt) + decisions.stale_exemptions(text, exempt)
    assert not problems, "\n".join(problems)


@pytest.mark.live_surface
def test_baseline_moves_only_down():
    """Планка освобождает, и потому расти ей нельзя — как и храповику качества."""
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    ceiling = 7
    grandfathered = payload["grandfathered"]
    assert len(grandfathered) <= ceiling, (
        f"освобождённых записей стало {len(grandfathered)} против потолка {ceiling}: "
        "новая запись обязана называть отвергнутое, а не проситься в планку"
    )
    assert len(grandfathered) == ceiling, (
        f"освобождений стало меньше — опустите потолок здесь до {len(grandfathered)}"
    )


# --------------------------------------------------------------------------- #
# Решение не правится задним числом (правило 043)
# --------------------------------------------------------------------------- #


def test_erased_entry_is_a_finding():
    found = decisions.erased(TWO, WHOLE)
    assert len(found) == 2
    assert all("Заменено" in item for item in found)


def test_kept_entry_is_silent():
    assert decisions.erased(WHOLE, WHOLE) == []


def test_new_entry_is_not_an_erasure():
    assert (
        decisions.erased(WHOLE, WHOLE.replace("## Другой", "### Новое\n\n## Другой"))
        == []
    )


def _repository(tmp_path: Path, text: str) -> Path:
    """Дерево с git и документом решений, закоммиченным как основа."""
    (tmp_path / "docs").mkdir()
    (tmp_path / decisions.DOCUMENT).write_text(text, encoding="utf-8")
    for command in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "основа"],
    ):
        subprocess.run(  # noqa: S603 — аргументы наши
            ["git", "-C", str(tmp_path), *command],  # noqa: S607 — git ищется в PATH
            check=True,
            timeout=30,
        )
    return tmp_path


def test_erasure_against_the_base_returns_one(tmp_path: Path, capsys):
    root = _repository(tmp_path, TWO)
    (root / decisions.DOCUMENT).write_text(
        TWO.split("### Второе", 1)[0], encoding="utf-8"
    )
    assert decisions.main(["--root", str(root), "--base", "HEAD"]) == 1
    assert "«Второе»" in capsys.readouterr().err


def test_unreadable_base_is_the_third_outcome(tmp_path: Path, capsys):
    root = _repository(tmp_path, WHOLE)
    assert (
        decisions.main(["--root", str(root), "--base", "нет-такой"]) == decisions.NOT_RUN
    )
    assert "не отработала" in capsys.readouterr().err


@pytest.mark.live_surface
def test_repository_erases_no_decision_of_its_base():
    """Живая половина: на основе origin/main ни одна запись не стёрта."""
    root = project_root()
    base = decisions.base_document("origin/main", root)
    if base is None:
        pytest.skip("основы origin/main в клоне не видно")
    text = (root / decisions.DOCUMENT).read_text(encoding="utf-8")
    assert decisions.erased(base, text) == []
