# Быстрый старт и команды

**Русский** · [English](getting-started.en.md)

## Состав репозитория

| Компонент | Назначение |
| --- | --- |
| `data/cards/<группа>.json` | Карточки — источник содержания, правится здесь |
| `data/glossary.json` | Сборка из `data/cards/` и версия формата (производный, вручную не правится) |
| `data/glossary.schema.json` | JSON Schema — автодополнение и проверка в IDE |
| `site/python_glossary.html` | Собранная витрина: поиск, фильтры, тёмная тема, работает офлайн |
| `src/glossary/` | Пакет: валидация, сборка витрины, экспорт, CLI |
| `tests/` | Тесты кода и контракта данных |

## Откуда берутся данные

```
data/cards/*.json ──► glossary assemble ──► data/glossary.json ──► site/python_glossary.html
   (источник)            (сборка)               (производный)          (витрина)
                                                       │
                                                       └──► выгрузка ──► Stepik-Python-Grader
```

У содержания один хозяин, и он здесь: правится `data/cards/`, остальное
собирается. Грейдер правку не вносит, а читает выгрузку — правка карточки в
двух местах разъехалась бы на первой же синхронизации.
<!--предмет:правка содержания глоссария-->

```bash
make assemble        # собрать data/glossary.json из data/cards/
make validate        # проверить качество
make objections      # очередь работы над содержанием
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
glossary build                          # пересобрать site/python_glossary.html
glossary build --check                  # витрина синхронна с данными? (для CI)
glossary export -f markdown -o out.md   # экспорт: html, json, markdown, csv
glossary assemble                       # собрать data/glossary.json из data/cards/
glossary assemble --check               # сборка синхронна с карточками? (для CI)
glossary objections                     # замечания к содержанию — очередь работы
glossary objections --format json       # тот же список контрактом для машины
glossary completeness                   # чего в глоссарии нет вовсе
```

Пакет запускается и как модуль: `python -m glossary …`. Runtime-зависимостей нет —
достаточно интерпретатора Python 3.14+. Замер языка (`glossary inventory`)
запускается из дерева и на младших версиях, от 3.11: так снимается разность версий.

## Как править глоссарий

Карточка правится в `data/cards/<группа>.json`; два других файла производные
и собираются командами — см. «Откуда берутся данные»:

```bash
make assemble    # data/cards/ → data/glossary.json
make validate    # что сломалось?
make build       # пересобрать витрину
git add data/cards data/glossary.json site/python_glossary.html
```

Правка `data/glossary.json` на месте теряется при следующей сборке, правка
`site/python_glossary.html` — тоже; CI сверяет оба файла с их входом и расхождения
не пропускает. Подробности — в [contributing.md](contributing.md),
архитектурные решения — в [architecture.md](architecture.md).
