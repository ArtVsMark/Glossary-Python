"""Гейт на третий исход: правила каталога 039 и 158.

Набор держит устройство разбора на подделках и отдельно — утверждение о живом
дереве. Главные предметы здесь те, которые гейт **обязан отвергнуть**
(правило 140): точка входа с двумя исходами и третий исход, называющий причину
без предмета.

Обе подделки взяты из живого дерева, а не выдуманы: ровно так выглядели
``changelog.py`` и ``whatsnew.py`` до правки в том же заходе.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_third_outcome as gate
from glossary.loader import project_root

TWO_OUTCOMES = '''
"""Проверка с двумя исходами."""


def main() -> int:
    if problems:
        print("замечания есть")
        return 1
    print("замечаний нет")
    return 0
'''

CAUSE_WITHOUT_SUBJECT = '''
"""Третий исход есть, но предмет не назван."""

NOT_RUN = 2


def main() -> int:
    if broken:
        print("проверка не отработала: что-то пошло не так")
        return NOT_RUN
    return 0
'''

SUBJECT_BY_SUBSTITUTION = '''
"""Предмет назван подстановкой."""

NOT_RUN = 2


def main() -> int:
    if broken:
        print(f"проверка не отработала: нет каталога {путь}")
        return NOT_RUN
    return 0
'''

SUBJECT_BY_ADDRESS = '''
"""Предмет назван буквальным адресом."""

EXIT_USAGE = 2


def main() -> int:
    if broken:
        print("проверка не отработала: не читается data/glossary.json")
        return EXIT_USAGE
    return 0
'''

UNKNOWN_NAME = '''
"""Исход назван именем, которого словарь не знает."""

ОТКАЗ = 2


def main() -> int:
    if broken:
        print(f"не отработало: {путь}")
        return ОТКАЗ
    return 0
'''

NOT_AN_ENTRY_POINT = '''
"""Модуль без точки входа: спрашивать с него нечего."""


def helper() -> int:
    return 0
'''


def whats_wrong(source: str) -> list[str]:
    """Что гейт скажет об этом исходнике."""
    return [finding.what for finding in gate.inspect(source, "проба.py")]


# --------------------------------------------------------------------------- #
# Предметы, которые гейт обязан отвергнуть
# --------------------------------------------------------------------------- #


def test_two_outcomes_are_rejected():
    """«Не отработало» неотличимо от «нарушений нет» — так было у четырёх."""
    problems = whats_wrong(TWO_OUTCOMES)
    assert len(problems) == 1
    assert "два исхода вместо трёх" in problems[0]


def test_cause_without_subject_is_rejected():
    """Причина отвечает «что случилось», предмет — «чей это отказ» (158)."""
    problems = whats_wrong(CAUSE_WITHOUT_SUBJECT)
    assert len(problems) == 1
    assert "не предмет" in problems[0]


def test_unknown_outcome_name_reads_as_missing():
    """Имя вне словаря гейт не узнаёт — и говорит это, а не молчит.

    Асимметрия намеренная: молчаливый пропуск хуже ложной находки, потому что
    находку читают, а молчание — нет. Ровно на этом гейт покраснел на самом
    себе при первом прогоне.
    """
    problems = whats_wrong(UNKNOWN_NAME)
    assert len(problems) == 1
    assert "два исхода вместо трёх" in problems[0]


# --------------------------------------------------------------------------- #
# Предметы, которые гейт обязан пропустить: красное на верном приучает к фону
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source", [SUBJECT_BY_SUBSTITUTION, SUBJECT_BY_ADDRESS, NOT_AN_ENTRY_POINT]
)
def test_correct_module_passes(source: str):
    assert whats_wrong(source) == []


def test_finding_names_its_own_address():
    """Находка гейта сама обязана называть файл и строку (правило 158)."""
    findings = gate.inspect(TWO_OUTCOMES, "проба.py")
    assert str(findings[0]).startswith("проба.py:")


# --------------------------------------------------------------------------- #
# Исходы команды и утверждение о живом дереве
# --------------------------------------------------------------------------- #


def test_empty_tree_is_the_third_outcome(tmp_path: Path, capsys):
    """Гейт на третий исход обязан иметь третий исход сам."""
    assert gate.main(["--root", str(tmp_path)]) == gate.NOT_RUN
    error = capsys.readouterr().err
    assert "проверка не отработала" in error
    assert str(tmp_path) in error


def test_findings_return_one(tmp_path: Path, capsys):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "плохой.py").write_text(TWO_OUTCOMES, encoding="utf-8")
    assert gate.main(["--root", str(tmp_path)]) == 1
    assert "два исхода вместо трёх" in capsys.readouterr().err


@pytest.mark.live_surface
def test_every_entry_point_of_the_repository_complies():
    """Утверждение о живом дереве, отдельно от проверки устройства (146)."""
    findings, seen = gate.scan(project_root())
    assert seen, "не разобрано ни одной точки входа — гейт смотрел бы в пустоту"
    assert not findings, "\n".join(str(finding) for finding in findings)
