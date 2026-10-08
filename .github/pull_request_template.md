## Что меняется / What changes

<!-- Кратко: суть изменения и зачем оно нужно. -->
<!-- In short: what the change does and why it is needed. -->

## Тип изменения / Type of change

- [ ] Содержимое глоссария / Glossary content (cards in `data/cards/`)
- [ ] Код инструментов / Tooling code (`src/glossary`)
- [ ] Инфраструктура / Infrastructure (CI, configuration, documentation)

## Проверки / Checks

- [ ] `make check` проходит локально / passes locally
- [ ] Для правки данных: выполнены `make assemble` и `make build`, сборка и витрина в коммите / For data edits: `make assemble` and `make build` were run, the assembly and the showcase are committed
- [ ] Для правки данных: `tests/quality_baseline.json` опущен, если замечаний стало меньше / For data edits: `tests/quality_baseline.json` is lowered if objections went down
- [ ] Новое поведение кода покрыто тестами / New code behaviour is covered by tests

## Связанные задачи / Related issues

У изменения ровно три ответа задаче, и четвёртого — слить и промолчать — нет
(правило каталога 173). Оставьте один.
A change has exactly three answers to an issue; a fourth — merge and stay
silent — does not exist (catalogue rule 173). Keep one:

<!-- Closes #123 — площадка закроет задачу сама / the platform closes the issue itself -->
<!-- Часть #123. Остаток: что именно ещё не сделано -->
<!-- Part of #123. Remaining: what exactly is not done yet -->
<!-- Без задачи: причина -->
<!-- No issue: reason -->
