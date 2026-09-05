#!/usr/bin/env bash
# Reels Agent — installer for Claude Code, Codex and Antigravity.
#   ./install.sh                      auto-detect the platform
#   ./install.sh --platform codex     install for a specific one
#   ./install.sh --platform all       install for all three
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM=""
[[ "${1:-}" == "--platform" ]] && PLATFORM="${2:-}"

say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }

detect() {
  [[ -d "$HOME/.claude"  || -n "${CLAUDE_CODE:-}"  ]] && { echo claude;      return; }
  [[ -d "$HOME/.codex"   || -n "${CODEX_HOME:-}"   ]] && { echo codex;       return; }
  [[ -d "$HOME/.gemini"  || -d "$HOME/.agent"      ]] && { echo antigravity; return; }
  echo ""
}

install_to() {
  local platform="$1" dest root
  case "$platform" in
    claude)      root="$HOME/.claude";  dest="$root/skills/matvieiev-agent_reels-editor" ;;
    codex)       root="$HOME/.codex";   dest="$root/../.agents/skills/matvieiev-agent_reels-editor" ;;
    antigravity) root="$HOME/.agent";   dest="$root/skills/matvieiev-agent_reels-editor" ;;
    *) say "unknown platform: $platform"; exit 1 ;;
  esac

  mkdir -p "$dest"
  ( cd "$SRC/skills/matvieiev-agent_reels-editor" && \
    find . -type d -name __pycache__ -prune -o -type f -print0 \
    | tar --null -cf - -T - ) | ( cd "$dest" && tar -xf - )
  mkdir -p "$dest/../../profiles" 2>/dev/null || true
  cp -n "$SRC/profiles/example.json" "$dest/profiles-example.json" 2>/dev/null || true
  ok "$platform → $dest"
}

say ""
say "Reels Agent — монтаж вертикальних рілсів"
say "зібрав Віталій Матвєєв · instagram.com/matvieiev.vitaliy"
say ""

if [[ "$PLATFORM" == "all" ]]; then
  for p in claude codex antigravity; do install_to "$p"; done
else
  [[ -z "$PLATFORM" ]] && PLATFORM="$(detect)"
  if [[ -z "$PLATFORM" ]]; then
    say "Не вдалось визначити платформу автоматично."
    say "Вкажи явно:  ./install.sh --platform claude|codex|antigravity|all"
    exit 1
  fi
  install_to "$PLATFORM"
fi

say ""
say "Перевіряю залежності..."
MISSING=0
command -v ffmpeg  >/dev/null || { warn "ffmpeg не знайдено — brew install ffmpeg"; MISSING=1; }
command -v python3 >/dev/null || { warn "python3 не знайдено"; MISSING=1; }
if command -v python3 >/dev/null; then
  python3 -c "import faster_whisper" 2>/dev/null \
    || { warn "faster-whisper не встановлено — pip install faster-whisper"; MISSING=1; }
  python3 -c "import PIL" 2>/dev/null \
    || { warn "Pillow не встановлено — pip install Pillow"; MISSING=1; }
fi
[[ $MISSING -eq 0 ]] && ok "всі залежності на місці"

say ""
say "Готово. Відкрий свого агента в папці з відео і скажи:"
say '   "змонтуй цей рілс"'
say ""
[[ $MISSING -eq 1 ]] && say "Спершу постав те, що вище — інакше перший запуск зупиниться."
say ""
