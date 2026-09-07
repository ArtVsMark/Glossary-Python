"""Обрезка выдачи не умеет быть молчаливой: правило каталога 016.

Правило: урезанный результат обязан сообщать, что он урезан, и насколько.
Полный ответ и обрезанный выглядят одинаково, а различить их можно, только зная
ожидаемый объём — то есть уже имея то, чего нет.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. Ответ проекта по правилу гласил «предмета
нет: ни один механизм проекта не обрезает вывод по пределу». Это было неверно
дважды: выдачу режут ``objections`` и ``completeness``, у обоих объявлен
``DEFAULT_LIMIT``. Маркер обрыва при этом стоял — правило исполнялось, — но
писался в ТРЁХ местах своими руками, и четвёртое могло написать его иначе либо
забыть вовсе. Вердикт был неверен в посылке, а механизм держался соглашением.

Держатся здесь две вещи, обе машинные:

* модуль, объявивший ``DEFAULT_LIMIT``, обязан звать общий ``truncate``;
* срез по ``limit`` живёт в одном модуле — самом помощнике. Срез в другом месте
  и есть та самая молчаливая обрезка: маркер к нему приписывать некому.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **обрезку под другим именем.** Предел, названный ``top``, ``head`` или
  ``max_items``, гейт не заметит: он ищет ``DEFAULT_LIMIT`` и срез по ``limit``;
* **обрезку не срезом.** Цикл со счётчиком и ``break`` режет так же, а разбор
  этого не видит;
* **верность числа в маркере.** Что ``…и ещё N`` называет настоящий остаток,
  проверяют наборы отчётов, а не этот гейт.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from glossary.loader import project_root
from glossary.reporting import FULL_LIST_HINT, truncate

MODULES = "src/glossary/**/*.py"
HELPER = "reporting.py"
"""Дом среза: здесь он законен, потому что здесь же к нему приписан маркер."""

DECLARED_LIMIT = "DEFAULT_LIMIT"
HELPER_NAME = "truncate"
LIMIT = "limit"

FORGED_SILENT = '''
"""Отчёт, который режет молча."""
DEFAULT_LIMIT = 20


def as_markdown(items, limit=DEFAULT_LIMIT):
    return "\\n".join(items[:limit])
'''

FORGED_WHOLE = '''
"""Отчёт, который зовёт помощника."""
from glossary.reporting import truncate

DEFAULT_LIMIT = 20


def as_markdown(items, limit=DEFAULT_LIMIT):
    shown, note = truncate(items, limit)
    return "\\n".join([*shown, *note])
'''

FORGED_NO_LIMIT = '''
"""Модуль без ограничения выдачи: гейту он неинтересен."""


def as_markdown(items):
    return "\\n".join(items)
'''


def declares_limit(module: ast.Module) -> bool:
    """Объявляет ли модуль предел выдачи."""
    return any(
        isinstance(target, ast.Name) and target.id == DECLARED_LIMIT
        for node in module.body
        if isinstance(node, ast.AnnAssign | ast.Assign)
        for target in (
            [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
        )
    )


def imports_helper(module: ast.Module) -> bool:
    """Зовёт ли модуль общего помощника обрезки."""
    return any(
        alias.name == HELPER_NAME
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )


def slices_by_limit(module: ast.Module) -> list[int]:
    """Строки, где список режется по ``limit``."""
    return [
        node.lineno
        for node in ast.walk(module)
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Slice)
        and isinstance(node.slice.upper, ast.Name)
        and node.slice.upper.id == LIMIT
    ]


def inspect(source: str, name: str) -> list[str]:
    """Разобрать модуль и проверить обе половины требования.

    Args:
        source: Текст модуля.
        name: Имя файла для сообщений.

    Returns:
        Находки; пустой список — обрезка тут не бывает молчаливой.
    """
    module = ast.parse(source)
    problems: list[str] = []
    if declares_limit(module) and not imports_helper(module):
        problems.append(
            f"{name}: объявлен {DECLARED_LIMIT}, а общий {HELPER_NAME}() не зовётся — "
            "маркер обрыва пришлось бы писать руками, и четвёртое место напишет "
            "его иначе либо забудет (правило 016)"
        )
    if not name.endswith(HELPER):
        problems.extend(
            f"{name}:{line}: срез по {LIMIT} мимо {HELPER_NAME}() — обрезка молчит, "
            f"а урезанное от полного не отличить (правило 016)"
            for line in slices_by_limit(module)
        )
    return problems


def findings(root: Path) -> tuple[list[str], int]:
    """Находки по дереву и число разобранных модулей.

    Второе число нужно само по себе: ноль находок при нуле модулей означает не
    «чисто», а «нечего смотреть» (правила 039, 146).
    """
    problems: list[str] = []
    seen = 0
    for path in sorted(root.glob(MODULES)):
        if "__pycache__" in path.parts:
            continue
        seen += 1
        problems.extend(
            inspect(path.read_text(encoding="utf-8"), str(path.relative_to(root)))
        )
    return problems, seen


# --------------------------------------------------------------------------- #
# Помощник: срез и маркер отдаются одним вызовом
# --------------------------------------------------------------------------- #


def test_truncate_marks_the_break():
    shown, note = truncate(list(range(10)), 3)
    assert shown == [0, 1, 2]
    assert note == ["", f"…и ещё 7. {FULL_LIST_HINT}"]


@pytest.mark.parametrize("limit", [0, -1], ids=["ноль", "отрицательный"])
def test_non_positive_limit_shows_everything(limit: int):
    shown, note = truncate([1, 2, 3], limit)
    assert shown == [1, 2, 3]
    assert note == [], "обрыва не было — маркер соврал бы"


def test_exact_fit_is_not_a_break():
    """Ровно предел — не обрыв: маркер «…и ещё 0» был бы ложью."""
    shown, note = truncate([1, 2, 3], 3)
    assert shown == [1, 2, 3]
    assert note == []


def test_empty_input_is_silent():
    assert truncate([], 5) == ([], [])


def test_hint_tells_how_to_get_the_rest():
    """Маркер без способа получить остаток — тупик для читателя."""
    _, note = truncate([1, 2], 1)
    assert "--limit 0" in note[-1]


# --------------------------------------------------------------------------- #
# Гейт умеет краснеть: подделки модулей
# --------------------------------------------------------------------------- #


def test_silent_truncation_is_a_finding():
    problems = inspect(FORGED_SILENT, "поддельный.py")
    assert len(problems) == 2, problems
    assert any(DECLARED_LIMIT in p for p in problems)
    assert any("срез по limit" in p for p in problems)


def test_module_calling_the_helper_is_silent():
    assert inspect(FORGED_WHOLE, "поддельный.py") == []


def test_module_without_a_limit_is_not_examined():
    assert inspect(FORGED_NO_LIMIT, "поддельный.py") == []


def test_helper_may_slice_at_home():
    """В самом помощнике срез законен: маркер приписан к нему тут же."""
    assert inspect(FORGED_SILENT.replace("DEFAULT_LIMIT = 20", ""), "reporting.py") == []


def test_empty_tree_looked_nowhere(tmp_path: Path):
    """«Не нашли» и «нечего смотреть» — разные ответы (правило 039)."""
    problems, seen = findings(tmp_path)
    assert problems == []
    assert seen == 0


# --------------------------------------------------------------------------- #
# Утверждения о живом дереве (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_repository_has_modules_to_look_at():
    _, seen = findings(project_root())
    assert seen, f"под образец {MODULES} не попал ни один модуль"


@pytest.mark.live_surface
def test_no_module_truncates_silently():
    problems, _ = findings(project_root())
    assert not problems, "\n".join(problems)


@pytest.mark.live_surface
def test_both_reports_of_the_repository_declare_a_limit():
    """У гейта есть предмет: пределов нет — сверять не с чем (правило 075)."""
    root = project_root()
    limited = [
        path.name
        for path in sorted(root.glob(MODULES))
        if declares_limit(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert set(limited) == {"objections.py", "completeness.py"}, limited
