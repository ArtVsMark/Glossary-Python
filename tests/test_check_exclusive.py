"""Гейт исключительных утверждений: правило каталога 181.

Набор держит две разные вещи и не смешивает их. На **подделанном дереве**
проверяется устройство разбора: где кончается окно, что считается предметом,
какие пары находятся. На **живом дереве** проверяется утверждение о самом
репозитории — что предмет у гейта есть и что документы сверены; зелёный гейт
подтверждает себя, а не дерево (правило 146).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_exclusive
from glossary.loader import project_root


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Подделанное дерево: документы задаются тестом, а не репозиторием."""

    def write(**documents: str) -> Path:
        names = []
        for name, text in documents.items():
            path = tmp_path / f"{name}.md"
            path.write_text(text, encoding="utf-8")
            names.append(path.name)
        monkeypatch.setattr(check_exclusive, "DOCUMENTS", tuple(names))
        return tmp_path

    return write


LONG = "и" * check_exclusive.MIN_LENGTH


# --------------------------------------------------------------------------- #
# Устройство разбора — на подделке
# --------------------------------------------------------------------------- #


def test_claim_without_subject_is_a_finding(tree):
    root = tree(svod=f"Числа берутся только из сборки. {LONG}\n")
    problems = check_exclusive.findings(check_exclusive.collect(root))
    assert len(problems) == 1
    assert "предмет не назван" in problems[0]
    assert "svod.md:1" in problems[0], "находка обязана называть адрес (158)"


def test_two_claims_on_one_subject_collide(tree):
    root = tree(
        svod=(
            f"Числа берутся только из сборки. {LONG}\n<!--предмет:числа-->\n"
            "\n"
            f"Числа правятся только руками. {LONG}\n<!--предмет:числа-->\n"
        )
    )
    problems = check_exclusive.findings(check_exclusive.collect(root))
    assert len(problems) == 1
    assert "«числа»" in problems[0]
    assert "svod.md:1" in problems[0] and "svod.md:4" in problems[0]


def test_same_subject_in_two_documents_is_not_a_pair(tree):
    """181 — про один документ. Тема, разъехавшаяся по двум, это правило 022."""
    root = tree(
        svod=f"Числа берутся только из сборки. {LONG}\n<!--предмет:числа-->\n",
        guide=f"Числа правятся только руками. {LONG}\n<!--предмет:числа-->\n",
    )
    assert check_exclusive.findings(check_exclusive.collect(root)) == []


def test_not_a_claim_never_collides(tree):
    """«нет» — ответ автора «здесь предмета нет», и таких может быть много."""
    root = tree(
        svod=(
            f"Роль, которая только соглашается, не заводится. {LONG}\n"
            "<!--предмет:нет-->\n"
            "\n"
            f"Было: единственный артефакт на 599 строк. {LONG}\n"
            "<!--предмет:нет-->\n"
        )
    )
    assert check_exclusive.findings(check_exclusive.collect(root)) == []


def test_subject_comparison_ignores_case_and_spaces(tree):
    root = tree(
        svod=(
            f"Числа берутся только из сборки. {LONG}\n<!--предмет: Числа -->\n"
            "\n"
            f"Числа правятся только руками. {LONG}\n<!--предмет:числа-->\n"
        )
    )
    assert len(check_exclusive.findings(check_exclusive.collect(root))) == 1


def test_list_items_are_separate_claims(tree):
    """Замер, из-за которого окно — не абзац: список склеивался в одно окно."""
    root = tree(
        svod=(
            f"- Числа только из сборки. {LONG}\n  <!--предмет:числа-->\n"
            f"- Журнал только фрагментом. {LONG}\n  <!--предмет:журнал-->\n"
        )
    )
    claims = check_exclusive.collect(root)
    assert [claim.subject for claim in claims] == ["числа", "журнал"]
    assert [claim.line for claim in claims] == [1, 3]


def test_table_rows_and_code_are_not_claims(tree):
    root = tree(
        svod=(
            f"| поле | только из сборки, и ничего больше {LONG} |\n"
            "\n"
            "```bash\n"
            f"# только руками, и никак иначе {LONG}\n"
            "```\n"
        )
    )
    assert check_exclusive.collect(root) == []


def test_short_line_is_not_a_claim(tree):
    root = tree(svod="## Только сборкой\n")
    assert check_exclusive.collect(root) == []


def test_claim_without_marker_word_is_invisible(tree):
    """Названная граница: исключительность без слова-маркера в перебор не идёт."""
    root = tree(svod=f"У содержания один хозяин, и он не здесь. {LONG}\n")
    assert check_exclusive.collect(root) == []


# --------------------------------------------------------------------------- #
# Исходы команды
# --------------------------------------------------------------------------- #


def test_empty_tree_is_the_third_outcome(tmp_path: Path, capsys):
    """Ноль утверждений — «предмета нет», а не «чисто» (правила 075, 039)."""
    assert check_exclusive.main(["--check", "--root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "проверка не отработала" in error
    assert str(tmp_path) in error, "третий исход обязан назвать предмет (158)"


def test_check_returns_one_on_findings(tree, capsys):
    root = tree(svod=f"Числа берутся только из сборки. {LONG}\n")
    assert check_exclusive.main(["--check", "--root", str(root)]) == 1
    assert "предмет не назван" in capsys.readouterr().err


def test_check_returns_zero_when_clean(tree, capsys):
    root = tree(svod=f"Числа только из сборки. {LONG}\n<!--предмет:числа-->\n")
    assert check_exclusive.main(["--check", "--root", str(root)]) == 0
    assert "столкновений нет" in capsys.readouterr().out


def test_list_prints_subjects(tree, capsys):
    root = tree(svod=f"Числа только из сборки. {LONG}\n<!--предмет:числа-->\n")
    assert check_exclusive.main(["--list", "--root", str(root)]) == 0
    assert "[числа]" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Утверждения о живом дереве — отдельно от проверки устройства
# --------------------------------------------------------------------------- #


def test_repository_has_exclusive_claims():
    """У гейта есть предмет: проверка, которой нечего проверять, не гейт (075)."""
    assert check_exclusive.collect(project_root()), (
        "в нормативных документах не найдено ни одного исключительного "
        "утверждения — либо список документов разъехался с деревом, либо "
        "разбор сломан"
    )


def test_repository_documents_are_reconciled():
    problems = check_exclusive.findings(check_exclusive.collect(project_root()))
    assert not problems, "\n".join(problems)
