"""Английский двойник повторяет устройство русского оригинала.

Подделки показывают, что разбор устроен верно: правка, внесённая в одну половину
пары, становится находкой. Живая половина держит само дерево — все пары из
``PAIRS`` на месте и совпадают устройством.
"""

from pathlib import Path

import pytest

import check_translations as translations

RU = """# Документ

**Русский** · [English](doc.en.md)

## Раздел

| a | b |
| --- | --- |
| 1 | 2 |

```bash
# комментарий — не заголовок
make check
```
"""

EN = """# Document

[Русский](doc.md) · **English**

## Section

| a | b |
| --- | --- |
| 1 | 2 |

```bash
# a comment is not a heading
make check
```
"""


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """Дерево с документами по относительным путям."""
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_matching_pair_is_silent():
    assert translations.compare("doc.md", RU, EN) == []


def test_comment_inside_code_is_not_a_heading():
    assert len(translations.shape(RU).headings) == 2


def test_section_added_to_one_half_is_a_finding():
    problems = translations.compare("doc.md", RU + "\n## Новый\n", EN)
    assert len(problems) == 1
    assert "'## Новый'" in problems[0]
    assert "doc.en.md" in problems[0], "находка называет половину, где нет раздела"


def test_heading_of_other_level_is_a_finding():
    problems = translations.compare("doc.md", RU, EN.replace("## Section", "### Section"))
    assert "разного уровня" in problems[0]


def test_table_row_added_to_one_half_is_a_finding():
    problems = translations.compare(
        "doc.md", RU.replace("| 1 | 2 |", "| 1 | 2 |\n| 3 | 4 |"), EN
    )
    assert any("строк таблиц 4 против 3" in p for p in problems)


def test_dropped_code_block_is_a_finding():
    english = EN.split("```bash", 1)[0]
    assert any(
        "блоков кода 1 против 0" in p for p in translations.compare("doc.md", RU, english)
    )


def test_missing_switcher_is_a_finding_on_each_side():
    problems = translations.compare(
        "doc.md", RU.replace("(doc.en.md)", ""), EN.replace("(doc.md)", "")
    )
    assert len(problems) == 2


def test_missing_twin_is_a_finding(tmp_path: Path, capsys):
    root = tree(tmp_path, dict.fromkeys(translations.PAIRS, RU))
    assert translations.main(["--root", str(root)]) == translations.FOUND
    assert "нет английского двойника" in capsys.readouterr().err


def test_missing_original_is_the_third_outcome(tmp_path: Path, capsys):
    assert translations.main(["--root", str(tmp_path)]) == translations.REFUSED
    error = capsys.readouterr().err
    assert "не отработала" in error
    assert translations.PAIRS[0] in error, "третий исход называет предмет (158)"


def test_twin_name():
    assert translations.twin("docs/use/status.md") == "docs/use/status.en.md"


@pytest.mark.live_surface
def test_every_pair_of_the_repository_matches():
    problems, refusals = translations.check(translations.ROOT, translations.PAIRS)
    assert not refusals, "\n".join(refusals)
    assert not problems, "\n".join(problems)
