"""Тесты выгрузки для потребителей — контракт ``delivery.json``.

Потребитель импортирует выгрузку записью каждой группы в свой файл. Поэтому
сторож формы — обратная сборка: группы, разложенные по файлам, обязаны дать
ровно тот же глоссарий, что собран из ``data/cards/``. Расхождение здесь
означало бы, что грейдер учит не тому, что лежит в источнике.
"""

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

import version as version_module
from glossary import delivery, taxonomy
from glossary.cards import assemble, default_cards_dir, read_cards
from glossary.cli import EXIT_OK, EXIT_USAGE, main
from glossary.contracts import PRODUCER
from glossary.errors import DataFormatError
from glossary.loader import digest, load_glossary, project_root
from glossary.models import SCHEMA_VERSION

ROOT = project_root()


def card(**overrides: Any) -> dict[str, Any]:
    """Карточка в форме ``data/cards/`` — без ``color_group``."""
    base: dict[str, Any] = {
        "id": "sample",
        "title": {"ru": "sample()", "en": "sample()"},
        "kind": "function",
        "summary": {"ru": "Сводка.", "en": "Summary."},
        "body": {"ru": "Тело.", "en": "Body."},
        "status": "ready",
        "section": "Раздел",
    }
    return base | overrides


def make_cards(root: Path, files: dict[str, list[dict[str, Any]]]) -> Path:
    """Разложить карточки по файлам групп."""
    root.mkdir(parents=True, exist_ok=True)
    for name, items in files.items():
        (root / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False), "utf-8")
    return root


def unpack(groups: dict[str, list[dict[str, Any]]], root: Path) -> Path:
    """Сделать то, что сделает импорт потребителя: группа → файл."""
    return make_cards(root, groups)


# --------------------------- форма ---------------------------


def test_groups_mirror_card_files(tmp_path: Path):
    """Ключ — имя файла, порядок карточек — порядок файла, группы в поле нет."""
    source = make_cards(
        tmp_path,
        {"str": [card(id="b"), card(id="a")], "exc": [card(id="e", kind="exception")]},
    )
    groups = delivery.groups_of(read_cards(source))
    assert list(groups) == ["exc", "str"]
    assert [c["id"] for c in groups["str"]] == ["b", "a"]
    assert all("color_group" not in c for cards in groups.values() for c in cards)


def test_drafts_stay_home(tmp_path: Path):
    """Черновик не должен оказаться у учащегося раньше, чем его допишут."""
    source = make_cards(tmp_path, {"str": [card(id="a"), card(id="b", status="draft")]})
    groups = delivery.groups_of(read_cards(source))
    assert [c["id"] for c in groups["str"]] == ["a"]


def test_group_with_only_drafts_is_absent(tmp_path: Path):
    source = make_cards(
        tmp_path, {"str": [card(id="a")], "exc": [card(id="e", status="draft")]}
    )
    assert list(delivery.groups_of(read_cards(source))) == ["str"]


def test_unpacked_delivery_assembles_to_the_same_glossary(tmp_path: Path):
    """Сторож формы: импорт потребителя восстанавливает ту же сборку."""
    source = make_cards(
        tmp_path / "src",
        {
            "str": [card(id="я", section="Второй"), card(id="b", section="Первый")],
            "exc": [card(id="a", section="Второй", kind="exception")],
        },
    )
    payload = delivery.collect(source)
    restored = unpack(payload["groups"], tmp_path / "consumer")
    assert assemble(read_cards(restored)) == assemble(read_cards(source))


def test_header_and_snapshot(tmp_path: Path):
    source = make_cards(tmp_path, {"str": [card(id="a"), card(id="b")]})
    payload = delivery.collect(source)
    assert payload["producer"] == PRODUCER
    assert payload["schema_of"] == delivery.SCHEMA_OF
    assert set(payload) >= {"schema", "source", "generated_at", "snapshot", "groups"}
    assert payload["snapshot"] == {
        "cards": 2,
        "schema_version": SCHEMA_VERSION,
        "digest": digest(assemble(read_cards(source))),
    }


# --------------------------- команда ---------------------------


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_cli_writes_file(tmp_path: Path):
    source = make_cards(tmp_path / "cards", {"str": [card(id="a")]})
    target = tmp_path / "out" / "delivery.json"
    code, out, _ = run("delivery", "--cards", str(source), "-o", str(target))
    assert code == EXIT_OK
    assert "1" in out
    assert json.loads(target.read_text("utf-8"))["groups"]["str"][0]["id"] == "a"


def test_cli_prints_to_stdout(tmp_path: Path):
    source = make_cards(tmp_path, {"str": [card(id="a")]})
    code, out, _ = run("delivery", "--cards", str(source))
    assert code == EXIT_OK
    assert json.loads(out)["snapshot"]["cards"] == 1


