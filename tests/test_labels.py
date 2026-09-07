"""Метка — вход механизма, а не украшение: правило каталога 064.

От классификации зависят закрытие задачи, порядок очереди и зона работы, то
есть пропуск метки ломает не оформление, а поведение. Здесь держится машинная
половина требования: **метка, которую что-то проставляет автоматически,
объявлена в наборе репозитория**.

РАЗБОР НАДВОЕ (правило 182). Какая метка верна для конкретной задачи — суждение
и машинной эта половина не станет. Что проставляемая метка существует в
объявленном наборе — следует из дерева целиком.

ЗАМЕР, ИЗ-ЗА КОТОРОГО НАБОР ЗАВЕДЁН. Шаблоны задач и dependabot раздавали пять
меток — «баг», «контент», «новая карточка», «зависимости», «ci», — а файла с
объявленным набором не было вовсе. Метка, которой в репозитории нет, не
создаётся сама: площадка молча пропускает её, и классификация не доезжает.

ЧЕГО НАБОР НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056): что
метка ЗАВЕДЕНА на площадке. Это состояние вне дерева, и проверить его можно
только обращением к API; гейт держит согласованность дерева с самим собой.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from glossary.loader import project_root

GITHUB = project_root() / ".github"
DECLARED = GITHUB / "labels.yml"
TEMPLATES = GITHUB / "ISSUE_TEMPLATE"
DEPENDABOT = GITHUB / "dependabot.yml"


def declared() -> set[str]:
    """Имена меток из объявленного набора."""
    document = yaml.safe_load(DECLARED.read_text(encoding="utf-8"))
    return {str(entry["name"]) for entry in document}


def _labels_of(document: Any) -> list[str]:
    """Метки, проставляемые этим документом, где бы они в нём ни лежали."""
    found: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "labels" and isinstance(value, list):
                found.extend(str(item) for item in value)
            else:
                found.extend(_labels_of(value))
    elif isinstance(document, list):
        for item in document:
            found.extend(_labels_of(item))
    return found


def assigned() -> dict[str, set[str]]:
    """Кто какие метки проставляет: файл — набор меток."""
    sources = [*sorted(TEMPLATES.glob("*.yml")), DEPENDABOT]
    result: dict[str, set[str]] = {}
    for path in sources:
        if not path.exists():
            continue
        labels = set(_labels_of(yaml.safe_load(path.read_text(encoding="utf-8"))))
        if labels:
            result[str(path.relative_to(project_root()))] = labels
    return result


def test_label_set_is_declared():
    assert DECLARED.exists(), (
        f"нет {DECLARED.name}: набор меток не объявлен, и проставляемая метка "
        "неотличима от опечатки"
    )
    assert declared(), "набор объявлен пустым — проверять нечего (правило 075)"


def test_something_actually_assigns_labels():
    """У гейта должен быть предмет: некому проставлять — это не гейт (075)."""
    assert assigned(), "ни один файл не проставляет меток — гейт держал бы пустоту"


def undeclared(assignments: dict[str, set[str]], known: set[str]) -> dict[str, list[str]]:
    """Кто проставляет метку, которой нет в наборе.

    Вынесено функцией, чтобы предмет отказа можно было подать гейту напрямую, а
    не подделывать дерево вокруг него (правило 140).
    """
    return {
        source: sorted(labels - known)
        for source, labels in assignments.items()
        if labels - known
    }


def test_every_assigned_label_is_declared():
    """Метка, которой нет в репозитории, не создаётся сама — она теряется молча."""
    unknown = undeclared(assigned(), declared())
    assert not unknown, (
        "проставляется метка, которой нет в объявленном наборе — классификация "
        f"не доедет: {unknown}. Объявите её в .github/labels.yml"
    )


def test_hold_label_is_declared_and_honoured():
    """Объявленная метка, которую никто не читает, — бутафория.

    Метка `hold` управляет поведением прогона, а не оформлением: она и есть тот
    случай, ради которого правило 064 написано. Поэтому проверяется не только
    объявление, но и то, что прогон её читает.
    """
    assert "hold" in declared(), "метка hold обязана быть объявлена"
    workflow = (GITHUB / "workflows" / "automerge.yml").read_text(encoding="utf-8")
    assert "'hold'" in workflow, (
        "метка hold объявлена, но автомерж её не читает — объявление без "
        "механизма это украшение (правило 064)"
    )


def test_every_label_carries_a_description():
    """Метка без описания — украшение: читатель не знает, когда её ставить."""
    document = yaml.safe_load(DECLARED.read_text(encoding="utf-8"))
    thin = [str(entry["name"]) for entry in document if not entry.get("description")]
    assert not thin, "у метки нет описания: " + ", ".join(thin)


# --------------------------------------------------------------------------- #
# Гейт проверяется тем, что он обязан отвергнуть (правило 140)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "document, expected",
    [
        ({"labels": ["баг"]}, ["баг"]),
        ({"updates": [{"labels": ["ci", "зависимости"]}]}, ["ci", "зависимости"]),
        ({"body": [{"attributes": {"labels": ["вложенная"]}}]}, ["вложенная"]),
        ({"name": "шаблон без меток"}, []),
    ],
)
def test_labels_are_found_wherever_they_lie(document: Any, expected: list[str]):
    """Метки лежат по-разному: у шаблона сверху, у dependabot внутри updates."""
    assert sorted(_labels_of(document)) == sorted(expected)


def test_undeclared_label_is_rejected():
    """Предмет, который гейт обязан отвергнуть."""
    found = undeclared({"шаблон.yml": {"баг", "незнакомая"}}, {"баг"})
    assert found == {"шаблон.yml": ["незнакомая"]}


def test_declared_label_passes():
    """И тот, который обязан пропустить: красное на верном приучает к фону (051)."""
    assert undeclared({"шаблон.yml": {"баг"}}, {"баг", "ci"}) == {}
