"""Тесты командного интерфейса."""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from glossary.cli import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main
from glossary.loader import dump_glossary
from tests.factories import make_entry, make_glossary


class Result:
    """Результат запуска CLI: код возврата и перехваченные потоки."""

    def __init__(self, code: int, out: str, err: str) -> None:
        self.code = code
        self.out = out
        self.err = err


def run(*argv: str) -> Result:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, out=out, err=err)
    return Result(code, out.getvalue(), err.getvalue())


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Небольшой валидный файл данных во временном каталоге."""
    glossary = make_glossary(
        make_entry(id="alpha", name="alpha()", group="Раздел"),
        make_entry(id="beta", name="beta()", group="Раздел"),
    )
    return dump_glossary(glossary, tmp_path / "glossary.json")


def with_data(data_file: Path, *argv: str) -> Sequence[str]:
    return ("--data", str(data_file), *argv)


# --------------------------- общее ---------------------------


def test_version_flag_exits_cleanly():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == EXIT_OK


def test_missing_command_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == EXIT_USAGE


def test_missing_data_file_reports_error(tmp_path: Path):
    result = run("--data", str(tmp_path / "нет.json"), "stats")
    assert result.code == EXIT_USAGE
    assert "Ошибка:" in result.err


@pytest.mark.parametrize("position", ["before", "after"])
def test_data_flag_works_in_both_positions(data_file: Path, position: str):
    """`glossary --data X stats` и `glossary stats --data X` эквивалентны."""
    argv = (
        ("--data", str(data_file), "stats", "--format", "json")
        if position == "before"
        else ("stats", "--data", str(data_file), "--format", "json")
    )
    result = run(*argv)
    assert result.code == EXIT_OK
    assert json.loads(result.out)["total"] == 2


def test_data_path_defaults_to_repository_file():
    """Без --data команда работает с data/glossary.json репозитория."""
    result = run("stats", "--format", "json")
    assert result.code == EXIT_OK
    assert json.loads(result.out)["total"] > 0


# --------------------------- validate ---------------------------


def test_validate_passes_on_clean_data(data_file: Path):
    result = run(*with_data(data_file, "validate"))
    assert result.code == EXIT_OK
    assert "ошибок: 0" in result.out


def test_validate_fails_on_broken_data(tmp_path: Path):
    broken = dump_glossary(
        make_glossary(make_entry(id="a", cg="нет"), make_entry(id="b")),
        tmp_path / "glossary.json",
    )
    result = run("--data", str(broken), "validate")
    assert result.code == EXIT_FAILED
    assert "color-group" in result.err


def test_validate_strict_turns_warnings_into_failure(tmp_path: Path):
    warned = dump_glossary(
        make_glossary(
            make_entry(id="a", version="3.9"), make_entry(id="b", version="3.9")
        ),
        tmp_path / "glossary.json",
    )
    assert run("--data", str(warned), "validate").code == EXIT_OK
    strict = run("--data", str(warned), "validate", "--strict")
    assert strict.code == EXIT_FAILED
    assert "--strict" in strict.err


def test_validate_json_output_is_machine_readable(data_file: Path):
    result = run(*with_data(data_file, "validate", "--format", "json"))
    payload = json.loads(result.out)
    assert payload["ok"] is True
    assert payload["total"] == 2
    assert payload["issues"] == []


def test_validate_min_description_is_configurable(data_file: Path):
    result = run(*with_data(data_file, "validate", "--min-description", "500"))
    assert result.code == EXIT_FAILED
    assert "description-length" in result.err


# --------------------------- build ---------------------------


def test_build_writes_showcase(data_file: Path, tmp_path: Path):
    target = tmp_path / "out" / "showcase.html"
    result = run(*with_data(data_file, "build", "-o", str(target)))
    assert result.code == EXIT_OK
    assert target.exists()
    assert "alpha" in target.read_text(encoding="utf-8")


def test_build_check_passes_after_build(data_file: Path, tmp_path: Path):
    target = tmp_path / "showcase.html"
    run(*with_data(data_file, "build", "-o", str(target)))
    assert (
        run(*with_data(data_file, "build", "--check", "-o", str(target))).code == EXIT_OK
    )


def test_build_check_detects_drift(data_file: Path, tmp_path: Path):
    target = tmp_path / "showcase.html"
    target.write_text("<html>устаревшая витрина</html>", encoding="utf-8")
    result = run(*with_data(data_file, "build", "--check", "-o", str(target)))
    assert result.code == EXIT_FAILED
    assert "расходится" in result.err


def test_build_check_reports_missing_file(data_file: Path, tmp_path: Path):
    result = run(
        *with_data(data_file, "build", "--check", "-o", str(tmp_path / "нет.html"))
    )
    assert result.code == EXIT_FAILED
    assert "не найдена" in result.err


def test_build_check_does_not_write(data_file: Path, tmp_path: Path):
    target = tmp_path / "нет.html"
    run(*with_data(data_file, "build", "--check", "-o", str(target)))
    assert not target.exists()


# --------------------------- export ---------------------------


def test_export_writes_to_stdout_by_default(data_file: Path):
    result = run(*with_data(data_file, "export", "-f", "json"))
    assert result.code == EXIT_OK
    assert [e["id"] for e in json.loads(result.out)] == ["alpha", "beta"]


def test_export_writes_file(data_file: Path, tmp_path: Path):
    target = tmp_path / "вложенный" / "glossary.md"
    result = run(*with_data(data_file, "export", "-f", "markdown", "-o", str(target)))
    assert result.code == EXIT_OK
    assert target.read_text(encoding="utf-8").startswith("# Глоссарий Python")


def test_export_rejects_unknown_format(data_file: Path):
    with pytest.raises(SystemExit) as exc:
        main(with_data(data_file, "export", "-f", "pdf"))
    assert exc.value.code == EXIT_USAGE


# --------------------------- stats ---------------------------


def test_stats_text_output(data_file: Path):
    result = run(*with_data(data_file, "stats"))
    assert result.code == EXIT_OK
    assert "Карточек:" in result.out
    assert "Раздел" in result.out


def test_stats_json_output(data_file: Path):
    payload = json.loads(run(*with_data(data_file, "stats", "--format", "json")).out)
    assert payload["total"] == 2
    assert payload["groups"] == {"Раздел": 2}
    assert payload["versioned"] == 0
