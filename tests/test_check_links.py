"""Гейт на ссылки: ловит битую и молчит на целой.

Правило каталога 166: проверяя ссылку, ищут ссылку, а не путь в тексте. Отсюда
устройство набора — двусторонний, и с отдельной парой на саму подмену: гейт
обязан находить цель, ведущую в никуда, при **верной подписи**. Проверка
подстрокой такую подмену пропускает зелёной, и здесь это показано явно, а не
подразумевается.

Дерево подделывается в ``tmp_path``: настоящее дерево показывает только, что
гейт на нём чист, но не показывает, что он вообще способен упасть.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_links
from check_links import CLEAN, FOUND, REFUSED
from glossary.loader import project_root


def tree(root: Path, files: dict[str, str]) -> Path:
    """Собрать подделанное дерево из пар «путь → содержимое»."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run(root: Path, *documents: str) -> int:
    """Прогнать гейт по подделанному дереву."""
    return check_links.main(["--root", str(root), *documents])


# --------------------------------------------------------------------------- #
# Ссылка ищется разметкой, а не подстрокой
# --------------------------------------------------------------------------- #


def test_label_never_becomes_a_target():
    """В находках живёт цель ссылки; подпись в них не попадает вовсе."""
    links = check_links.find_links("[docs/architecture.md](никуда.md)", "README.md")
    assert [link.target for link in links] == ["никуда.md"]


def test_swapped_target_behind_a_correct_label_is_found(tmp_path: Path):
    """Подмена цели при верной подписи — находка, а не зелёный гейт.

    Ровно тот случай, ради которого правило 166 существует: подстрока
    ``docs/architecture.md`` в документе есть, а ссылка ведёт в никуда.
    """
    text = "Решения — в [docs/architecture.md](docs/архитектура.md).\n"
    root = tree(tmp_path, {"README.md": text, "docs/architecture.md": "# Решения\n"})

    # Условие проверки подстрокой выполнено — и ничего не значит.
    assert "docs/architecture.md" in text

    assert run(root, "README.md") == FOUND
    problems = check_links.check(root, check_links.find_links(text, "README.md"))
    assert any("архитектура.md" in problem for problem in problems)


def test_reference_style_target_is_found_by_markup():
    """Ссылка-определение ``]: адрес`` — та же ссылка, ищется так же."""
    links = check_links.find_links("[решения]: docs/архитектура.md\n", "README.md")
    assert [link.target for link in links] == ["docs/архитектура.md"]


def test_footnote_is_not_a_link():
    """``[^1]:`` — сноска: её текст не адрес, и находкой быть не может."""
    assert check_links.find_links("[^1]: обычный текст сноски\n") == []


# --------------------------------------------------------------------------- #
# Обе стороны: находит битую, молчит на целой
# --------------------------------------------------------------------------- #


def test_broken_link_is_found(tmp_path: Path, capsys):
    """Цель, которой в дереве нет, роняет гейт и называет место."""
    root = tree(tmp_path, {"README.md": "См. [витрину](docs/нет.md).\n"})
    assert run(root, "README.md") == FOUND
    assert "README.md:1" in capsys.readouterr().err


def test_whole_link_is_silent(tmp_path: Path):
    """Разрешимая ссылка находкой не считается — иначе гейт нечем починить."""
    root = tree(
        tmp_path,
        {
            "README.md": "См. [решения](docs/architecture.md).\n",
            "docs/architecture.md": "# Решения\n",
        },
    )
    assert run(root, "README.md") == CLEAN


def test_relative_link_resolves_from_the_document_directory(tmp_path: Path):
    """Адрес соседа считается от каталога документа, а не от корня дерева."""
    root = tree(
        tmp_path,
        {
            "docs/architecture.md": "Состав — [роли](agent/roles.md).\n",
            "docs/agent/roles.md": "# Роли\n",
        },
    )
    assert run(root, "docs/architecture.md") == CLEAN


def test_empty_target_is_found(tmp_path: Path):
    """Пустой адрес — ссылка в никуда, а не отсутствие ссылки."""
    root = tree(tmp_path, {"README.md": "[витрина]()\n"})
    assert run(root, "README.md") == FOUND


def test_target_outside_the_tree_is_found(tmp_path: Path, capsys):
    """Цель за пределами дерева — находка, даже если файл по ней есть."""
    root = tree(tmp_path, {"docs/architecture.md": "[наружу](../../etc/hosts)\n"})
    assert run(root, "docs/architecture.md") == FOUND
    assert "за пределы дерева" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Названные границы: чего гейт не ловит
