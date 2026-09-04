# История изменений

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [семантическому версионированию](https://semver.org/lang/ru/).

## [Unreleased]

### Добавлено

- **Источник истины.** Данные глоссария выделены из `python_glossary.html`
  в `data/glossary.json` (581 карточка) с описанием формата в
  `data/glossary.schema.json`. Содержимое карточек при переносе не менялось:
  сборка витрины из нового источника даёт байт в байт тот же HTML.
- **Пакет `glossary`** (`src`-layout, без runtime-зависимостей): модели данных,
  загрузка, валидация, экспортёры и CLI.
- **CLI `glossary`**: `validate`, `build`, `export`, `stats`. Доступен также как
  `python -m glossary`.
- **Проверка качества данных** — реестр из десяти правил с разделением на ошибки
  и предупреждения; пороги вынесены в `ValidationConfig`.
- **Экспорт** в HTML, JSON, Markdown и CSV.
- **Тесты** (106 шт., покрытие 99 %), включая контракт данных: витрина собрана
  из текущего источника, файл записан канонически, данные соответствуют схеме.
- **Храповик качества** `tests/quality_baseline.json` — не даёт числу
  предупреждений расти.
- **Инфраструктура разработки**: `pyproject.toml`, ruff (линтер и форматтер),
  mypy в строгом режиме, pytest с покрытием, pre-commit, `Makefile`,
  `.editorconfig`.
- **CI на GitHub Actions**: линтер и типы, тесты на Python 3.11–3.13, проверка
  качества данных и синхронности витрины, отчёт в сводке запуска.
- **Публикация витрины** на GitHub Pages при изменении `python_glossary.html`.
- **Шаблоны issue и pull request**, `CODEOWNERS`, Dependabot.
- **Документация**: README, `CONTRIBUTING.md`, `docs/architecture.md`,
  `CLAUDE.md`, лицензия MIT.

- **Подключение к каталогу правил**
  [Engineering-Incidents-Playbook](https://github.com/ArtVsMark/Engineering-Incidents-Playbook):
  `.rules/bindings.json` (ответ по 179 правилам), `.rules/proposals.json`
  (канал обратно) и ежедневный прогон `rules-inbox` с закреплённым тегом
  каталога. Набор собран командой каталога, а не перенесён руками.

- **Разбор всех 179 правил каталога.** `unreviewed` не осталось: 58 правил
  держатся гейтом, документом или конвейером, 42 действуют без механизма
  с названной причиной, 79 не имеют здесь предмета. Число правил без
  механизма зафиксировано потолком и двигается только вниз.
- **Гейт на форму ответа** `tests/test_rules_bindings.py`: адрес механизма
  обязан разрешаться в существующий файл репозитория, у каждого `none`
  названа причина, `unreviewed` не допускается. Встроен в `make check`,
  CI и pre-commit.

- **Обязательная проверка `check PR`** — работа-агрегатор в `ci.yml` с одним
  постоянным именем, совпадающим с настройкой защиты ветки. Собрана с
  `if: always()` и явной сверкой вердиктов: без этого работа с `needs:` при
  падении зависимости не краснеет, а пропускается, а пропущенное защита
  засчитывает пройденным — то есть разрешает слияние ровно тогда, когда
  обязана запретить.
- **Сторожа конвейера** `tests/test_workflow_guardrails.py`: имя обязательной
  проверки сверяется с эталоном в дереве, ни одна работа не может уйти из-под
  `needs`, у каждого прогона есть ручной запуск.

### Исправлено

- **Гейт на пустом входе зеленел.** Валидатор на глоссарии без карточек
  сообщал «ошибок 0» и возвращал успех, а сборка молча делала пустую витрину —
  ровно тот случай, который описывает правило каталога 075. Добавлено правило
  `non-empty`, сборка пустой витрины отклоняется.

### Изменено

- README переписан: журнал изменений перенесён в этот файл, вместо него —
  описание проекта, команд и правил работы с данными.
- `.gitattributes`: `python_glossary.html` помечен как генерируемый файл.

## Ранняя история

До появления инструментов изменения фиксировались в README. Ниже — сохранённая
запись о расширении глоссария.

### Расширение до 581 карточки

Итог: 507 → 581 карточка (+74), 37 → 43 раздела.

**Приоритет 1 — выполнено полностью**

- Исключения (+14): `ValueError`, `TypeError`, `KeyError`, `IndexError`,
  `AttributeError`, `NameError`, `ImportError`, `ModuleNotFoundError`,
  `FileNotFoundError`, `PermissionError`, `OSError`, `StopIteration`,
  `NotImplementedError`, `RecursionError`
- Модуль `datetime` (+9): `weekday()`, `isoweekday()`, `replace()`,
  `timestamp()`, `fromtimestamp()`, `utcfromtimestamp()`, `combine()`,
  `timetuple()`, `astimezone()`
- Модуль `threading` (+6): `Thread`, `Lock`, `Event`, `Semaphore`, `RLock`, GIL
- Модуль `concurrent.futures` (+5): `ThreadPoolExecutor`, `ProcessPoolExecutor`,
  `Future`, `submit()`, `as_completed()`
- Модуль `logging` (+10): `basicConfig`, `getLogger`, `info`/`warning`/`error`/`debug`,
  `Formatter`, `Handler`, `StreamHandler`, `FileHandler`
- Модуль `subprocess` (+4): `run()`, `Popen()`, `PIPE`, `check_output()`
- Модуль `unittest` (+5): `TestCase`, `setUp`/`tearDown`,
  `assertEqual`/`assertRaises`, `mock.patch()`, `MagicMock`

**Приоритеты 2 и 3 — выполнено**

- Строки (+6): `isascii`, `isprintable`, `isdecimal`, `isnumeric`,
  `isidentifier`, `format_map`
- Файлы (+5): `tell`, `flush`, `truncate`, `buffering=`, `errors=`
- Модуль `re` (+2): именованные группы, `re.escape`
- Словари (+2): `d1 | d2`, `d1 |= d2`
- Множества (+2): `set.clear`, `set.copy`
- Модуль `os` (+2): `os.getenv`, `os.scandir`
- Модуль `hashlib` (+2): `md5`, `sha256`

**Короткие описания**

Улучшено 107 карточек; описаний короче 60 символов не осталось. Все описания
объясняют не только «что», но и «зачем».

[Unreleased]: https://github.com/ArtVsMark/Glossary-Python/compare/main...HEAD
