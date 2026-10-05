"""Тесты источника карточек и сборки ``data/glossary.json``.

Источник теперь здесь, и ошибка сборки не видна глазами: файл соберётся,
витрина построится, а карточки окажутся не те. Поэтому проверяется форма
результата: порядок, отбор по статусу, происхождение цветовой группы.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from glossary.cards import assemble, default_cards_dir, read_cards
from glossary.cli import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main
from glossary.errors import DataFormatError
from glossary.loader import default_data_path
from glossary.models import SCHEMA_VERSION


def card(**overrides: Any) -> dict[str, Any]:
    """Карточка в форме источника — без ``color_group``, его даёт имя файла."""
    base: dict[str, Any] = {
        "id": "sample",
        "title": "sample()",
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
        (root / f"{name}.json").write_text(
            json.dumps(items, ensure_ascii=False), encoding="utf-8"
        )
    return root


def run(*argv: str) -> tuple[int, str, str]:
    """Запустить CLI и вернуть код возврата с перехваченными потоками."""
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


# --------------------------- чтение и сборка ---------------------------


def test_color_group_comes_from_file_name(tmp_path: Path):
    """Рубрика выражена именем файла, а не полем карточки."""
    source = make_cards(
        tmp_path, {"str": [card(id="a")], "exc": [card(id="b", kind="exception")]}
    )
    assert {e.id: e.color_group for e in read_cards(source)} == {"a": "str", "b": "exc"}


def test_file_name_wins_over_field_in_card(tmp_path: Path):
    """Поле в карточке не перебивает файл: у факта одно место."""
    source = make_cards(tmp_path, {"seq": [card(id="a", color_group="str")]})
    assert read_cards(source)[0].color_group == "seq"


def test_missing_directory_is_an_input_error(tmp_path: Path):
    with pytest.raises(DataFormatError, match="каталог карточек не найден"):
        read_cards(tmp_path / "нет")


def test_empty_directory_is_an_input_error(tmp_path: Path):
    """Ноль файлов — не пустой глоссарий, а неверно указанный источник."""
    with pytest.raises(DataFormatError, match="нет ни одного файла"):
        read_cards(tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('{"id": "a"}', "ожидался массив карточек"),
        ("[1]", "должен быть объектом"),
        ("[", "некорректный JSON"),
    ],
)
def test_malformed_file_is_rejected(tmp_path: Path, text: str, message: str):
    (tmp_path / "str.json").write_text(text, encoding="utf-8")
    with pytest.raises(DataFormatError, match=message):
        read_cards(tmp_path)


def test_assemble_keeps_only_published_cards(tmp_path: Path):
    """Черновики остаются в источнике: в сборку идёт готовое."""
    source = make_cards(tmp_path, {"str": [card(id="a"), card(id="b", status="draft")]})
    assert [e.id for e in assemble(read_cards(source))] == ["a"]


def test_assemble_orders_by_section_then_id(tmp_path: Path):
    """Порядок не зависит от порядка файлов на диске — иначе сборка «дышит»."""
    source = make_cards(
        tmp_path,
        {
            "str": [card(id="я", section="Второй"), card(id="b", section="Первый")],
            "exc": [card(id="a", section="Второй")],
        },
    )
    assert [e.id for e in assemble(read_cards(source))] == ["a", "я", "b"]


def test_assemble_keeps_duplicates_for_the_validator(tmp_path: Path):
    """Дубликат не отбрасывается молча: выбирать за автора сборке не по чину."""
    source = make_cards(tmp_path, {"str": [card(id="dup"), card(id="dup", title="2")]})
    assert len(assemble(read_cards(source))) == 2


def test_assemble_stamps_current_schema_version(tmp_path: Path):
    source = make_cards(tmp_path, {"str": [card()]})
    assert assemble(read_cards(source)).schema_version == SCHEMA_VERSION


# --------------------------- команда assemble ---------------------------


def test_assemble_is_idempotent(tmp_path: Path):
    """Один и тот же вход даёт побайтово одинаковый файл."""
    source = make_cards(tmp_path / "cards", {"str": [card(id="a"), card(id="b")]})
    target = tmp_path / "glossary.json"
    args = ("assemble", "--cards", str(source), "--data", str(target))

    assert run(*args)[0] == EXIT_OK
    first = target.read_bytes()
    assert run(*args)[0] == EXIT_OK
    assert target.read_bytes() == first


def test_check_passes_and_leaves_no_trace(tmp_path: Path):
    source = make_cards(tmp_path / "cards", {"str": [card(id="a")]})
    target = tmp_path / "glossary.json"
    run("assemble", "--cards", str(source), "--data", str(target))

    code, out, _ = run(
        "assemble", "--check", "--cards", str(source), "--data", str(target)
    )
    assert code == EXIT_OK
    assert "1 карточек" in out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cards", "glossary.json"]


def test_check_fails_when_file_drifted(tmp_path: Path):
    """Гейт проверяется тем, что он обязан отвергнуть (каталог, 140/145)."""
    source = make_cards(tmp_path / "cards", {"str": [card(id="a"), card(id="b")]})
    target = tmp_path / "glossary.json"
    run("assemble", "--cards", str(source), "--data", str(target))
    make_cards(source, {"str": [card(id="a")]})

    code, _, err = run(
        "assemble", "--check", "--cards", str(source), "--data", str(target)
    )
    assert code == EXIT_FAILED
    assert "расходится" in err


def test_check_without_file_is_the_third_outcome(tmp_path: Path):
    """Собранного файла нет — сверять не с чем; это не «разошлось» (039, 158)."""
    source = make_cards(tmp_path / "cards", {"str": [card(id="a")]})
    missing = tmp_path / "нет.json"
    code, _, err = run(
        "assemble", "--check", "--cards", str(source), "--data", str(missing)
    )
    assert code == EXIT_USAGE
    assert "не отработала" in err
    assert str(missing) in err, "третий исход обязан назвать предмет"


def test_missing_cards_is_the_third_outcome(tmp_path: Path):
    absent = tmp_path / "нет-каталога"
    code, _, err = run(
        "assemble", "--cards", str(absent), "--data", str(tmp_path / "g.json")
    )
    assert code == EXIT_USAGE
    assert str(absent) in err


# --------------------------- живая половина ---------------------------


def test_repository_glossary_is_assembled_from_cards():
    """Боевой ``data/glossary.json`` — ровно сборка ``data/cards/``."""
    if not default_cards_dir().is_dir():  # pragma: no cover - вне репозитория
        pytest.skip("каталога data/cards нет")
    code, _, err = run("assemble", "--check", "--data", str(default_data_path()))
    assert code == EXIT_OK, err
