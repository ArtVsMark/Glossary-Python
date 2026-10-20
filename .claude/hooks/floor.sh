# Планка requires-python, прочитанная БЕЗ Python. Подключается через `.`.
#
# ПОЧЕМУ ВТОРОЙ РАЗБОР, ХОТЯ ЕСТЬ scripts/python_floor.py (правило 214).
# Обёртке стража планка нужна, чтобы выбрать интерпретатор, — то есть до того,
# как известно, каким Python её читать. Читать её системным python3 окна
# значило бы снова звать интерпретатор мимо планки (правило 217). Разборы
# совпадают не на слово: tests/test_check_hook_interpreter.py сверяет этот sed с
# python_floor.floor на настоящем pyproject.toml и на подделках. Приём взят у
# каталога правил (.claude/hooks/floor.sh, Glossary-Python#274).
planka_floor() {
  sed -nE 's/^[[:space:]]*requires-python[[:space:]]*=[[:space:]]*"[^"0-9]*([0-9]+)\.([0-9]+).*/\1.\2/p' \
    "${1:-pyproject.toml}" 2>/dev/null | head -n 1
}
