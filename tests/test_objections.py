"""Контракт замечаний к содержанию.

Замечания — единственный обратный поток к источнику: карточки правятся там,
а найдены они здесь. У контракта две формы, и у каждой своя обязанность.
Markdown читает человек, поэтому список усекается. JSON читает машина, поэтому
не усекается никогда: усечённый контракт хуже отсутствующего — он выглядит
полным.
"""

from __future__ import annotations

import json

from glossary import objections
from glossary.models import Glossary, Text
from tests.factories import make_entry, make_glossary

BROKEN_EXAMPLE = ("for x in y:", "print(x)")


def test_clean_glossary_reports_nothing(sample_glossary: Glossary):
    data = objections.collect(sample_glossary)
    assert data["findings"] == []
    assert data["totals"] == {"errors": 0, "warnings": 0, "cards_affected": 0}
    assert "Замечаний нет." in objections.as_markdown(sample_glossary)


def test_contract_names_its_schema_and_both_sides():
    """Потребитель обязан понять, что читает и от кого."""
    data = objections.collect(make_glossary())
    assert data["schema"] == objections.SCHEMA
    assert data["producer"] == objections.PRODUCER
    assert data["source"] == objections.SOURCE


def test_snapshot_size_travels_with_the_findings():
    """Сто замечаний на сто карточек и на десять тысяч — разные новости."""
    glossary = make_glossary(make_entry(id="a"), make_entry(id="b"))
    assert objections.collect(glossary)["snapshot"]["cards"] == 2


def test_findings_group_by_rule_and_count_cards_once():
    """Правило даёт по находке на язык — карточка в списке одна."""
    glossary = make_glossary(make_entry(id="a", body=Text(ru="", en="")))
    finding = next(
        f for f in objections.collect(glossary)["findings"] if f["rule"] == "translated"
    )
    assert finding["count"] == 2
    assert finding["cards"] == ["a"]


def test_findings_are_ordered_by_weight():
    """Первым читают самое частое, а не самое алфавитное."""
    entries = [make_entry(id=f"e{n}", examples=BROKEN_EXAMPLE) for n in range(4)]
    entries.append(make_entry(id="lone", section="Одинокий"))
    data = objections.collect(make_glossary(*entries))
    assert data["findings"][0]["rule"] == "example-indent"


def test_json_list_is_never_truncated():
    """Усечённый контракт выглядит полным — это хуже, чем его отсутствие."""
    entries = [make_entry(id=f"e{n}", examples=BROKEN_EXAMPLE) for n in range(60)]
    payload = json.loads(objections.as_json(make_glossary(*entries)))
    finding = next(f for f in payload["findings"] if f["rule"] == "example-indent")
    assert len(finding["cards"]) == 60


def test_json_carries_no_timestamp():
    """Отметка времени меняла бы файл на каждом прогоне.

    Публикующий прогон коммитит только изменившееся; дата сделала бы «ничего
    не изменилось» неотличимым от изменения, и ветка копила бы пустые коммиты.
    """
    rendered = objections.as_json(make_glossary(make_entry(examples=BROKEN_EXAMPLE)))
    assert objections.as_json(make_glossary(make_entry(examples=BROKEN_EXAMPLE))) == (
        rendered
    )
    payload = json.loads(rendered)
    assert not {"generated_at", "timestamp", "date"} & payload.keys()


def test_json_is_valid_utf8_without_escapes():
    """Идентификаторы кириллические: контракт читают глазами, когда он ломается."""
    glossary = make_glossary(make_entry(id="бинарный-поиск", examples=BROKEN_EXAMPLE))
    assert "\\u" not in objections.as_json(glossary)
    assert "бинарный-поиск" in objections.as_json(glossary)


def test_markdown_truncates_and_says_how_to_get_the_rest():
    entries = [make_entry(id=f"e{n}", examples=BROKEN_EXAMPLE) for n in range(30)]
    text = objections.as_markdown(make_glossary(*entries), limit=5)
    assert text.count("- `e") == 5
    assert "…и ещё 25" in text
    assert "--limit 0" in text


def test_markdown_full_list_on_zero_limit():
    entries = [make_entry(id=f"e{n}", examples=BROKEN_EXAMPLE) for n in range(30)]
    text = objections.as_markdown(make_glossary(*entries), limit=0)
    assert text.count("- `e") == 30
    assert "…и ещё" not in text


def test_markdown_points_at_the_machine_readable_twin():
    """Письмо называет адрес, по которому тот же список читает машина."""
    text = objections.as_markdown(make_glossary(make_entry(examples=BROKEN_EXAMPLE)))
    assert "objections.json" in text and "badges" in text
