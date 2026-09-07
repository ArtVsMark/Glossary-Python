"""Что витрина завела на машине читателя, она обязана уметь удалить: правило 112.

Правило каталога 112: у всякого накопления, заведённого продуктом, есть штатная
команда удаления. «Почистите хранилище браузера руками» способом не является:
читатель этих ключей не создавал и знать о них не обязан.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. Витрина писала в ``localStorage`` два ключа
— тему и язык — четырьмя разными местами кода, а команды удаления не имела
вовсе. Ответ проекта по правилу при этом гласил «накоплений, заведённых
продуктом на машине пользователя, нет»: вердикт был верен когда-то и не
перечитывался.

Держится здесь ОДНА вещь, зато машинная: **всякий ключ проходит через список**
``STORE``. Литеральный ключ в обращении к хранилищу — находка, потому что
сбросить его нечем: сброс перебирает список, а не ищет ключи по дереву.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **точность подсказки.** Строка ``resetHint`` перечисляет удаляемое прозой;
  третий ключ, добавленный в ``STORE``, подсказку не обновит, и гейт смолчит —
  он сверяет обращения к хранилищу, а не текст о них;
* **другие хранилища.** ``sessionStorage``, ``indexedDB`` и ``document.cookie``
  разбираются наравне с ``localStorage``, но хранилище, названное иначе, в
  словарь не попадёт и останется невидимым;
* **исполнение.** Что кнопка действительно очищает хранилище, проверяется
  чтением кода, а не браузером: живой поверхности у прогона нет (правило 037).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from glossary.loader import project_root

TEMPLATE = project_root() / "src" / "glossary" / "templates" / "showcase.html"

STORAGES = ("localStorage", "sessionStorage", "indexedDB")
"""Хранилища браузера, обращения к которым разбираются."""

ACCESS = re.compile(
    r"(?P<storage>" + "|".join(STORAGES) + r")\.(?P<method>\w+)\(\s*(?P<key>[^,)\s]+)"
)
"""Обращение к хранилищу: имя, метод и первый аргумент."""

STORE_DECLARATION = re.compile(r"const STORE = \{(?P<body>[^}]*)\}")
KEY_NAME = re.compile(r"(\w+)\s*:\s*\"(?P<value>[^\"]+)\"")

LITERAL = re.compile(r"^[\"']")
"""Признак литерального ключа: строка вместо обращения к списку."""

RESET_BODY = re.compile(r"function resetPreferences\(\)\s*\{(?P<body>.*?)\n\}", re.DOTALL)
LANGUAGES = 2
"""Сколько локалей у витрины: подпись обязана быть в каждой."""

FORGED_LITERAL = """
const STORE = { theme:"glossary-theme" };
localStorage.setItem("glossary-filters", value);
"""

FORGED_WHOLE = """
const STORE = { theme:"glossary-theme" };
localStorage.setItem(STORE.theme, value);
"""


def declared_keys(source: str) -> dict[str, str]:
    """Ключи, объявленные в списке ``STORE``.

    Args:
        source: Текст шаблона витрины.

    Returns:
        Отображение «имя поля → значение ключа»; пусто — списка нет.
    """
    declaration = STORE_DECLARATION.search(source)
    if declaration is None:
        return {}
    return {
        match.group(1): match.group("value")
        for match in KEY_NAME.finditer(declaration.group("body"))
    }


def reset_body(source: str) -> str:
    """Тело функции сброса.

    Args:
        source: Текст шаблона витрины.

    Returns:
        Тело функции; пустая строка — функции нет.
    """
    found = RESET_BODY.search(source)
    return found.group("body") if found else ""


def quiet_call(body: str, name: str) -> bool:
    """Зовётся ли функция с признаком «не сохранять» последним аргументом.

    Аргументы читаются до конца оператора, а не до первой скобки: у вызова
    внутри сброса есть вложенные — ``matchMedia("(prefers-color-scheme: …)")``.

    Args:
        body: Текст, в котором ищется вызов.
        name: Имя вызываемой функции.

    Returns:
        ``True`` — вызов найден и последним аргументом идёт ``false``.
    """
    return re.search(rf"{name}\(.*,\s*false\s*\);", body) is not None


def findings(source: str) -> tuple[list[str], int]:
    """Обращения к хранилищу мимо списка и число разобранных обращений.

    Второе число нужно само по себе: ноль находок при нуле обращений означает
    не «чисто», а «нечего смотреть» (правила 039, 146).

    Args:
        source: Текст шаблона витрины.

    Returns:
        Готовые к печати находки и число разобранных обращений.
    """
    problems: list[str] = []
    seen = 0
    for match in ACCESS.finditer(source):
        seen += 1
        key = match.group("key")
        if LITERAL.match(key):
            problems.append(
                f"{match.group('storage')}.{match.group('method')}({key}…): "
                "ключ записан литералом мимо списка STORE — сбросить его нечем, "
                "а сброс перебирает список (правило 112)"
            )
    return problems, seen


# --------------------------------------------------------------------------- #
# Гейт умеет краснеть: подделки шаблона
# --------------------------------------------------------------------------- #


def test_literal_key_is_a_finding():
    problems, seen = findings(FORGED_LITERAL)
    assert seen == 1
    assert len(problems) == 1
    assert "glossary-filters" in problems[0]


def test_key_from_the_list_is_silent():
    problems, seen = findings(FORGED_WHOLE)
    assert seen == 1
    assert problems == []


def test_source_without_storage_looked_nowhere():
    """«Не нашли» и «нечего смотреть» — разные ответы (правило 039)."""
    problems, seen = findings("const x = 1;")
    assert problems == []
    assert seen == 0


@pytest.mark.parametrize(
    "storage", STORAGES, ids=["localStorage", "sessionStorage", "indexedDB"]
)
def test_every_storage_of_the_dictionary_is_read(storage: str):
    problems, seen = findings(f'{storage}.setItem("что-то", 1);')
    assert seen == 1
    assert len(problems) == 1


def test_call_without_the_flag_is_not_quiet():
    """Признак «не сохранять» ищется, а не предполагается.

    Вложенная скобка в аргументе взята из живой витрины: разбор «до первой
    закрывающей» на ней и спотыкался.
    """
    nested = 'setTheme(matchMedia("(prefers-color-scheme: dark)").matches ? "d" : "l"'
    assert not quiet_call(f"{nested});", "setTheme")
    assert quiet_call(f"{nested}, false);", "setTheme")


def test_reset_body_is_extracted():
    source = 'function resetPreferences(){\n  applyLang("ru", false);\n}\n'
    assert 'applyLang("ru", false)' in reset_body(source)
    assert reset_body("function other(){}") == ""


def test_store_declaration_is_parsed():
    assert declared_keys(FORGED_LITERAL) == {"theme": "glossary-theme"}


def test_missing_declaration_is_empty():
    assert declared_keys("const x = 1;") == {}


# --------------------------------------------------------------------------- #
# Утверждения о живой витрине (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_showcase_declares_its_storage():
    """У гейта есть предмет: списка нет — сверять не с чем (правило 075)."""
    keys = declared_keys(TEMPLATE.read_text(encoding="utf-8"))
    assert keys, "витрина не объявляет STORE — сбрасывать было бы нечего"
    assert set(keys) == {"theme", "lang"}, keys


@pytest.mark.live_surface
def test_showcase_writes_nothing_outside_the_list():
    source = TEMPLATE.read_text(encoding="utf-8")
    problems, seen = findings(source)
    assert seen, "обращений к хранилищу не найдено — разбор смотрел в пустоту"
    assert not problems, "\n".join(problems)


@pytest.mark.live_surface
def test_showcase_offers_a_deletion_command():
    """Штатная команда удаления есть, и она перебирает ВЕСЬ список."""
    source = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="resetBtn"' in source, "кнопки сброса в разметке нет"
    assert "Object.values(STORE).forEach" in source, (
        "сброс не перебирает список: удаление выбранного ключа оставляет "
        "остаток там, куда читатель не заглядывает (правило 112)"
    )


@pytest.mark.live_surface
@pytest.mark.parametrize("label", ["reset", "resetDone", "resetHint"])
def test_deletion_command_speaks_both_languages(label: str):
    """Счёт, а не текст: слова меняются, число локалей — нет."""
    source = TEMPLATE.read_text(encoding="utf-8")
    assert source.count(f'{label}:"') == LANGUAGES, (
        f"подпись {label} объявлена не во всех локалях: команда удаления, "
        "названная на одном языке, на другом читается пустотой"
    )


@pytest.mark.live_surface
def test_reset_does_not_write_the_keys_back():
    """Умолчания применяются без записи — иначе сброс создаёт ключи заново."""
    body = reset_body(TEMPLATE.read_text(encoding="utf-8"))
    assert body, "функции resetPreferences в витрине нет"
    for call in ("setTheme", "applyLang"):
        assert quiet_call(body, call), (
            f"{call} внутри сброса зовётся без признака «не сохранять»: "
            "ключ создался бы заново тем же движением, что его удалило"
        )


def test_showcase_template_exists():
    assert TEMPLATE.exists(), f"шаблона витрины нет: {TEMPLATE}"
    assert isinstance(TEMPLATE, Path)
