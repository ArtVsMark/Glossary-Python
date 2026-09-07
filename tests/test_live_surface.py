"""У каждого гейта есть половина, смотрящая на живое дерево: правило 037.

Правило каталога 037: находка, полученная на подделке, — гипотеза, пока её не
подтвердили на настоящей поверхности. Обратное верно так же и стоит дороже:
**зелёное на подделках не есть утверждение о дереве**. Набор, собранный целиком
из фикстур, доказывает, что разбор устроен верно, и молчит о том, что разбирают.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. 7 сентября прогон ``test_check_attribution``
дал ровно эту картину: четырнадцать проверок на подделках зелены, а единственное
утверждение о живой истории — красно. Половины отвечают на разные вопросы, и
ответ одной ничего не говорит о другой. К этому дню обе половины были у всех
пяти гейтов дерева — но требовало этого только соглашение, и шестой гейт мог
приехать с одними подделками, ничего не нарушив.

Половина объявляется маркером, а не угадывается. Признак «тест не берёт
``tmp_path``» ловил бы заодно чистые функции разбора, а признак по имени —
переименование. Маркер стоит там, где автор знает ответ, и виден в отчёте
прогона: ``pytest -m live_surface``.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **содержательность живой половины.** Помеченный тест, читающий дерево и не
  утверждающий о нём ничего, гейт примет: он видит маркер, а не смысл;
* **гейты, живущие тестом.** ``tests/test_labels.py`` и подобные не имеют
  скрипта в ``scripts/`` и в перечисление не попадают — у них подделок нет
  вовсе, и путать зелень не с чем;
* **тяжесть находки.** Правило 037 говорит о severity в сводке аудита; здесь
  severity нет, и гейт требует только, чтобы живая половина существовала.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from glossary.loader import project_root

MARKER = "pytest.mark.live_surface"
"""Чем объявляется утверждение о живой поверхности."""

GATES = "scripts/check_*.py"
"""Образец намеренно широкий: новый гейт обязан попасть под него сам."""

FORGED_TESTS = '''
"""Набор, у которого есть только подделки."""

def test_parser_rejects_a_forgery():
    assert True
'''

LIVE_ONLY_TESTS = """
import pytest

@pytest.mark.live_surface
def test_repository_complies():
    assert True
"""

BOTH_HALVES = """
import pytest

def test_parser_rejects_a_forgery():
    assert True

@pytest.mark.live_surface
def test_repository_complies():
    assert True
"""


def dotted(node: ast.expr) -> str:
    """Имя узла в точечной записи: ``pytest.mark.live_surface``.

    Args:
        node: Узел выражения — цепочка атрибутов либо имя.

    Returns:
        Имя через точку; пустая строка — узел не является цепочкой.
    """
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    parts.append(current.id)
    return ".".join(reversed(parts))


def is_live_marker(decorator: ast.expr) -> bool:
    """Объявляет ли декоратор утверждение о живой поверхности."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return dotted(target) == MARKER


def halves(source: str) -> tuple[set[str], set[str]]:
    """Две половины набора: живая и на подделках.

    Args:
        source: Текст модуля с тестами.

    Returns:
        Пара «помеченные живыми» и «все остальные тесты».
    """
    module = ast.parse(source)
    live: set[str] = set()
    every: set[str] = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        every.add(node.name)
        if any(is_live_marker(item) for item in node.decorator_list):
            live.add(node.name)
    return live, every - live


def findings(root: Path) -> tuple[list[str], int]:
    """Гейты без живой половины и число разобранных гейтов.

    Второе число нужно само по себе: ноль находок при нуле гейтов означает не
    «чисто», а «нечего смотреть» (правила 039, 146).

    Args:
        root: Корень дерева.

    Returns:
        Готовые к печати находки и число разобранных гейтов.
    """
    problems: list[str] = []
    seen = 0
    for script in sorted(root.glob(GATES)):
        seen += 1
        suite = root / "tests" / f"test_{script.stem}.py"
        address = suite.relative_to(root)
        if not suite.exists():
            problems.append(f"{script.relative_to(root)}: набора {address} нет вовсе")
            continue
        live, forged = halves(suite.read_text(encoding="utf-8"))
        if not live:
            problems.append(
                f"{address}: нет ни одного утверждения о живом дереве. Зелень на "
                f"подделках говорит об устройстве разбора, а не о дереве — "
                f"пометьте живую половину маркером {MARKER} (правило 037)"
            )
        if not forged:
            problems.append(
                f"{address}: подделок нет вовсе — гейт, ни разу не показанный "
                "красным, зелен неизвестно о чём (правило 146)"
            )
    return problems, seen


