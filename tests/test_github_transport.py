"""Транспорт к GitHub: список GraphQL-исключений закрыт и объяснён.

Правило каталога 001: все операции с GitHub — по REST, а GraphQL применяется,
**только если операция в REST физически отсутствует, и каждый такой случай
назван поимённо**. Одна операция GraphQL стоит около трёхсот единиц квоты
против одной у REST; счётчик при этом считает попытки, а не успехи.

РАЗБОР НАДВОЕ (правило 182). Верна ли причина — суждение о том, чего REST не
умеет, и машинной эта половина не станет. **Что случай назван и причина у него
есть** — проверяется целиком, и держит это здешний набор.

ПОЧЕМУ ГЕЙТ НА ПРОЗУ, А НЕ НА ДЕРЕВО. Своего транспорта у проекта нет: код
наружу не ходит ни одним вызовом. Ходит окно, через MCP-сервер, и его вызовы в
дереве не оставляют следа — разбирать нечего. Прежний ответ по 001 именно это и
принял за отсутствие предмета: замер по дереву дал ноль, вывод «гейт держал бы
пустоту» был сделан про дерево, а правило живёт в окне. Предмет нашёлся в той
же сессии — два вызова по GraphQL, из них один без REST-эквивалента, а второй
с ним.

ЧЕГО НАБОР НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056): вызов
окна, обошедший список. Он не в дереве, и красного из-за него не будет — это
цена, а не недосмотр.
"""

from __future__ import annotations

import re

import pytest

from glossary.loader import project_root

SVOD = project_root() / "CLAUDE.md"
SECTION = "## Работа с GitHub"

HEADER_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")
MIN_CELLS = 2
"""Строка таблицы — это как минимум операция и причина.

Столбцов может быть больше: между ними встал «кто зовёт», когда у дерева
появился собственный вызов. Разбирать по фиксированному числу столбцов значило
бы ронять гейт на добавлении колонки — то есть на верной правке.
"""
MIN_REASON = 20
"""Короткая причина — это пометка, а не объяснение: «нет в REST» ничего не даёт."""


def section_text(document: str) -> str | None:
    """Текст раздела о транспорте; ``None`` — раздела нет."""
    if SECTION not in document:
        return None
    tail = document.split(SECTION, 1)[1]
    return tail.split("\n## ", 1)[0]


def exceptions(document: str) -> list[tuple[str, str]]:
    """Строки таблицы исключений: пары «операция, причина».

    Заголовок и разделитель отбрасываются: они описывают таблицу, а не случай.
    """
    text = section_text(document)
    if text is None:
        return []
    rows: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or HEADER_SEPARATOR.match(line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < MIN_CELLS or cells[0] == "Операция":
            continue
        rows.append((cells[0], cells[-1]))
    return rows


@pytest.fixture(scope="module")
def svod() -> str:
    """Свод проекта."""
    return SVOD.read_text(encoding="utf-8")


def test_transport_section_exists(svod: str):
    """Без раздела правило держится памятью окна, а она не переживает перезапуск."""
    assert section_text(svod) is not None, (
        f"в {SVOD.name} нет раздела «{SECTION}» — транспорт к GitHub не объявлен"
    )


def test_rest_is_declared_the_default(svod: str):
    text = section_text(svod)
    assert text is not None
    assert "REST" in text, "раздел не называет транспорт по умолчанию"


def test_graphql_exceptions_are_listed(svod: str):
    """Пустой список — не «исключений нет», а «вопрос не задан» (правило 075).

    Замер этой сессии даёт как минимум один законный случай: треда ревью в REST
    нет как понятия. Список, оказавшийся пустым, означает, что таблицу потеряли.
    """
    assert exceptions(svod), (
        "список GraphQL-исключений пуст — либо таблицу потеряли, либо правило "
        "исполняется молча, а молчание неотличимо от «не смотрели»"
    )


def test_every_exception_names_a_reason(svod: str):
    """Случай без причины — занятое место в закрытом списке."""
    thin = [
        f"{operation}: {why!r}"
        for operation, why in exceptions(svod)
        if len(why) < MIN_REASON
    ]
    assert not thin, (
        "у GraphQL-исключения нет внятной причины — правило требует назвать, "
        "чего именно REST не умеет: " + "; ".join(thin)
    )


# --------------------------------------------------------------------------- #
# Гейт проверяется тем, что он обязан отвергнуть (правило 140)
# --------------------------------------------------------------------------- #

FORGERY = f"""# Свод

{SECTION}

Транспорт — REST.

| Операция | Почему не REST |
| --- | --- |
| `list_issues` | нет |

## Следующий раздел

| Операция | Почему не REST |
| --- | --- |
| `не_из_раздела` | строка соседнего раздела не должна попасть в список |
"""


def test_missing_section_is_rejected():
    assert section_text("# Свод\n\n## Роли\n\nтекст\n") is None


def test_reason_that_explains_nothing_is_rejected():
    rows = exceptions(FORGERY)
    assert rows == [("`list_issues`", "нет")], rows
    assert [why for _, why in rows if len(why) < MIN_REASON], (
        "короткая причина обязана отвергаться, иначе гейт держит форму, а не смысл"
    )


def test_rows_of_a_neighbouring_section_are_not_counted():
    """Раздел кончается следующим заголовком, иначе список растёт чужими строками."""
    assert all("не_из_раздела" not in operation for operation, _ in exceptions(FORGERY))
