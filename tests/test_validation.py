"""Тесты правил качества."""

import ast
from pathlib import Path

import pytest

from glossary.models import Glossary, Text
from glossary.validation import (
    RULES,
    Issue,
    Severity,
    ValidationConfig,
    ValidationReport,
    _cyrillic_share,
    rule_body_length,
    rule_color_group,
    rule_docs_url,
    rule_duplicate_title,
    rule_example_compiles,
    rule_examples,
    rule_id_format,
    rule_kind,
    rule_label_translated,
    rule_language_script,
    rule_non_empty,
    rule_platforms,
    rule_platforms_summary,
    rule_related_errors_resolve,
    rule_related_resolves,
    rule_required_fields,
    rule_section_size,
    rule_summary_length,
    rule_translated,
    rule_unique_id,
    rule_version_format,
    validate,
)
from tests.factories import make_entry, make_glossary

CFG = ValidationConfig()


def rules_of(report: ValidationReport, rule: str) -> tuple[Issue, ...]:
    return tuple(i for i in report.issues if i.rule == rule)


def test_valid_glossary_has_no_issues(sample_glossary: Glossary):
    assert validate(sample_glossary).issues == ()


def test_report_ok_ignores_warnings():
    report = ValidationReport(issues=(Issue(Severity.WARNING, "правило", "текст"),))
    assert report.ok
    assert report.warnings and not report.errors


def test_report_not_ok_with_errors():
    report = ValidationReport(issues=(Issue(Severity.ERROR, "правило", "текст"),))
    assert not report.ok


def test_issue_format_uses_placeholder_without_entry():
    assert "<глоссарий>" in Issue(Severity.WARNING, "r", "сообщение").format()
    assert "alpha" in Issue(Severity.ERROR, "r", "сообщение", "alpha").format()


