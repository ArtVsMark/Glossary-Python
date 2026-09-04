"""Проверки боевых данных репозитория.

Эти тесты — контракт между данными, витриной и схемой. Они не смотрят на
содержание карточек, а следят за тем, что источник истины пригоден к сборке и
что качество не деградирует от правки к правке.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from glossary.exporters import get_exporter
from glossary.loader import dump_glossary, load_glossary, project_root
from glossary.models import SCHEMA_VERSION, Glossary
from glossary.validation import validate

pytestmark = pytest.mark.data

BASELINE_PATH = Path(__file__).parent / "quality_baseline.json"
SHOWCASE_PATH = project_root() / "python_glossary.html"
SCHEMA_PATH = project_root() / "data" / "glossary.schema.json"


def test_data_loads(real_glossary: Glossary):
    assert len(real_glossary) > 0
    assert real_glossary.schema_version == SCHEMA_VERSION


def test_data_has_no_validation_errors(real_glossary: Glossary):
    report = validate(real_glossary)
    assert report.ok, "\n".join(i.format() for i in report.errors)


def test_data_file_is_canonically_formatted(real_data_path: Path, tmp_path: Path):
    """Файл записан ровно так, как его пишет ``dump_glossary``.

    Иначе diff в git смешивает смысловые правки с переформатированием, а
    сравнение витрины со сборкой перестаёт быть надёжным.
    """
    rewritten = dump_glossary(load_glossary(real_data_path), tmp_path / "out.json")
    assert rewritten.read_text(encoding="utf-8") == real_data_path.read_text(
        encoding="utf-8"
    ), "Выполните `glossary build` после ручной правки data/glossary.json"


def test_showcase_matches_data(real_glossary: Glossary):
    """Закоммиченная витрина собрана из текущих данных."""
    assert SHOWCASE_PATH.exists()
    expected = get_exporter("html").render(real_glossary)
    assert SHOWCASE_PATH.read_text(encoding="utf-8") == expected, (
        "Витрина устарела — выполните `make build` и закоммитьте результат"
    )


def test_showcase_data_block_parses(real_glossary: Glossary):
    """Витрина остаётся самодостаточной: блок данных читается как JSON."""
    html = SHOWCASE_PATH.read_text(encoding="utf-8")
    marker = '<script id="glossary-data" type="application/json">'
    start = html.index(marker) + len(marker)
    payload = json.loads(html[start : html.index("</script>", start)])
    assert len(payload) == len(real_glossary)


def test_every_export_format_runs_on_real_data(real_glossary: Glossary):
    for name in ("json", "markdown", "csv"):
        assert get_exporter(name).render(real_glossary)


def test_quality_does_not_regress(real_glossary: Glossary):
    """Храповик качества: число предупреждений по каждому правилу не растёт.

    Когда данные становятся чище, baseline опускается вместе с ними — тест
    сообщает об этом отдельно, чтобы файл не расходился с реальностью.
    """
    raw: dict[str, object] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    # Ключи с подчёркиванием — пояснения внутри файла, а не правила.
    baseline: dict[str, int] = {
        k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, int)
    }
    current: Counter[str] = validate(real_glossary).by_rule()

    grown = {
        rule: (count, baseline.get(rule, 0))
        for rule, count in current.items()
        if count > baseline.get(rule, 0)
    }
    assert not grown, (
        "Замечаний стало больше, чем в tests/quality_baseline.json: "
        + ", ".join(f"{r}: {now} > {was}" for r, (now, was) in sorted(grown.items()))
    )

    improved = {
        rule: (current.get(rule, 0), was)
        for rule, was in baseline.items()
        if current.get(rule, 0) < was
    }
    assert not improved, (
        "Качество улучшилось — опустите планку в tests/quality_baseline.json: "
        + ", ".join(f"{r}: {now} < {was}" for r, (now, was) in sorted(improved.items()))
    )


def test_data_matches_json_schema(real_data_path: Path):
    """Данные соответствуют опубликованной JSON Schema."""
    jsonschema = pytest.importorskip(
        "jsonschema", reason="установите extra 'schema' для проверки по JSON Schema"
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    document = json.loads(real_data_path.read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(document),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors, "\n".join(
        f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors[:20]
    )