def test_missing_cards_is_the_third_outcome(tmp_path: Path):
    absent = tmp_path / "нет-каталога"
    code, _, err = run("delivery", "--cards", str(absent))
    assert code == EXIT_USAGE
    assert str(absent) in err, "третий исход обязан назвать предмет"


# --------------------------- живая половина ---------------------------


@pytest.mark.live_surface
def test_repository_delivery_matches_the_assembled_glossary(tmp_path: Path):
    """Выгрузка дерева восстанавливает ровно ``data/glossary.json``."""
    if not default_cards_dir().is_dir():  # pragma: no cover - вне репозитория
        pytest.skip("каталога data/cards нет")
    payload = delivery.collect()
    restored = assemble(read_cards(unpack(payload["groups"], tmp_path)))
    assert restored == load_glossary()
    assert payload["snapshot"]["digest"] == digest(load_glossary())


# --------------------------- версия формы и схема ---------------------------


def test_form_major_is_the_schema_version():
    major, minor = delivery.FORM.split(".")
    assert int(major) == SCHEMA_VERSION
    assert minor.isdigit()


def test_header_names_the_form(tmp_path: Path):
    source = make_cards(tmp_path, {"str": [card()]})
    assert delivery.collect(source)["form"] == delivery.FORM


def test_delivery_schema_is_derived_from_the_card_schema():
    """Вторая схема руками не пишется: карточка выгрузки — карточка данных без группы."""
    cards = json.loads((ROOT / delivery.CARD_SCHEMA).read_text(encoding="utf-8"))
    entry = delivery.schema()["$defs"]["entry"]
    expected = set(cards["$defs"]["entry"]["properties"]) - {"color_group"}
    assert set(entry["properties"]) == expected
    assert "color_group" not in entry["required"]
    assert delivery.schema()["properties"]["form"] == {"const": delivery.FORM}


def test_cli_writes_the_schema(tmp_path: Path):
    target = tmp_path / "delivery.schema.json"
    code, out, _ = run("delivery", "--schema", "-o", str(target))
    assert code == EXIT_OK
    assert delivery.FORM in out
    assert json.loads(target.read_text("utf-8"))["title"] == "Glossary-Python delivery"


JOURNAL_ROW = re.compile(r"^\| `(?P<form>\d+\.\d+)` \|", re.MULTILINE)


@pytest.mark.live_surface
def test_form_journal_names_the_current_form():
    """Поднял форму — допиши журнал: по нему потребитель читает свой дрейф."""
    text = (ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    journal = text.split("### Журнал формы", 1)[1].split("\n## ", 1)[0]
    assert delivery.FORM in JOURNAL_ROW.findall(journal), (
        f"в docs/contracts.md § «Журнал формы» нет строки `{delivery.FORM}`"
    )


@pytest.mark.live_surface
def test_repository_delivery_matches_its_schema():
    jsonschema = pytest.importorskip("jsonschema", reason="extra 'schema' не установлен")
    jsonschema.validate(delivery.collect(), delivery.schema())


# --------------------------- переезды ---------------------------


def write_moved(cards_dir: Path, mapping: dict[str, str]) -> None:
    """Положить ``moved.json`` рядом с каталогом карточек, как ``data/moved.json``."""
    (cards_dir.parent / delivery.MOVED_FILE).write_text(
        json.dumps(
            {"_описание": "пояснение", delivery.MOVES_KEY: mapping}, ensure_ascii=False
        ),
        "utf-8",
    )


def test_no_moved_file_means_no_moves(tmp_path: Path):
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="a")]})
    assert delivery.collect(source)["moved"] == {}


def test_moved_reaches_the_delivery(tmp_path: Path):
    """Слитая карточка исчезла — потребитель узнаёт, куда вести её ссылки."""
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="new")]})
    write_moved(source, {"old": "new"})
    assert delivery.collect(source)["moved"] == {"old": "new"}


def test_move_of_an_underscored_id_reaches_the_delivery(tmp_path: Path):
    """Id с подчёркиванием — переезд, а не пояснение (#172).

    Прежде пояснением считался любой ключ с ``_``, и переезд карточки
    ``__str__-__repr__`` молча выпадал из выгрузки.
    """
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="repr-vs-str")]})
    write_moved(source, {"__str__-__repr__": "repr-vs-str"})
    assert delivery.collect(source)["moved"] == {"__str__-__repr__": "repr-vs-str"}


def test_moves_outside_their_key_are_refused(tmp_path: Path):
    """Файл прежней формы не читается молча как «переездов нет»."""
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="new")]})
    (source.parent / delivery.MOVED_FILE).write_text('{"old": "new"}', "utf-8")
    with pytest.raises(DataFormatError, match="moves"):
        delivery.collect(source)


