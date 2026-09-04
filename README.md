# Glossary Python

[![CI](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/ci.yml/badge.svg)](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/ci.yml)
[![Публикация витрины](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/pages.yml/badge.svg)](https://github.com/ArtVsMark/Glossary-Python/actions/workflows/pages.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Справочник стандартной библиотеки Python на русском языке: **581 карточка**
в **43 разделах**. Каждая карточка — описание, синтаксис, исполняемые примеры,
минимальная версия Python и ссылка на официальную документацию.

Репозиторий — это витрина и инструменты вокруг неё. Живой глоссарий ведётся как
база знаний внутри проекта Stepik-Python-Grader; сюда данные попадают в виде
выгрузки, проходят проверку качества и собираются в одностраничный HTML.

## Что внутри

| Компонент | Назначение |
| --- | --- |
| `data/glossary.json` | Источник истины: все карточки и версия формата |
| `data/glossary.schema.json` | JSON Schema — автодополнение и проверка в IDE |
| `python_glossary.html` | Собранная витрина: поиск, фильтры, тёмная тема, работает офлайн |
| `src/glossary/` | Пакет: валидация, сборка витрины, экспорт, CLI |
| `tests/` | Тесты кода и контракта данных |

Витрина — один самодостаточный HTML-файл: данные встроены в страницу, внешних
запросов при работе нет.

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
```

Пакет запускается и как модуль: `python -m glossary …`. Runtime-зависимостей нет —
достаточно интерпретатора Python 3.11+.

## Качество данных

Валидатор — это реестр независимых правил. Ошибки ломают сборку в CI,
предупреждения формируют бэклог по контенту и не блокируют работу.

| Правило | Уровень | Что проверяет |
| --- | --- | --- |
| `required-fields` | ошибка | Все текстовые поля карточки заполнены |
| `id-format` | ошибка | Идентификатор пригоден как якорь URL |
| `unique-id` | ошибка | Идентификаторы не повторяются |
| `color-group` | ошибка | Цветовая группа известна витрине |
| `docs-url` | ошибка / предупреждение | Ссылка ведёт на docs.python.org и указывает на конкретный раздел |
| `description-length` | ошибка / предупреждение | Описание от 60 до 400 символов |
| `version-format` | ошибка / предупреждение | Маркер версии записан как `3.N+` |
| `examples-depth` | предупреждение | В карточке больше одной строки примеров |
| `duplicate-name` | предупреждение | Одинаковые имена в разных разделах |
| `group-size` | предупреждение | Раздел не состоит из одной карточки |

Текущее состояние: **0 ошибок, 93 предупреждения**. Число предупреждений
зафиксировано в `tests/quality_baseline.json` — храповик не даёт замечаниям
расти и напоминает опустить планку, когда данные становятся чище.

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
