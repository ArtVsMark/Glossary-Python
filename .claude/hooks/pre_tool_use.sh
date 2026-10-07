#!/bin/sh
# Сторож окна перед командой оболочки: правила каталога 012 и 013
# (scripts/window_guard.py). Python — из .venv, если он уже собран хуком старта,
# иначе системный: сторож держит грамматику младшей версии.
dir="${CLAUDE_PROJECT_DIR:-.}"
py="$dir/.venv/bin/python"
[ -x "$py" ] || py=python3
exec "$py" "$dir/scripts/window_guard.py"
