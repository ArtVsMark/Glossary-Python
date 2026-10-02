#!/bin/bash
# Старт облачного окна: окружение проверки на планке проекта и Python 3.14.
#
# ТОЛЬКО В ОБЛАКЕ. На машине владельца окружение его, и ставить туда
# интерпретатор без спроса хук не вправе: признак облака — CLAUDE_CODE_REMOTE.
#
# ЗАЧЕМ 3.14. Это планка всей семьи (решение владельца 1 октября, #53), а образ
# облачного окна несёт 3.10–3.13, и встроенный uv знает лишь 3.14.0rc2. Сайт
# установщика uv закрыт сетевой политикой, PyPI открыт — поэтому свежий uv
# ставится из PyPI (приём каталога правил, его .claude/hooks/session-start.sh).
#
# ЗАЧЕМ .venv НА ПЛАНКЕ. Прогон перед толчком должен идти на той версии, на
# которой гоняет конвейер, иначе «чисто локально» остаётся на его поверхности.
# Планку читает scripts/python_floor.py, а не второй разбор здесь (правило 214):
# сдвинется планка — хук сам соберёт окружение на новой версии.
#
# СБОЙ СЕТИ НЕ РОНЯЕТ СТАРТ. Всякий отказ — предупреждение с названным шагом и
# выход 0. Окно открывается всегда; не готово только то, что названо. .venv
# попадает в PATH, лишь когда собран целиком.
#
# ПОВТОРНЫЙ ЗАПУСК ДЕШЁВЫЙ. Зависимости ставятся заново, только когда сменился
# pyproject.toml: его отпечаток лежит в .venv рядом с окружением.
set -uo pipefail

warn() {
  echo "старт окна: $1 — окно работает без этого; проверки перед толчком запускайте интерпретатором не ниже планки вручную" >&2
}

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
cd "${CLAUDE_PROJECT_DIR:-}" 2>/dev/null || { warn "нет каталога проекта"; exit 0; }

if ! command -v python3.14 >/dev/null 2>&1; then
  { python3.12 -m venv /opt/uv \
      && /opt/uv/bin/pip install -q -U uv \
      && /opt/uv/bin/uv python install 3.14 \
      && ln -sf "$(/opt/uv/bin/uv python find 3.14)" /usr/local/bin/python3.14; } \
    || warn "Python 3.14 не поставлен"
fi

reader=$(command -v python3.14 || command -v python3)
floor=$("$reader" scripts/python_floor.py) || { warn "планка requires-python не прочитана"; exit 0; }
command -v "python$floor" >/dev/null 2>&1 || { warn "интерпретатора python$floor нет"; exit 0; }

if [ ! -x .venv/bin/python ] \
  || [ "$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')" != "$floor" ]; then
  rm -rf .venv
  "python$floor" -m venv .venv || { warn "окружение на $floor не собрано"; exit 0; }
fi

stamp=.venv/.pyproject.sha256
current=$(sha256sum pyproject.toml | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null)" != "$current" ]; then
  .venv/bin/pip install -q -e ".[dev]" \
    || { warn "зависимости проверки не поставлены"; exit 0; }
  echo "$current" > "$stamp"
fi

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
exit 0
