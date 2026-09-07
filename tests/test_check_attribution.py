"""Атрибуция и трейлеры: правила каталога 123 и 156.

Набор держит три разные вещи. **Разбор трейлера** — чистая функция, и её
проверяют предметом, который она обязана отвергнуть: прозаическим упоминанием
ключа в теле сообщения. **Список в силе** — пересечение основы и рабочего
дерева: личность, объявленная тем же заходом, что и подписанные ею коммиты, в
силу не входит. **Утверждение о живой истории** — что имена в ней сходятся со
списком — проверяется отдельно и своими словами (правило 146).

Предмет отказа не выдуман. Правило 156 родилось у каталога ровно на нём: гейт
принял за соавтора середину фразы «github-actions[bot] в уплотнённый коммит».
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import check_attribution as attribution
from glossary.loader import project_root

PROSE_MENTION = """fix: разобраться с подписью бота

Раньше Co-Authored-By: github-actions[bot] в уплотнённый коммит попадал
случайно, и гейт принимал середину этой фразы за директиву.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
"""

TRAILERS_NOT_LAST = """feat: что-то сделано

Co-Authored-By: Кто-то <кто@то.рф>

А потом абзац прозы, и хвостового блока у сообщения больше нет.
"""

MIXED_TAIL = """feat: что-то сделано

Co-Authored-By: Кто-то <кто@то.рф>
и ещё строка прозой в том же абзаце
"""

CLEAN_TAIL = """feat: что-то сделано

Тело сообщения.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_x
"""


# --------------------------------------------------------------------------- #
# Трейлер читается только из хвостового блока (правило 156)
# --------------------------------------------------------------------------- #


def test_prose_mention_is_not_a_trailer():
    """Тот самый предмет, на котором правило 156 родилось у каталога."""
    found = attribution.trailers(PROSE_MENTION)
    assert found["co-authored-by"] == ["Claude Opus 5 <noreply@anthropic.com>"], (
        "упоминание ключа в теле сообщения принято за директиву — ровно то, "
        "против чего правило 156"
    )


def test_trailers_must_be_the_last_paragraph():
    assert attribution.trailers(TRAILERS_NOT_LAST) == {}


def test_paragraph_with_prose_is_not_a_block():
    """Хвостовым блоком абзац является ЦЕЛИКОМ либо не является вовсе."""
    assert attribution.trailers(MIXED_TAIL) == {}


def test_clean_tail_is_read_whole():
    found = attribution.trailers(CLEAN_TAIL)
    assert set(found) == {"co-authored-by", "claude-session"}


@pytest.mark.parametrize("message", ["", "\n\n", "просто строка без трейлеров"])
def test_message_without_a_block(message: str):
    assert attribution.trailer_block(message) == []


# --------------------------------------------------------------------------- #
# Имя сверяется со списком (правило 123)
# --------------------------------------------------------------------------- #

KNOWN = attribution.InForce(frozenset({"Свой <свой@тут.рф>", "Соавтор <со@тут.рф>"}))
"""Список, действующий для диапазона: расширений и закрытий в нём нет."""


def commit(author: str, message: str = "feat: что-то") -> attribution.Commit:
    return attribution.Commit("abc1234", author, message)


def test_known_author_passes():
    assert attribution.findings([commit("Свой <свой@тут.рф>")], KNOWN) == []


def test_unknown_author_is_a_finding():
    problems = attribution.findings([commit("Чужой <чужой@там.рф>")], KNOWN)
    assert len(problems) == 1
    assert "abc1234" in problems[0], "находка обязана назвать коммит (правило 158)"
    assert "Чужой" in problems[0]


def test_unknown_coauthor_is_a_finding():
    message = "feat: что-то\n\nCo-Authored-By: Чужой <чужой@там.рф>\n"
    problems = attribution.findings([commit("Свой <свой@тут.рф>", message)], KNOWN)
    assert len(problems) == 1
    assert "соавтор" in problems[0]


def test_prose_mention_does_not_produce_a_finding():
    """Красное на верном коде приучает читать красное как фон (правило 051)."""
    message = (
        "fix: подпись\n\nЗдесь Co-Authored-By: Чужой <чужой@там.рф> назван прозой,\n"
        "и это не директива.\n\nCo-Authored-By: Соавтор <со@тут.рф>\n"
    )
    assert attribution.findings([commit("Свой <свой@тут.рф>", message)], KNOWN) == []


# --------------------------------------------------------------------------- #
# Список в силе: расширение отложено, сужение действует сразу
# --------------------------------------------------------------------------- #

ROSTER = """# Комментарий и пустая строка пропускаются.

