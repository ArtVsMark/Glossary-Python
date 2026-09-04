"""Форму состава ролей держит гейт, а не добросовестность автора.

Правило каталога 062: роль заводится, если способна возразить, а не дополнить.
Требование машинно выразимо — значит, у него должен быть механизм, иначе это
обещание. Правило 082: непокрытый пласт называется непокрытым, поэтому раздел
о том, чего нет, обязателен.
"""

from __future__ import annotations

import re

import pytest

from glossary.loader import project_root

ROLES_PATH = project_root() / "docs" / "agent" / "roles.md"

ROLE_HEADING = re.compile(r"^### (?P<emoji>\S+) (?P<name>[^—\n]+?)(?: —.*)?$", re.M)
QUESTION = re.compile(r"^\*\*Вопрос\.\*\*\s+(?P<text>.+)$", re.M)
ARTEFACT = re.compile(r"^\*\*Артефакт\.\*\*\s+(?P<text>.+)$", re.M)
OBJECTION = re.compile(
    r"^\*\*Возражает\*\* роли «(?P<target>[^»]+)»:\s*(?P<text>.+)$", re.M
)


def sections() -> dict[str, str]:
    """Текст каждой роли, от её заголовка до следующего."""
    text = ROLES_PATH.read_text(encoding="utf-8")
    headings = list(ROLE_HEADING.finditer(text))
    result: dict[str, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        result[match.group("name").strip()] = text[match.end() : end]
    return result


def test_roles_document_exists():
    assert ROLES_PATH.exists(), "состав ролей — канонический документ, он обязателен"


def test_roles_are_declared():
    """Пустой состав — ошибка входа, а не «ролей нет»."""
    assert sections(), "в документе нет ни одной роли"


@pytest.mark.parametrize("name, body", sorted(sections().items()))
def test_role_has_question_artefact_and_objection(name: str, body: str):
    """Три условия приёмки роли — все сразу."""
    assert QUESTION.search(body), f"{name}: нет своего вопроса"
    assert ARTEFACT.search(body), f"{name}: нет своего артефакта"
    assert OBJECTION.search(body), (
        f"{name}: нет возражения — это профиль существующей роли, а не роль"
    )


@pytest.mark.parametrize("name, body", sorted(sections().items()))
def test_objection_targets_an_existing_role(name: str, body: str):
    """Возражать можно только названной здесь же роли, и не самому себе."""
    match = OBJECTION.search(body)
    assert match is not None
    target = match.group("target").strip()
    assert target in sections(), (
        f"{name}: возражает роли {target!r}, которой в составе нет"
    )
    assert target != name, f"{name}: возражение самому себе не считается"


def test_leading_roles_are_present():
    """Методист и Дизайнер ведут содержание и форму — без них состав неполон."""
    names = set(sections())
    assert {"Методист", "Дизайнер"} <= names, f"ведущие роли отсутствуют: {names}"


def test_uncovered_layers_are_named():
    """Непокрытое пишется как непокрытое (правило 082)."""
    text = ROLES_PATH.read_text(encoding="utf-8")
    assert "## Что не покрыто" in text
    assert "Владельца нет" in text, (
        "раздел есть, но ни один пласт не назван непокрытым — "
        "дыру в составе так не увидеть"
    )