def test_non_empty_fires_on_empty_glossary():
    """Пустой вход — ошибка входа, а не успешная проверка (каталог, 075)."""
    issues = list(rule_non_empty(Glossary(entries=()), CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]


def test_non_empty_silent_on_real_glossary(sample_glossary: Glossary):
    assert list(rule_non_empty(sample_glossary, CFG)) == []


def test_validate_fails_on_empty_glossary():
    """Полный прогон на пустых данных обязан быть красным, а не зелёным."""
    assert not validate(Glossary(entries=())).ok


@pytest.mark.parametrize("field", ["title", "kind", "section", "syntax", "docs_url"])
def test_required_fields_detects_blank(field: str):
    glossary = make_glossary(make_entry(**{field: "   "}))
    issues = list(rule_required_fields(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert field in issues[0].message


def test_id_format_rejects_anchor_breaking_characters():
    issues = list(rule_id_format(make_glossary(make_entry(id="a b#c")), CFG))
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR


def test_id_format_accepts_cyrillic_and_uppercase():
    glossary = make_glossary(
        make_entry(id="числовые-литералы"), make_entry(id="ValueError")
    )
    assert list(rule_id_format(glossary, CFG)) == []


def test_id_format_skips_empty_id():
    """Пустой id — забота rule_required_fields, дублировать ошибку не нужно."""
    assert list(rule_id_format(make_glossary(make_entry(id="")), CFG)) == []


def test_unique_id_detects_duplicates():
    glossary = make_glossary(make_entry(id="dup"), make_entry(id="dup"))
    issues = list(rule_unique_id(glossary, CFG))
    assert len(issues) == 1
    assert issues[0].entry_id == "dup"


def test_kind_rejects_unknown_value():
    issues = list(rule_kind(make_glossary(make_entry(kind="заклинание")), CFG))
    assert issues and issues[0].severity is Severity.ERROR


def test_color_group_rejects_unknown_value():
    """Незнакомая группа — новый файл в источнике, о котором витрина не знает."""
    glossary = make_glossary(make_entry(color_group="drafts"))
    issues = list(rule_color_group(glossary, CFG))
    assert issues and issues[0].severity is Severity.ERROR


def test_translated_errors_on_missing_summary_language():
    glossary = make_glossary(make_entry(summary=Text(ru="Есть.", en="")))
    issues = list(rule_translated(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "'en'" in issues[0].message


def test_translated_errors_on_missing_body():
    """Тела заполнены у всех карточек (#114) — новая карточка без тела красная."""
    glossary = make_glossary(make_entry(body=Text(ru="Есть.", en="")))
    issues = list(rule_translated(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "тело" in issues[0].message and "'en'" in issues[0].message


def test_untranslated_label_is_an_error():
    """Подписи переведены целиком (#91) — непереведённая новая карточка красная."""
    glossary = make_glossary(make_entry(title=Text(ru="Бинарный поиск", en="")))
    issues = list(rule_label_translated(glossary, CFG))
    assert [(i.severity, i.entry_id) for i in issues] == [(Severity.ERROR, "sample")]
    assert "'title'" in issues[0].message


def test_untranslated_subcat_is_found_too():
    glossary = make_glossary(make_entry(subcat=Text(ru="поиск", en="")))
    issues = list(rule_label_translated(glossary, CFG))
    assert ["'subcat'" in i.message for i in issues] == [True]


def test_code_name_label_needs_no_translation():
    """Имя из кода переводу не подлежит: совпавшие половины — норма."""
    glossary = make_glossary(make_entry(title="str.split()"))
    assert list(rule_label_translated(glossary, CFG)) == []


def test_empty_russian_label_is_a_required_field_error():
    glossary = make_glossary(make_entry(title=Text(ru="", en="split")))
    issues = list(rule_required_fields(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "'title'" in issues[0].message
    assert list(rule_label_translated(glossary, CFG)) == [], (
        "пустая русская половина — одна находка, не две"
    )


def test_russian_title_in_the_english_half_is_an_error():
    glossary = make_glossary(make_entry(title=Text(ru="Стек", en="Стек")))
    issues = list(rule_language_script(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "title" in issues[0].message


def test_all_os_passes():
    assert list(rule_platforms(make_glossary(make_entry()), CFG)) == []


def test_known_systems_subset_passes():
    glossary = make_glossary(make_entry(platforms=("Linux", "macOS")))
    assert list(rule_platforms(glossary, CFG)) == []


def test_empty_platforms_is_an_error():
    """Пустой список неотличим от «забыли заполнить»: «везде» пишется AllOS."""
    glossary = make_glossary(make_entry(platforms=()))
    assert "AllOS" in next(rule_platforms(glossary, CFG)).message


def test_unknown_platform_is_an_error():
    glossary = make_glossary(make_entry(platforms=("Unix",)))
    issues = list(rule_platforms(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "Unix" in issues[0].message


def test_all_os_does_not_combine_with_systems():
    glossary = make_glossary(make_entry(platforms=("AllOS", "Linux")))
    assert "не сочетается" in next(rule_platforms(glossary, CFG)).message


def test_all_systems_must_be_written_as_all_os():
    """«Везде» пишется одним способом: иначе витрина покажет ложный значок."""
    glossary = make_glossary(make_entry(platforms=("Linux", "macOS", "Windows")))
    assert "AllOS" in next(rule_platforms(glossary, CFG)).message


def test_repeated_platform_is_an_error():
    glossary = make_glossary(make_entry(platforms=("Linux", "Linux")))
    assert "повторяется" in next(rule_platforms(glossary, CFG)).message


def _claiming(ru: str, en: str, platforms: tuple[str, ...]) -> list[str]:
    entry = make_entry(summary=Text(ru=ru, en=en), platforms=platforms)
    return [i.message for i in rule_platforms_summary(make_glossary(entry), CFG)]


def test_unix_claim_against_all_os_is_an_error():
    """Текст и значок говорят разное — так разошлись 38 карточек (#110)."""
    issues = _claiming(
        "Посылает сигнал процессу по PID. Доступно на Unix.",
        "Send a signal to a process by PID. Availability: Unix.",
        ("AllOS",),
    )
    assert issues and "Unix" in issues[0] and "AllOS" in issues[0]


def test_claim_is_reported_once_per_system():
    """Обе половины назвали Unix — это одно расхождение, а не два."""
    issues = _claiming(
        "Посылает сигнал процессу по PID. Доступно на Unix.",
        "Send a signal to a process by PID. Availability: Unix.",
        ("AllOS",),
    )
    assert len(issues) == 1


def test_unix_claim_admits_a_narrower_set():
    """«Unix» — это Linux и macOS; одна из них — уточнение, а не спор."""
    assert (
        _claiming(
            "Возвращает расширенный атрибут. Доступно на Unix.",
            "Return an extended attribute. Availability: Unix.",
            ("Linux",),
        )
        == []
    )


def test_linux_claim_rejects_macos():
    issues = _claiming(
        "Возвращает расширенный атрибут. Доступно на Linux.",
        "Return an extended attribute. Availability: Linux.",
        ("Linux", "macOS"),
    )
    assert issues and "Linux" in issues[0]


def test_windows_claim_at_sentence_start():
    issues = _claiming(
        "Только Windows: возвращает список дисков системы.",
        "Windows only: return the list of drives on the system.",
        ("AllOS",),
    )
    assert issues and "Windows" in issues[0]


def test_mid_sentence_mention_of_another_object_is_not_a_claim():
    """«Функция os.uname — только на Unix» говорит о соседе: граница правила."""
    assert (
        _claiming(
            "Тип результата os.uname(). Сам тип есть везде, "
            "а функция os.uname — только на Unix.",
            "The result type of os.uname(). The type exists everywhere; "
            "os.uname is Unix-only.",
            ("AllOS",),
        )
        == []
    )


def test_summary_without_claim_passes():
    assert (
        _claiming(
            "Возвращает размер файла в байтах по пути к нему.",
            "Return the size of a file in bytes given its path.",
            ("Linux",),
        )
        == []
    )


# --------------------------------------------------------------------------- #
# Свойство текста, а не полнота ключей (правило каталога 077)
# --------------------------------------------------------------------------- #


def test_russian_text_in_the_english_half_is_an_error():
    """Заполненность обе половины проходят — а перевода нет."""
    russian = "Возвращает длину объекта, если у него определён метод длины."
    glossary = make_glossary(make_entry(summary=Text(ru=russian, en=russian)))
    assert list(rule_translated(glossary, CFG)) == [], (
        "полнота ключей молчит на скопированном тексте — ровно об этом правило 077"
    )
    issues = list(rule_language_script(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "summary" in issues[0].message
    assert issues[0].entry_id == "sample"


def test_cyrillic_named_as_an_example_is_not_a_finding():
    """Замер: ровно так написаны карточки string.ascii_letters и string.printable."""
    mention = (
        "This constant is ASCII and nothing else: Cyrillic letters such as "
        "«я» never appear in it, whatever the locale says about the alphabet."
    )
    glossary = make_glossary(make_entry(summary=Text(ru="Строка букв.", en=mention)))
    assert list(rule_language_script(glossary, CFG)) == []


def test_empty_english_half_is_not_this_rules_business():
    """Пустую половину судит rule_translated: у каждой находки один хозяин."""
    glossary = make_glossary(make_entry(body=Text(ru="Есть.", en="")))
    assert list(rule_language_script(glossary, CFG)) == []


@pytest.mark.parametrize(
    "text, expected",
    [("", 0.0), ("abc", 0.0), ("абв", 1.0), ("ab вг", 0.5), ("123 !", 0.0)],
    ids=["пусто", "латиница", "кириллица", "поровну", "без букв"],
)
def test_share_counts_letters_only(text: str, expected: float):
    assert _cyrillic_share(text) == expected


def test_docs_url_rejects_foreign_host():
    glossary = make_glossary(make_entry(docs_url="https://ya.ru"))
    issues = list(rule_docs_url(glossary, CFG))
    assert issues[0].severity is Severity.ERROR


def test_docs_url_warns_on_generic_root():
    glossary = make_glossary(make_entry(docs_url="https://docs.python.org/3/"))
    issues = list(rule_docs_url(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_warns_when_too_short():
    glossary = make_glossary(make_entry(summary=Text(ru="Ко", en="Short")))
    issues = list(rule_summary_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_warns_when_too_long():
    long_text = "д" * (CFG.max_summary + 1)
    glossary = make_glossary(make_entry(summary=Text(ru=long_text, en=long_text)))
    issues = list(rule_summary_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_ignores_empty_field():
    """Пустая сводка — забота rule_translated, дублировать находку не нужно."""
    glossary = make_glossary(make_entry(summary=Text(ru="", en="")))
    assert list(rule_summary_length(glossary, CFG)) == []


def test_summary_threshold_is_configurable():
    glossary = make_glossary(make_entry(summary=Text(ru="д" * 70, en="x" * 70)))
    assert list(rule_summary_length(glossary, ValidationConfig(min_summary=100)))


def test_body_length_warns_on_stub():
    glossary = make_glossary(make_entry(body=Text(ru="Коротко.", en="Short.")))
    issues = list(rule_body_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


@pytest.mark.parametrize("version", ["3", "3.x", "python3.9", "3.12+"])
def test_version_format_rejects_malformed(version: str):
    glossary = make_glossary(make_entry(version=version))
    issues = list(rule_version_format(glossary, CFG))
    assert issues[0].severity is Severity.ERROR


def test_version_format_accepts_canonical_and_empty():
    glossary = make_glossary(make_entry(version="3.12"), make_entry(version=""))
    assert list(rule_version_format(glossary, CFG)) == []


def test_examples_warns_when_absent():
    issues = list(rule_examples(make_glossary(make_entry(examples=())), CFG))
    assert issues[0].severity is Severity.WARNING


def test_example_compiles_flags_lost_indentation():
    """Блок без отступа — код, который не запустится (возражение источнику)."""
    glossary = make_glossary(make_entry(examples=("for x in range(3):", "print(x)")))
    issues = list(rule_example_compiles(glossary, CFG))
    assert issues[0].severity is Severity.WARNING
    assert "IndentationError" in issues[0].message


def test_example_compiles_flags_plain_syntax_error():
    """Прежняя эвристика «блок без отступа» такое не видела вовсе."""
    glossary = make_glossary(make_entry(examples=("def f(:",)))
    assert list(rule_example_compiles(glossary, CFG))


def test_example_compiles_silent_on_valid_code():
    glossary = make_glossary(make_entry(examples=("for x in range(3):", "    print(x)")))
    assert list(rule_example_compiles(glossary, CFG)) == []


def test_example_compiles_silent_without_examples():
    assert list(rule_example_compiles(make_glossary(make_entry(examples=())), CFG)) == []


def test_example_compiles_skips_syntax_from_a_newer_python():
    """Синтаксис 3.99 на сегодняшнем интерпретаторе не разберётся никогда.

    Находка была бы не о карточке, а о том, чем её проверяли.
    """
    glossary = make_glossary(
        make_entry(version="3.99", examples=("совершенно ((( не питон",))
    )
    assert list(rule_example_compiles(glossary, CFG)) == []


def test_example_compiles_still_judges_a_current_version():
    """Пропуск — только для будущего, а не для всякой карточки с версией."""
    glossary = make_glossary(make_entry(version="3.0", examples=("def f(:",)))
    assert list(rule_example_compiles(glossary, CFG))


def test_example_compiles_ignores_a_malformed_version_marker():
    """Форму маркера судит другое правило; здесь она не должна глушить проверку."""
    glossary = make_glossary(make_entry(version="не-версия", examples=("def f(:",)))
    assert list(rule_example_compiles(glossary, CFG))


def test_related_resolves_flags_dangling_link():
    glossary = make_glossary(make_entry(related=("нет-такого",)))
    issues = list(rule_related_resolves(glossary, CFG))
    assert issues[0].severity is Severity.WARNING
    assert "нет-такого" in issues[0].message


def test_related_resolves_accepts_existing_link():
    glossary = make_glossary(make_entry(id="a", related=("b",)), make_entry(id="b"))
    assert list(rule_related_resolves(glossary, CFG)) == []


def test_related_errors_resolve_ignores_case():
    """Источник хранит имя ``IndexError``, id карточки-исключения — в нижнем."""
    glossary = make_glossary(
        make_entry(id="a", related_errors=("IndexError",)),
        make_entry(id="indexerror", title="IndexError", kind="exception"),
    )
    assert list(rule_related_errors_resolve(glossary, CFG)) == []


def test_related_errors_resolve_flags_unknown_name():
    glossary = make_glossary(make_entry(id="a", related_errors=("НетТакойОшибки",)))
    issues = list(rule_related_errors_resolve(glossary, CFG))
    assert issues[0].severity is Severity.WARNING
    assert "НетТакойОшибки" in issues[0].message


def test_related_errors_resolve_flags_non_exception():
    """Ссылка на не-исключение обещает читателю не то, что покажет."""
    glossary = make_glossary(
        make_entry(id="a", related_errors=("len",)),
        make_entry(id="len", title="len()", kind="function"),
    )
    issues = list(rule_related_errors_resolve(glossary, CFG))
    assert issues and "не исключение" in issues[0].message


def test_duplicate_title_reports_all_locations():
    glossary = make_glossary(
        make_entry(id="a", title="len()", section="Первый"),
        make_entry(id="b", title="len()", section="Второй"),
    )
    issues = list(rule_duplicate_title(glossary, CFG))
    assert len(issues) == 1
    assert "Первый" in issues[0].message and "Второй" in issues[0].message


def test_section_size_warns_on_thin_section():
    glossary = make_glossary(make_entry(id="a", section="Крошечный"))
    issues = list(rule_section_size(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_validate_accepts_custom_rule_set():
    glossary = make_glossary(make_entry(id="плохой id", color_group="нет"))
    report = validate(glossary, rules=[rule_color_group])
    assert report.by_rule() == {"color-group": 1}


def test_all_rules_are_registered():
    """Каждое правило модуля должно попасть в реестр — иначе оно не работает."""
    expected = {
        rule_body_length,
        rule_color_group,
        rule_docs_url,
        rule_duplicate_title,
        rule_example_compiles,
        rule_examples,
        rule_id_format,
        rule_kind,
        rule_label_translated,
        rule_language_script,
        rule_non_empty,
        rule_platforms,
        rule_platforms_summary,
        rule_related_errors_resolve,
        rule_related_resolves,
        rule_required_fields,
        rule_section_size,
        rule_summary_length,
        rule_translated,
        rule_unique_id,
        rule_version_format,
    }
    assert set(RULES) == expected


def test_rule_names_are_unique_and_stable():
    """Имена правил — публичный контракт: по ним фильтруют отчёт в CI."""
    glossary = make_glossary(
        make_entry(
            id="a b",
            kind="ничто",
            color_group="нет",
            docs_url="https://ya.ru",
            version="4.0.1",
            related=("нет-такого",),
        )
    )
    names = {i.rule for i in validate(glossary).issues}
    assert names <= {
        "body-length",
        "color-group",
        "docs-url",
        "duplicate-title",
        "example-compiles",
        "examples",
        "id-format",
        "kind",
        "label-translated",
        "platforms",
        "platforms-summary",
        "related-errors-resolve",
        "related-resolves",
        "required-fields",
        "section-size",
        "summary-length",
        "translated",
        "unique-id",
        "version-format",
    }


# --------------------------------------------------------------------------- #
# У правила две защиты с разной слепотой (правило каталога 072)
# --------------------------------------------------------------------------- #


def exercised_rules() -> set[str]:
    """Правила, которые хоть один тест этого набора зовёт напрямую.

    Разбор, а не поиск подстроки: имя правила встречается и в списке импорта, и
    в перечислении реестра, и оба раза это не вызов (правило 166 о том же —
    искать надо предмет, а не его написание).

    Returns:
        Имена вызванных правил.
    """
    module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    return {
        node.func.id
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_every_rule_has_a_forgery_of_its_own():
    """Первая защита: правило показано СРАБОТАВШИМ на подделанной карточке.

    Правило каталога 072: защит должно быть две, и слепы они в разных местах.
    Вторая здесь — утверждение о снимке (``test_data_has_no_validation_errors``):
    она говорит, что данные чисты, и молчит о том, способно ли правило вообще
    покраснеть. Эта — наоборот. Ни одна не заменяет другую.
    """
    called = exercised_rules()
    silent = sorted(rule.__name__ for rule in RULES if rule.__name__ not in called)
    assert not silent, (
        "правила реестра не показаны сработавшими ни на одной подделке: "
        + ", ".join(silent)
        + ". Правило, ни разу не покрасневшее, зелено неизвестно о чём"
    )


def test_the_forgery_search_can_actually_come_up_empty():
    """Разбор обязан уметь не найти, иначе его молчание ничего не значит."""
    assert "rule_такого_нет" not in exercised_rules()