Свой <свой@тут.рф>
закрыто: Прежний <прежний@тут.рф>
"""


def test_roster_reads_three_states():
    """Действующая, закрытая и отсутствующая — три разных ответа, а не два."""
    names = attribution.parse_roster(ROSTER)
    assert names.active == frozenset({"Свой <свой@тут.рф>"})
    assert names.retired == frozenset({"Прежний <прежний@тут.рф>"})
    assert "Прежний <прежний@тут.рф>" in names.declared, (
        "закрытая личность остаётся ОБЪЯВЛЕННОЙ: она лежит в истории"
    )


def test_retired_mark_tolerates_spacing():
    names = attribution.parse_roster("закрыто:Плотно <плотно@тут.рф>")
    assert names.retired == frozenset({"Плотно <плотно@тут.рф>"})


def between(base: str, head: str) -> attribution.InForce:
    """Список в силе для пары «основа — рабочее дерево»."""
    return attribution.InForce.between(
        attribution.parse_roster(base), attribution.parse_roster(head)
    )


def test_identity_added_by_the_same_change_is_not_in_force():
    """ТОТ САМЫЙ ПРЕДМЕТ: сторож не расширяет собственный список своим заходом."""
    names = between("Свой <свой@тут.рф>", "Свой <свой@тут.рф>\nНовый <новый@там.рф>")
    assert names.pending == frozenset({"Новый <новый@там.рф>"})
    problems = attribution.findings([commit("Новый <новый@там.рф>")], names)
    assert len(problems) == 1
    assert "этим же изменением" in problems[0], (
        "находка обязана назвать причину: имя объявлено тем же заходом, "
        "а не отсутствует вовсе — это разные ответы (правило 039)"
    )


def test_identity_from_the_base_stays_in_force():
    names = between("Свой <свой@тут.рф>", "Свой <свой@тут.рф>\nНовый <новый@там.рф>")
    assert attribution.findings([commit("Свой <свой@тут.рф>")], names) == []


def test_retired_identity_is_closed_by_this_very_change():
    """Сужение не откладывается: закрытие действует тем же заходом."""
    names = between("Свой <свой@тут.рф>", "закрыто: Свой <свой@тут.рф>")
    problems = attribution.findings([commit("Свой <свой@тут.рф>")], names)
    assert len(problems) == 1
    assert "закрытая личность" in problems[0]


def test_retired_identity_is_allowed_in_existing_history():
    """История общей ветки не перезаписывается — закрытие смотрит вперёд."""
    names = attribution.InForce.as_declared(
        attribution.parse_roster("закрыто: Прежний <прежний@тут.рф>")
    )
    assert attribution.findings([commit("Прежний <прежний@тут.рф>")], names) == []


def test_reopening_an_identity_also_waits_for_the_next_change():
    """Снятие закрытия — расширение, и оно тоже вступает в силу следующим."""
    names = between("закрыто: Свой <свой@тут.рф>", "Свой <свой@тут.рф>")
    problems = attribution.findings([commit("Свой <свой@тут.рф>")], names)
    assert len(problems) == 1
    assert "этим же изменением" in problems[0]


def test_coauthor_is_measured_by_the_same_list():
    names = between("Свой <свой@тут.рф>", "Свой <свой@тут.рф>\nНовый <новый@там.рф>")
    message = "feat: что-то\n\nCo-Authored-By: Новый <новый@там.рф>\n"
    problems = attribution.findings([commit("Свой <свой@тут.рф>", message)], names)
    assert len(problems) == 1
    assert "соавтор" in problems[0]


@pytest.mark.parametrize(
    "commit_range",
    ["HEAD", "..HEAD", "origin/main..", "origin/main...HEAD"],
)
def test_range_without_a_base_is_the_third_outcome(commit_range: str):
    """Диапазон, не называющий основу, — отказ, а не сверка с рабочим деревом.

    Молчаливый откат к списку из рабочего дерева вернул бы ровно ту дыру, ради
    которой механизм заведён, и не сказал бы об этом ничего.
    """
    with pytest.raises(attribution.NotRunError) as refusal:
        attribution.base_of(commit_range)
    assert commit_range in str(refusal.value), "третий исход обязан назвать предмет"


def test_base_of_a_plain_range():
    assert attribution.base_of("origin/main..HEAD") == "origin/main"


# --------------------------------------------------------------------------- #
# Исходы и утверждение о живой истории
# --------------------------------------------------------------------------- #


def test_missing_list_is_the_third_outcome(tmp_path: Path):
    absent = tmp_path / "нет.txt"
    with pytest.raises(attribution.NotRunError) as refusal:
        attribution.roster(absent)
    assert str(absent) in str(refusal.value), "третий исход обязан назвать предмет"


def test_bad_range_is_the_third_outcome(capsys):
    assert attribution.main(["--range", "нет-такой-ревизии..HEAD"]) == attribution.NOT_RUN
    error = capsys.readouterr().err
    assert "не отработала" in error
    assert "нет-такой-ревизии" in error


@pytest.mark.live_surface
def test_repository_list_is_declared():
    """У гейта должен быть предмет: списка нет — сверять не с чем (075)."""
    assert attribution.roster().active, "действующих личностей объявлено ноль"


@pytest.mark.live_surface
def test_repository_list_is_readable_from_a_revision():
    """Список в силе берётся из ревизии — значит, путь обязан там разрешаться.

    Утверждение о живом дереве, а не о разборе: имя файла внутри дерева задано
    константой, и опечатка в ней делает гейт не строгим, а неработающим —
    третьим исходом на каждом запуске. Сравнивать содержимое ревизии с рабочим
    деревом здесь нельзя: изменение, правящее список, тем и занято, что их
    разводит.
    """
    assert attribution.roster_at("HEAD").declared, (
        f"{attribution.IN_TREE} в ревизии HEAD не читается или пуст — путь "
        "разъехался с константой, и гейт стал бы третьим исходом на каждом "
        "запуске вместо сверки"
    )


MIN_HISTORY = 2
"""Меньше двух коммитов — диапазона не построить, и сверять нечего."""


def git(*args: str) -> str:
    """Тот же git по имени из PATH, что зовёт и сам гейт."""
    # S603/S607 сняты по той же причине, что и в самом гейте: git зовётся по
    # имени из PATH, а команда собрана из констант набора.
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project_root(),
        check=True,
        timeout=attribution.TIMEOUT,
    ).stdout.strip()


def available_range(depth: int = 20) -> str | None:
    """Диапазон истории, который есть в этом клоне, либо ``None``.

    ``None`` — не «история чиста», а «сверять не с чем»: клон неглубокий либо
    несёт единственный коммит (правило 039).

    Args:
        depth: Сколько коммитов взять, если их столько есть.

    Returns:
        Диапазон в записи git; ``None`` — истории для сверки нет.
    """
    if git("rev-parse", "--is-shallow-repository") == "true":
        return None
    total = int(git("rev-list", "--count", "HEAD"))
    if total < MIN_HISTORY:
        return None
    return f"HEAD~{min(depth, total - 1)}..HEAD"


@pytest.mark.live_surface
def test_recent_history_matches_the_declared_list():
    """Утверждение о живой истории, отдельно от проверки разбора (146).

    ЗАМЕР. Первый прогон набора в CI покраснел здесь — и не на дереве, а на
    собственной арифметике этой проверки: матрица тестов берёт клон глубиной
    один коммит, счёт давал 1, диапазон складывался в пустой ``HEAD~0..HEAD``,
    и сообщение «история пуста» говорило о клоне, а не об атрибуции. Ровно та
    склейка, против которой заведён третий исход: «не нашли» и «нечего
    смотреть» — разные ответы (правило 039).
    """
    history = available_range()
    if history is None:
        pytest.skip(
            "клон неглубокий либо несёт единственный коммит — сверять не с чем. "
            "Живую историю смотрит прогон «Атрибуция коммитов изменения»: он "
            "берёт её целиком (fetch-depth: 0 в .github/workflows/ci.yml)"
        )
    commits = attribution.read_history(history)
    assert commits, f"в диапазоне {history} нет коммитов — гейт смотрел бы в пустоту"
    names = attribution.InForce.as_declared(attribution.roster())
    problems = attribution.findings(commits, names)
    assert not problems, "\n".join(problems)