def test_move_into_nowhere_is_refused(tmp_path: Path):
    """Перенаправить ссылку в пустоту хуже, чем не перенаправлять вовсе."""
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="a")]})
    write_moved(source, {"old": "нет-такой"})
    with pytest.raises(DataFormatError, match="несуществующую"):
        delivery.collect(source)


def test_moved_card_must_be_gone(tmp_path: Path):
    """Переехавшая карточка, оставшаяся на месте, — две живые копии."""
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="a"), card(id="b")]})
    write_moved(source, {"a": "b"})
    with pytest.raises(DataFormatError, match="ещё существуют"):
        delivery.collect(source)


def test_broken_moved_file_is_a_data_error(tmp_path: Path):
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="a")]})
    (source.parent / delivery.MOVED_FILE).write_text("{", "utf-8")
    with pytest.raises(DataFormatError, match="не JSON"):
        delivery.collect(source)


def test_moved_target_must_be_a_string(tmp_path: Path):
    source = make_cards(tmp_path / "cards", {"builtin": [card(id="a")]})
    write_moved(source, {"old": 1})  # type: ignore[dict-item]
    with pytest.raises(DataFormatError, match="строкой"):
        delivery.collect(source)


@pytest.mark.live_surface
def test_repository_moves_point_at_live_cards():
    """Переезды дерева сверены с карточками: сборка выгрузки не падает."""
    delivery.collect()


# ----------------------- исчезнувший id (#172) -----------------------


def vanished(previous: set[str], current: set[str], moves: dict[str, str]) -> list[str]:
    """Id прошлого выпуска, которых нет ни среди карточек, ни среди переездов."""
    return sorted(previous - current - moves.keys())


def test_vanished_id_is_caught_on_a_fake():
    assert vanished({"a", "b", "c"}, {"a", "d"}, {"b": "d"}) == ["c"]
    assert vanished({"a", "_x"}, {"a", "y"}, {"_x": "y"}) == []


@pytest.mark.live_surface
def test_no_released_id_vanishes_without_a_move():
    """Id из выпуска не исчезает молча: либо карточка есть, либо записан переезд.

    Ссылка потребителя на исчезнувший id становится битой без единого сигнала —
    так пропал ``__str__-__repr__`` (#172). Сверка идёт со сборкой КАЖДОГО тега
    выпуска, а не только последнего: потребитель закрепляет любой, а id,
    исчезнувший до последнего выпуска, в нём уже не виден. Выпуски до самой
    выгрузки (в них нет ``src/glossary/delivery.py``) контрактом не были: v0.1.0
    нёс другие 581 карточку, и обещания про их id не давалось.
    """
    listed = version_module.git("tag", "--list", version_module.TAG_GLOB)
    tags = [
        tag
        for tag in (listed or "").split()
        if version_module.TAG_RE.match(tag)
        and version_module.git("cat-file", "-e", f"{tag}:src/glossary/delivery.py")
        is not None
    ]
    if not tags:
        pytest.skip("тегов выпуска в клоне не видно: git fetch --tags")
    previous: set[str] = set()
    for tag in tags:
        shown = version_module.git("show", f"{tag}:data/glossary.json")
        if shown is not None:
            previous |= {entry["id"] for entry in json.loads(shown)["entries"]}
    current = {
        card["id"] for cards in delivery.collect()["groups"].values() for card in cards
    }
    lost = vanished(previous, current, delivery.moved())
    assert not lost, f"id выпусков {tags} исчезли без записи в data/moved.json: {lost}"


# --------------------------- навигация (форма 6.1) ---------------------------


def test_navigation_labels_every_section_of_the_delivery(tmp_path: Path):
    """Каждый раздел выгрузки подписан и отнесён к семейству — своей таблицы
    потребителю держать не нужно."""
    source = make_cards(
        tmp_path / "cards",
        {"builtin": [card(id="a", section="Модуль os"), card(id="b", section="Циклы")]},
    )
    navigation = delivery.collect(source)["navigation"]
    assert navigation["sections"] == {
        "Модуль os": {"group": "modules", "ru": "os", "en": "os"},
        "Циклы": {"group": "syntax", "ru": "Циклы", "en": "Loops"},
    }
    assert navigation["groups"][0] == "types"
    assert navigation["labels"]["modules"] == {"ru": "Модули", "en": "Modules"}


def test_navigation_is_the_showcase_table():
    """Одна классификация на витрину и выгрузку (правило 214)."""
    collected = delivery.collect()
    sections = sorted(
        {card["section"] for cards in collected["groups"].values() for card in cards}
    )
    assert collected["navigation"] == taxonomy.table(sections)
