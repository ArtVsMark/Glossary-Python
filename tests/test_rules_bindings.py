"""Проверка ответа проекта каталогу правил.

Контракт каталога требует у механизма **разрешимый адрес**: путь к файлу,
образец вида ``.github/workflows/*.yml`` или корневой документ по имени. Проза
вместо адреса не считается — гейт, чей адрес нельзя назвать, обычно и не гейт.

Этот набор держит форму ответа и разрешимость адресов. Полноту против выгрузки
каталога проверяет прогон ``rules-inbox``: она требует сети, и её место там.
"""

from __future__ import annotations

import json
import re

import pytest

from glossary.loader import project_root

BINDINGS_PATH = project_root() / ".rules" / "bindings.json"
PROPOSALS_PATH = project_root() / ".rules" / "proposals.json"

VALID_STATUSES = {"active", "rejected", "not-applicable", "unreviewed"}
VALID_MECHANISMS = {"gate", "pipeline", "document", "none"}
NEEDS_WHY = {"rejected", "not-applicable"}

# Токен, похожий на адрес: путь с разделителем, образец со звёздочкой,
# корневой dotfile (.gitattributes, .pre-commit-config.yaml) либо корневой
# документ по имени (ЗАГЛАВНЫЕ.md, Makefile, pyproject.toml).
ADDRESS = re.compile(
    r"(?:[\w.\-]+/)+[\w.\-*]+"
    r"|\.[a-z][\w.\-]*"
    r"|[A-Z][A-Za-z_]*\.md"
    r"|Makefile"
    r"|pyproject\.toml"
)


def load_bindings() -> dict[str, object]:
    """Прочитать ответ проекта."""
    doc: dict[str, object] = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    return doc


def rules() -> dict[str, dict[str, str]]:
    """Ответы по правилам."""
    payload = load_bindings()["rules"]
    assert isinstance(payload, dict)
    return payload


def resolves(token: str) -> bool:
    """Разрешается ли адрес в существующий файл репозитория."""
    root = project_root()
    if "*" in token:
        return any(root.glob(token))
    return (root / token).exists()


def test_bindings_file_exists():
    assert BINDINGS_PATH.exists(), "ответ каталогу обязателен: .rules/bindings.json"
    assert PROPOSALS_PATH.exists(), "канал предложений обязателен: пустой список законен"


def test_schema_and_project_declared():
    doc = load_bindings()
    assert doc["schema"] == "1.1"
    assert doc["project"] == "ArtVsMark/Glossary-Python"
    assert "Engineering-Incidents-Playbook" in str(doc["catalogue"])


def test_answers_are_not_empty():
    """Пустой ответ — ошибка входа, а не «правил нет» (правило 075)."""
    assert rules(), "ответ не содержит ни одного правила"


@pytest.mark.parametrize("rule_id, answer", sorted(rules().items()))
def test_answer_follows_contract(rule_id: str, answer: dict[str, str]):
    status = answer.get("status")
    assert status in VALID_STATUSES, f"{rule_id}: неизвестный статус {status!r}"

    if status in NEEDS_WHY:
        assert answer.get("why"), f"{rule_id}: статус {status} требует причины"
        return

    if status != "active":
        return

    mechanism = answer.get("mechanism")
    assert mechanism in VALID_MECHANISMS, f"{rule_id}: механизм {mechanism!r}"

    if mechanism == "none":
        # Правило 154: «не держится ничем» обязано назвать причину,
        # иначе none означает сразу «нельзя» и «не дошли руки».
        assert answer.get("why"), f"{rule_id}: mechanism none обязан назвать причину"
        return

    where = answer.get("where", "")
    assert where, f"{rule_id}: механизм {mechanism} требует адреса"
    found = [t for t in ADDRESS.findall(where) if resolves(t)]
    assert found, (
        f"{rule_id}: в поле where нет разрешимого адреса — "
        f"проза рядом с адресом допустима, вместо адреса нет. Получено: {where!r}"
    )


def test_no_unreviewed_answers():
    """Незакрытая работа по правилам идёт впереди новой (правило 177)."""
    pending = sorted(k for k, v in rules().items() if v.get("status") == "unreviewed")
    assert not pending, "правила без разбора: " + ", ".join(pending)


def test_unmechanised_count_does_not_grow():
    """Метрика «сколько правил не обеспечено ничем» должна уменьшаться.

    Число зафиксировано здесь намеренно: растворённая в тексте метрика выглядит
    отсутствующей. Планка двигается только вниз — как и храповик качества данных.
    """
    ceiling = 42
    unmechanised = sorted(
        k
        for k, v in rules().items()
        if v.get("status") == "active" and v.get("mechanism") == "none"
    )
    assert len(unmechanised) <= ceiling, (
        f"правил без механизма стало {len(unmechanised)} против потолка {ceiling}: "
        + ", ".join(unmechanised)
    )
    assert len(unmechanised) == ceiling, (
        f"механизмов стало больше — опустите потолок в этом тесте до {len(unmechanised)}"
    )


def test_proposals_channel_is_valid():
    doc = json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))
    assert doc["schema"] == "1.0"
    assert isinstance(doc["proposals"], list)
    for proposal in doc["proposals"]:
        assert "id" not in proposal, "номер присваивает каталог при приёме"
