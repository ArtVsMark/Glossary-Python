# Точки входа для разработки. Каждая цель повторяет то, что делает CI,
# поэтому локальный `make check` даёт тот же результат, что и пайплайн.

PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help venv install lint format typecheck test cov validate objections completeness import import-check rules facts facts-check changelog-check changelog-preview changelog-collect build build-check export check clean

help: ## Показать список целей
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Создать виртуальное окружение
	$(PYTHON) -m venv $(VENV)

install: ## Установить пакет в режиме разработки со всеми dev-зависимостями
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev,schema]"
	$(BIN)/python -m pip install pre-commit
	$(BIN)/pre-commit install

lint: ## Проверить стиль и найти дефекты (ruff)
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Отформатировать код и починить автоисправимое
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck: ## Проверить типы (mypy strict)
	$(BIN)/mypy

test: ## Прогнать тесты
	$(BIN)/pytest

cov: ## Прогнать тесты с отчётом о покрытии
	$(BIN)/pytest --cov=glossary --cov-report=term-missing --cov-report=xml

validate: ## Проверить качество данных глоссария
	$(BIN)/python -m glossary validate

objections: ## Собрать замечания к содержанию для отправки в источник
	$(BIN)/python -m glossary objections

completeness: ## Показать, чего в глоссарии нет вовсе (эталон — сам Python)
	$(BIN)/python -m glossary completeness

import: ## Перечитать карточки из клона Stepik-Python-Grader (SOURCE=путь)
	$(BIN)/python scripts/import_from_grader.py --source $(SOURCE)

import-check: ## Сверить снимок с источником, ничего не записывая (SOURCE=путь)
	$(BIN)/python scripts/import_from_grader.py --source $(SOURCE) --check

rules: ## Проверить ответ проекта каталогу правил
	$(BIN)/pytest tests/test_rules_bindings.py -q

changelog-check: ## Проверить форму записей журнала
	$(BIN)/python scripts/changelog.py --check

changelog-preview: ## Показать, как соберётся журнал
	$(BIN)/python scripts/changelog.py --preview

changelog-collect: ## Перенести фрагменты в [Unreleased]
	$(BIN)/python scripts/changelog.py --collect

facts: ## Переписать числа в README из источников
	$(BIN)/python scripts/facts.py --render --check

build: ## Пересобрать HTML-витрину из данных
	$(BIN)/python -m glossary build

build-check: ## Убедиться, что витрина синхронна с данными
	$(BIN)/python -m glossary build --check

export: ## Выгрузить глоссарий во все поддерживаемые форматы
	@mkdir -p dist-export
	$(BIN)/python -m glossary export -f json     -o dist-export/glossary.json
	$(BIN)/python -m glossary export -f markdown -o dist-export/glossary.md
	$(BIN)/python -m glossary export -f csv      -o dist-export/glossary.csv

check: lint typecheck test validate rules facts-check changelog-check build-check ## Полный набор проверок (как в CI)

facts-check: ## Проверить, что числа в README не разъехались
	$(BIN)/python scripts/facts.py --check

clean: ## Удалить артефакты сборки и кэши
	rm -rf build dist dist-export *.egg-info src/*.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
