# Glossary Python

[![CI](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/ci.yml/badge.svg)](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/ci.yml)
[![Публикация витрины](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/pages.yml/badge.svg)](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/pages.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Карточек](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FArtVsMark%2FGlossary-Python%2Fbadges%2F.github%2Fbadges%2Fcards.json)](data/glossary.json)
[![Замечаний](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FArtVsMark%2FGlossary-Python%2Fbadges%2F.github%2Fbadges%2Fwarnings.json)](#качество-данных)
[![Правил без механизма](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FArtVsMark%2FGlossary-Python%2Fbadges%2F.github%2Fbadges%2Frules.json)](#правила-проекта)

### → [Открыть глоссарий](https://artvsmark.github.io/Glossary-Python/)

Двуязычный справочник стандартной библиотеки Python: **<!--m:cards-->1349<!--/m:cards--> карточка**
в **<!--m:groups-->55<!--/m:groups--> разделах**. Каждая карточка — краткая сводка и развёрнутый разбор
на русском и английском, синтаксис, исполняемые примеры, синонимы для поиска,
связи с соседними темами, версия Python и ссылка на официальную документацию.

Репозиторий — витрина и инструменты вокруг неё. **Содержание ведётся не здесь:**
живой глоссарий — база знаний внутри Stepik-Python-Grader, откуда карточки
приезжают импортом, проходят проверку качества и собираются в одностраничный
HTML. Замечания к содержанию едут обратно письмом (`make objections`), а не
правкой на месте.

## Что внутри

| Компонент | Назначение |
| --- | --- |
| `data/glossary.json` | Снимок карточек из источника и версия формата (производный, вручную не правится) |
| `data/glossary.schema.json` | JSON Schema — автодополнение и проверка в IDE |
| `python_glossary.html` | Собранная витрина: поиск, фильтры, тёмная тема, работает офлайн |
| `src/glossary/` | Пакет: валидация, сборка витрины, экспорт, CLI |
| `scripts/import_from_grader.py` | Импорт карточек из клона Stepik-Python-Grader |
| `tests/` | Тесты кода и контракта данных |

Витрина — один самодостаточный HTML-файл: данные, стили и скрипт встроены
в страницу, внешних запросов при работе нет — ни шрифтов, ни CDN. Кнопка
**«Скачать»** отдаёт сам этот файл: страница сохраняет свою исходную копию,
а не текущее состояние с чужим поиском и открытыми карточками.

Опубликованные адреса:

| Адрес | Что отдаёт |
| --- | --- |
| [`/Glossary-Python/`](https://artvsmark.github.io/Glossary-Python/) | Витрина: поиск, фильтры, тёмная тема |
| [`/Glossary-Python/glossary.json`](https://artvsmark.github.io/Glossary-Python/glossary.json) | Снимок карточек обычным HTTP — без клона и без токена |
| [`badges/.github/badges/facts.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/facts.json) | Числа о проекте: карточки, разделы, замечания, состав ответа каталогу |
| [`badges/.github/badges/objections.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/objections.json) | Замечания к содержанию: правило, уровень, область, полный список карточек |
| [`badges/.github/badges/coverage.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/coverage.json) | Покрытие официального Python: чего в глоссарии нет вовсе |
| [`badges/.github/badges/whatsnew.json`](https://raw.githubusercontent.com/ArtVsMark/Glossary-Python/badges/.github/badges/whatsnew.json) | Что появилось и исчезло между версиями Python — и что из нового не описано |

Это контракты, а не удобство. Глоссарий забирают выгрузкой, а не копированием
файла из репозитория. А `objections.json` — обратный поток: карточки правятся
в источнике, замечания находятся здесь, и переносить руками список из
четырёхсот идентификаторов бессмысленно — источник читает его сам.

```jsonc
{
  "schema": 1,
  "producer": "ArtVsMark/Glossary-Python",
  "source": "ArtVsMark/Stepik-Python-Grader",
  "snapshot": { "cards": 1349, "schema_version": 2 },
  "totals": { "errors": 0, "warnings": 746, "cards_affected": 421 },
  "findings": [
    { "rule": "example-indent", "severity": "warning",
      "message": "пример открывает блок, но ни одна строка не имеет отступа…",
      "count": 97, "cards": ["бинарный-поиск", "…"] }
  ]
}
```

Отметки времени в файле нет намеренно: она меняла бы его на каждом прогоне, и
ветка копила бы коммиты «ничего не изменилось». Дата есть у самого коммита.

## Откуда берутся данные

```
Stepik-Python-Grader ──► import_from_grader.py ──► data/glossary.json ──► python_glossary.html
    (база знаний)              (импорт)               (снимок)               (витрина)
         ▲                                                  │
         └────────────── make objections ◄──────────────────┘
                     (замечания к содержанию)
```

У содержания один хозяин. Правка карточки в двух местах разъезжается на первой
же выгрузке, а спор о том, чья версия верна, решать некому — поэтому поток
односторонний, а обратно едут только замечания.

```bash
make import SOURCE=../Stepik-Python-Grader        # перечитать карточки
make import-check SOURCE=../Stepik-Python-Grader  # сверить, ничего не записывая
make objections                                   # что предъявить источнику
```

## Быстрый старт

```bash
git clone https://github.com/ArtVsMark/Glossary-Python.git
cd Glossary-Python
make install          # venv + пакет + dev-зависимости + pre-commit
make check            # линтер, типы, тесты, валидация, синхронность витрины
```

Без `make`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,schema]"
python -m glossary stats
```

## Команды

```bash
glossary stats                          # сводка: карточки, разделы, покрытие
glossary validate                       # проверка качества данных
glossary validate --strict              # предупреждения считаются ошибками
glossary validate --format json         # машиночитаемый отчёт
glossary build                          # пересобрать python_glossary.html
glossary build --check                  # витрина синхронна с данными? (для CI)
glossary export -f markdown -o out.md   # экспорт: html, json, markdown, csv
glossary objections                     # замечания к содержанию — письмом в источник
glossary objections --format json       # тот же список контрактом для машины
glossary coverage                       # чего в глоссарии нет вовсе
```

Пакет запускается и как модуль: `python -m glossary …`. Runtime-зависимостей нет —
достаточно интерпретатора Python 3.11+.

## Качество данных

Валидатор — это реестр независимых правил. Ошибки ломают сборку в CI,
предупреждения формируют бэклог по контенту и не блокируют работу.

| Правило | Уровень | Что проверяет |
| --- | --- | --- |
| `non-empty` | ошибка | Снимок не пуст: проверять нечего — это ошибка входа, а не успех |
| `required-fields` | ошибка | Обязательные текстовые поля карточки заполнены |
| `id-format` | ошибка | Идентификатор пригоден как якорь URL |
| `unique-id` | ошибка | Идентификаторы не повторяются |
| `kind` | ошибка | Вид карточки известен: понятие, функция, исключение, конструкция |
| `color-group` | ошибка | Цветовая группа известна витрине |
| `translated` | ошибка / предупреждение | Сводка есть на обоих языках; тело — желательно |
| `docs-url` | ошибка / предупреждение | Ссылка ведёт на docs.python.org и указывает на конкретный раздел |
| `version-format` | ошибка | Маркер версии записан как `N.N` либо пуст |
| `summary-length` | предупреждение | Сводка от 30 до 200 символов: помещается в список |
| `body-length` | предупреждение | Тело не короче 60 символов — иначе оно не добавляет к сводке ничего |
| `examples` | предупреждение | У карточки есть хотя бы один пример |
| `example-indent` | предупреждение | Пример, открывающий блок, содержит строку с отступом |
| `related-resolves` | предупреждение | Связь «см. также» ведёт на существующую карточку |
| `duplicate-title` | предупреждение | Одинаковые имена в разных разделах |
| `section-size` | предупреждение | Раздел не состоит из одной карточки |

Все замечания адресованы источнику: карточки правятся там. `make objections`
собирает их в готовый к отправке отчёт — правило, сколько карточек задето и
какие именно.

## Полнота: чего нет вовсе

Валидатор судит написанные карточки. Ненаписанные считает `make coverage`:
инвентарь языка снимается **интроспекцией работающего интерпретатора** — без
сети и без разбора документации, — и сопоставляется с карточками точным
совпадением полного имени (`functools.reduce`, `str.split`).

Ответ зависит от версии Python и потому назван в отчёте: **версия здесь ось
измерения, а не настройка**. Инвентарь снимается на каждой версии матрицы, а
разность соседних отвечает на вопрос «что появилось в 3.14» — тот самый, за
которым обычно идут в раздел What's New, только вычитанием, без сети и без
разбора чужой вёрстки:

```bash
glossary inventory -o inventory-3.13.json   # на 3.13
glossary inventory -o inventory-3.14.json   # на 3.14
python scripts/whatsnew.py inventory-*.json # что появилось и что исчезло
```

Ценность не в списке нового, а в его пересечении с глоссарием: у каждой
появившейся сущности стоит `documented` — есть ли о ней карточка. Появилось в
языке и не описано — это очередь на завтра.

Python 3.15 снимается отдельным прогоном с правом упасть: заморозка
возможностей на нём уже прошла, поэтому список практически финальный, но
ронять из-за release candidate публикацию незачем.

Граница названа прямо: интроспекция видит объекты, а не текст. Синтаксис
(`match`, walrus, спецификаторы f-строк), устаревания и удаления в неё не
попадают — эти пласты не измеряются, и это записано, а не умолчано.

Текущее состояние: **<!--m:errors-->0<!--/m:errors--> ошибок, <!--m:warnings-->746<!--/m:warnings--> предупреждения**. Число предупреждений
зафиксировано в `tests/quality_baseline.json` — храповик не даёт замечаниям
расти и напоминает опустить планку, когда данные становятся чище.

## Правила проекта

Проект подключён к каталогу правил
[Engineering-Incidents-Playbook](https://github.com/ArtVsMark/Engineering-Incidents-Playbook)
— своду инженерных правил, каждое из которых выросло из конкретного инцидента.

| Файл | Что это |
| --- | --- |
| `.rules/bindings.json` | Ответ проекта по каждому правилу каталога: действует и чем · отклонено и почему · нет предмета · ещё не смотрели |
| `.rules/proposals.json` | Канал обратно: правило, родившееся здесь, едет в каталог |
| `.github/workflows/rules-inbox.yml` | Ежедневные «входящие»: очередь неотвеченных правил и то, что уже решено у соседних проектов |
| `tests/test_rules_bindings.py` | Гейт на форму ответа: разрешимость адресов, причина у каждого `none`, потолок правил без механизма |

Набор собран командой каталога `onboard_consumer.py`, а не перенесён руками:
копия генератора в каждом проекте — это N реализаций одного алгоритма.

Разобраны все **<!--m:rules_total-->179<!--/m:rules_total-->** правил каталога, `unreviewed` не осталось:

| Ответ | Сколько | Что означает |
| --- | --- | --- |
| `active` + механизм | <!--m:rules_mechanised-->67<!--/m:rules_mechanised--> | Правило действует и держится гейтом (<!--m:rules_gate-->34<!--/m:rules_gate-->), документом (<!--m:rules_document-->27<!--/m:rules_document-->) или конвейером (<!--m:rules_pipeline-->6<!--/m:rules_pipeline-->) |
| `active` + `none` | <!--m:rules_none-->35<!--/m:rules_none--> | Правило действует, но здесь ничем не держится — у каждого названа причина |
| `not-applicable` | <!--m:rules_na-->77<!--/m:rules_na--> | Предмета правила в этом проекте нет — с объяснением, почему |

**<!--m:rules_none-->35<!--/m:rules_none--> — это метрика, и она должна уменьшаться.** Потолок зафиксирован в
`tests/test_rules_bindings.py` и двигается только вниз, как и храповик качества
данных. Растворённая в тексте метрика выглядит отсутствующей.

Форму ответа держит гейт: механизм обязан назвать **разрешимый адрес** — путь,
который действительно существует в репозитории. Гейт покраснел на первом же
прогоне, поймав нераспознанный адрес: проверка, которая ни разу не краснела,
обычно ничего не проверяет.

Первая находка каталога в этом проекте — правило
[075](https://github.com/ArtVsMark/Engineering-Incidents-Playbook/blob/main/rules/ru/075-a-guard-that-finds-nothing-must-fail.md):
валидатор на пустых данных отвечал «ошибок 0» и возвращал успех. Закрыто
правилом `non-empty` и отказом собирать пустую витрину.

## Как править глоссарий

Витрина — производный артефакт. Правится только `data/glossary.json`, после чего
страница пересобирается:

```bash
$EDITOR data/glossary.json
make validate                 # что сломалось?
make build                    # пересобрать витрину
git add data/glossary.json python_glossary.html
```

Правки прямо в `python_glossary.html` будут потеряны при следующей сборке — CI
проверяет синхронность и не пропустит расхождение. Подробности —
в [CONTRIBUTING.md](CONTRIBUTING.md), архитектурные решения —
в [docs/architecture.md](docs/architecture.md).

## Лицензия

Код — [MIT](LICENSE). Тексты карточек ссылаются на официальную документацию
Python, распространяемую по [лицензии PSF](https://docs.python.org/3/license.html).
