"""Проверка ответа проекта каталогу правил.

Контракт каталога требует у механизма **разрешимый адрес**: путь к файлу,
образец вида ``.github/workflows/*.yml`` или корневой документ по имени. Проза
вместо адреса не считается — гейт, чей адрес нельзя назвать, обычно и не гейт.

Этот набор держит форму ответа и разрешимость адресов. Полноту против выгрузки
каталога проверяет прогон ``rules-inbox``: она требует сети, и её место там.

Формы у ответа с тех пор стало две сверх адреса, и обе про честность вердикта:

* **``machine_half`` у каждого ``mechanism: none``** (правило 182). Требование —
  конъюнкция, а причина пишется, глядя на неё целиком: если хоть одна часть
  требует суждения, весь ответ звучит как «требует суждения» — истинно про
  конъюнкцию и ложно про каждую часть. Честный ответ при этом не
  перепроверяют, и потому он живёт годами. Здесь у него спрашивается отдельно:
  что следует из данных целиком и почему оно всё-таки не построено.
* **``refuted_by`` у ответов «предмета нет»** (правило 175). «Не применимо» —
  утверждение о ДЕЙСТВИТЕЛЬНОСТИ, и устаревает оно молча: прозу не двигает
  никакой механизм, а выглядит она осознанным решением. Вердикт, опровергаемый
  одной командой поиска, обязан нести свой рецепт опровержения, и набор его
  исполняет. Асимметрия намеренная: нашли опровержение — отказ, не нашли —
  молчание; «не нашли» и «нет» разные ответы (правило 039).
"""

from __future__ import annotations

import json
import re
from typing import Any

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


def rules() -> dict[str, dict[str, Any]]:
    """Ответы по правилам.

    Значение записи разнородно: строки вердикта и вложенный объект пробы
    ``refuted_by``, — поэтому тип значения широкий, а не ``str``.
    """
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
def test_answer_follows_contract(rule_id: str, answer: dict[str, Any]):
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
        # Правило 182: причины мало. Разбор надвое всех 35 ответов за один заход
        # нашёл два устаревших вердикта (040, 100) и одну машинную половину,
        # лежавшую в этом же файле (175) — то есть ответ про всё требование
        # сразу прятал ровно то, что было достижимо.
        assert answer.get("machine_half"), (
            f"{rule_id}: причина есть, а разбора надвое нет. Скажите в поле "
            "machine_half, ЧТО ИМЕННО следует из данных целиком — и почему оно "
            "не построено: половины нет · нашла бы пустоту (146) · очередь"
        )
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
    ceiling = 31
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


# --------------------------------------------------------------------------- #
# Пробы опровержения: «предмета нет» проверяется, а не перечитывается (175)
# --------------------------------------------------------------------------- #


def probes() -> dict[str, dict[str, Any]]:
    """Ответы, несущие свой рецепт опровержения."""
    return {
        rule_id: answer["refuted_by"]
        for rule_id, answer in rules().items()
        if "refuted_by" in answer
    }


def refutation(probe: dict[str, Any]) -> tuple[str | None, int]:
    """Опровергнут ли ответ и сколько файлов проба вообще посмотрела.

    Второе число нужно само по себе: проба, не нашедшая ни одного файла,
    молчит так же, как проба, ничего не обнаружившая, — и без счёта эти два
    исхода неразличимы (правила 039, 146).
    """
    root = project_root()
    globs = probe["globs"]
    needles = probe["contains"]
    assert isinstance(globs, list) and isinstance(needles, list)
    seen = 0
    for pattern in globs:
        for path in sorted(root.glob(str(pattern))):
            if not path.is_file():
                continue
            seen += 1
            if not needles:
                return f"{path.relative_to(root)} существует", seen
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in needles:
                if str(needle) in text:
                    return f"{path.relative_to(root)} содержит «{needle}»", seen
    return None, seen


def test_refutation_probes_exist():
    """У гейта должен быть предмет: проверять нечего — это не гейт (правило 075)."""
    assert probes(), (
        "ни один ответ «предмета нет» не несёт рецепта опровержения — "
        "проверка держала бы пустоту"
    )


@pytest.mark.parametrize("rule_id, probe", sorted(probes().items()))
def test_probe_is_well_formed(rule_id: str, probe: dict[str, Any]):
    answer = rules()[rule_id]
    assert answer["status"] == "not-applicable", (
        f"{rule_id}: рецепт опровержения принадлежит ответу «предмета нет»"
    )
    assert probe.get("globs"), f"{rule_id}: у пробы нет ни одного образца пути"
    assert probe.get("why"), f"{rule_id}: проба обязана сказать, что означает находка"


@pytest.mark.parametrize("rule_id, probe", sorted(probes().items()))
def test_absence_claim_is_not_refuted(rule_id: str, probe: dict[str, Any]):
    """Ответ «предмета нет» устаревает молча — здесь он проверяется командой."""
    found, seen = refutation(probe)
    assert not found, (
        f"{rule_id}: ответ «предмета нет» опровергнут — {found}. "
        f"{probe['why']}. Перечитайте вердикт: предмет появился"
    )
    if probe["contains"]:
        assert seen, (
            f"{rule_id}: проба не посмотрела ни одного файла — образцы "
            f"{probe['globs']} ни на что не разрешились, и молчание тут "
            "означает не «чисто», а «нечего смотреть» (правило 146)"
        )


def test_probe_can_actually_refute():
    """Проба обязана уметь краснеть, иначе зелень ничего не значит (правило 146)."""
    found, seen = refutation(
        {"globs": ["pyproject.toml"], "contains": ["hatchling"], "why": "проверка"}
    )
    assert found and "pyproject.toml" in found
    assert seen == 1


def test_probe_stays_silent_when_nothing_is_found():
    found, seen = refutation(
        {"globs": ["pyproject.toml"], "contains": ["его-тут-нет"], "why": "проверка"}
    )
    assert found is None
    assert seen == 1, "файл посмотрен — молчание означает «не нашли», а не «негде»"


def test_probe_reports_that_it_looked_nowhere():
    """«Не нашли» и «нечего смотреть» — разные ответы (правило 039)."""
    found, seen = refutation(
        {"globs": ["нет-такого-каталога/*.py"], "contains": ["x"], "why": "проверка"}
    )
    assert found is None
    assert seen == 0