# --------------------------------------------------------------------------- #
# Гейт умеет краснеть: подделки набора о наборах
# --------------------------------------------------------------------------- #


def tree(root: Path, name: str, source: str) -> Path:
    """Собрать поддельное дерево с одним гейтом и одним набором."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / f"{name}.py").write_text("def main(): ...\n", encoding="utf-8")
    (root / "tests" / f"test_{name}.py").write_text(source, encoding="utf-8")
    return root


def test_suite_without_a_live_half_is_a_finding(tmp_path: Path):
    problems, seen = findings(tree(tmp_path, "check_forged", FORGED_TESTS))
    assert seen == 1
    assert len(problems) == 1
    assert "живом дереве" in problems[0]
    assert "tests/test_check_forged.py" in problems[0], "находка обязана назвать файл"


def test_suite_without_forgeries_is_a_finding(tmp_path: Path):
    problems, seen = findings(tree(tmp_path, "check_live", LIVE_ONLY_TESTS))
    assert seen == 1
    assert len(problems) == 1
    assert "подделок нет" in problems[0]


def test_both_halves_are_silent(tmp_path: Path):
    problems, seen = findings(tree(tmp_path, "check_whole", BOTH_HALVES))
    assert seen == 1
    assert problems == []


def test_missing_suite_is_a_finding(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_orphan.py").write_text("x = 1\n", encoding="utf-8")
    problems, seen = findings(tmp_path)
    assert seen == 1
    assert "набора tests/test_check_orphan.py нет" in problems[0]


def test_empty_tree_looked_nowhere(tmp_path: Path):
    """«Не нашли» и «нечего смотреть» — разные ответы (правило 039)."""
    problems, seen = findings(tmp_path)
    assert problems == []
    assert seen == 0


# --------------------------------------------------------------------------- #
# Разбор маркера
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "decorator",
    ["@pytest.mark.live_surface", "@pytest.mark.live_surface()"],
    ids=["без скобок", "со скобками"],
)
def test_both_spellings_of_the_marker_are_read(decorator: str):
    live, _ = halves(f"{decorator}\ndef test_x():\n    assert True\n")
    assert live == {"test_x"}


@pytest.mark.parametrize(
    "decorator",
    ["@pytest.mark.data", "@pytest.fixture", "@staticmethod"],
)
def test_other_decorators_are_not_the_marker(decorator: str):
    live, forged = halves(f"{decorator}\ndef test_x():\n    assert True\n")
    assert live == set()
    assert forged == {"test_x"}


def test_helper_is_not_a_test():
    """Вспомогательная функция не половина: считаются только тесты."""
    live, forged = halves("def helper():\n    return 1\n")
    assert live == set()
    assert forged == set()


def test_dotted_gives_up_on_a_call_chain():
    """Цепочка, не начинающаяся с имени, именем не является."""
    assert dotted(ast.parse("f().mark.live_surface", mode="eval").body) == ""


# --------------------------------------------------------------------------- #
# Утверждение о живом дереве — о самом этом гейте (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_repository_has_gates_to_look_at():
    """У гейта есть предмет: проверять нечего — это не гейт (правило 075)."""
    _, seen = findings(project_root())
    assert seen, f"под образец {GATES} не попал ни один гейт — смотреть не на что"


@pytest.mark.live_surface
def test_every_gate_of_the_repository_has_a_live_half():
    problems, _ = findings(project_root())
    assert not problems, "\n".join(problems)