# --------------------------------------------------------------------------- #


def test_external_address_is_not_fetched(tmp_path: Path):
    """Внешний адрес не запрашивается: сетевой шаг был бы недетерминирован."""
    root = tree(tmp_path, {"README.md": "[витрина](https://example.invalid/нет)\n"})
    assert run(root, "README.md") == CLEAN


def test_anchor_is_not_resolved_but_its_file_is(tmp_path: Path):
    """У ``файл.md#раздел`` проверяется файл; раздел — граница, а не проверка."""
    root = tree(
        tmp_path,
        {
            "README.md": "[раз](#нет-такого-раздела) и [два](docs/нет.md#раздел)\n",
            "docs/architecture.md": "# Решения\n",
        },
    )
    assert run(root, "README.md") == FOUND
    problems = check_links.check(
        root, check_links.find_links("[раз](#нет-такого)\n", "README.md")
    )
    assert problems == []


def test_link_inside_a_fence_is_an_example(tmp_path: Path):
    """Внутри ограды кода markdown ссылки не делает — не делает и гейт."""
    text = "```markdown\n[подпись](docs/нет.md)\n```\n\nПосле: [есть](README.md)\n"
    root = tree(tmp_path, {"README.md": text})
    assert run(root, "README.md") == CLEAN


def test_link_inside_inline_code_is_an_example(tmp_path: Path):
    """Обратные кавычки внутри строки гасятся так же, как ограда.

    Без этого документ не может привести ссылку примером: `CLAUDE.md`
    объясняет правило 166 ровно таким образцом, и гейт ронял на нём сам себя.
    """
    text = "Так нельзя: `[docs/architecture.md](никуда.md)`. Вот целая: [я](README.md)\n"
    root = tree(tmp_path, {"README.md": text})
    assert run(root, "README.md") == CLEAN


def test_backticked_label_does_not_hide_its_target(tmp_path: Path):
    """Подпись в кавычках гасится, цель за скобкой — нет: она остаётся ссылкой."""
    text = "См. [`docs/нет.md`](docs/нет.md).\n"
    root = tree(tmp_path, {"README.md": text})
    assert run(root, "README.md") == FOUND


def test_line_numbers_survive_a_fence(tmp_path: Path, capsys):
    """Строки ограды не выбрасываются: номер находки обязан совпасть с файлом."""
    text = "```bash\nmake check\n```\n\nСм. [витрину](docs/нет.md).\n"
    root = tree(tmp_path, {"README.md": text})
    assert run(root, "README.md") == FOUND
    assert "README.md:5" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Третий исход: проверка не отработала
# --------------------------------------------------------------------------- #


def test_missing_document_names_the_subject(tmp_path: Path, capsys):
    """Отказ называет предмет — какой документ не прочитан (правило 158)."""
    root = tree(tmp_path, {"README.md": "[решения](docs/architecture.md)\n"})
    assert run(root, "README.md", "CONTRIBUTING.md") == REFUSED
    err = capsys.readouterr().err
    assert "CONTRIBUTING.md" in err, "причина без предмета не говорит, что чинить"
    assert "не прочитан" in err


def test_no_links_at_all_is_a_refusal(tmp_path: Path, capsys):
    """Гейт без предмета обязан падать: ноль ссылок — не ноль находок (075)."""
    root = tree(tmp_path, {"README.md": "Текст вовсе без ссылок.\n"})
    assert run(root, "README.md") == REFUSED
    assert "проверять нечего" in capsys.readouterr().err


def test_refusal_is_not_the_same_code_as_a_finding():
    """Три исхода различимы: «не отработала» — это не «нашла» и не «чисто»."""
    assert len({CLEAN, FOUND, REFUSED}) == 3


# --------------------------------------------------------------------------- #
# Живое дерево
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_declared_documents_exist():
    """Предмет назван списком, и каждый документ из него есть в дереве."""
    assert check_links.DOCUMENTS, "пустой предмет дал бы зелёный гейт без проверок"
    for name in check_links.DOCUMENTS:
        assert (project_root() / name).is_file(), f"{name}: документ предмета отсутствует"


@pytest.mark.live_surface
def test_repository_links_resolve():
    """Ссылки документации разрешаются в файлы дерева прямо сейчас."""
    root = project_root()
    links, refusals = check_links.read_documents(root, check_links.DOCUMENTS)
    assert not refusals, "\n".join(refusals)
    assert links, "в предмете не нашлось ни одной ссылки"
    problems = check_links.check(root, links)
    assert not problems, "\n".join(problems)
