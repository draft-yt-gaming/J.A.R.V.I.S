#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="main"
RESTART_SERVICE=1
ALLOW_LOCAL_CHANGES=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --no-restart)
      RESTART_SERVICE=0
      shift
      ;;
    --force)
      ALLOW_LOCAL_CHANGES=1
      shift
      ;;
    -h|--help)
      cat <<HELP
Usage: bash scripts/update_jarvis.sh [options]

Options:
  --branch <nom>   Branche Git a suivre, par defaut main.
  --no-restart     Ne redemarre pas jarvis-vm.service apres la mise a jour.
  --force          Continue meme si des fichiers suivis ont ete modifies localement.
HELP
      exit 0
      ;;
    *)
      echo "Option inconnue: $1" >&2
      exit 2
      ;;
  esac
done

info() { printf '\033[0;36m[update]\033[0m %s\n' "$*"; }
ok() { printf '\033[0;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[attention]\033[0m %s\n' "$*"; }
fail() { printf '\033[0;31m[erreur]\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git est requis."
[ -d .git ] || fail "Ce dossier n'est pas un depot Git."

if [ "$ALLOW_LOCAL_CHANGES" -ne 1 ] && ! git diff --quiet --ignore-submodules -- .; then
  fail "Des fichiers suivis ont ete modifies localement. Commit/stash tes changements ou relance avec --force. Les fichiers .env et runtime ignores ne bloquent pas la mise a jour."
fi

OLD_REV="$(git rev-parse HEAD)"
TARGET="origin/${BRANCH}"

info "Sauvegarde des fichiers runtime locaux..."
BACKUP_DIR=".jarvis_backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
for file in .env jarvis_runtime_settings.json jarvis_memoire.json; do
  if [ -f "$file" ]; then
    cp -p "$file" "$BACKUP_DIR/$file"
  fi
done
ok "Sauvegarde creee dans $BACKUP_DIR"

info "Recherche de la derniere version sur GitHub..."
if ! git fetch origin "$BRANCH" --prune; then
  REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
  if printf '%s' "$REMOTE_URL" | grep -q '^git@github.com:'; then
    fail "GitHub refuse la cle SSH pour l'utilisateur actuel. Pour une installation publique, passe le remote en HTTPS : git remote set-url origin https://github.com/draft-yt-gaming/J.A.R.V.I.S.git"
  fi
  fail "Impossible de contacter GitHub depuis ce depot. Verifie la connexion reseau et le remote origin."
fi
NEW_REV="$(git rev-parse "$TARGET")"

if [ "$OLD_REV" = "$NEW_REV" ]; then
  ok "Jarvis est deja a jour ($OLD_REV)."
  exit 0
fi

if git merge-base --is-ancestor "$NEW_REV" "$OLD_REV"; then
  ok "Cette installation contient deja la derniere version disponible sur GitHub."
  exit 0
fi

if ! git merge-base --is-ancestor "$OLD_REV" "$NEW_REV"; then
  fail "La branche locale et GitHub ont diverge. Fais une sauvegarde puis resous le merge manuellement."
fi

CHANGED_FILES="$(git diff --name-only "$OLD_REV" "$NEW_REV")"
REQ_CHANGED=0
FRONTEND_DEPS_CHANGED=0
FRONTEND_BUILD_NEEDED=0
if printf '%s\n' "$CHANGED_FILES" | grep -q '^requirements.txt$'; then
  REQ_CHANGED=1
fi
if printf '%s\n' "$CHANGED_FILES" | grep -Eq '^frontend/(package.json|package-lock.json)$'; then
  FRONTEND_DEPS_CHANGED=1
fi
if printf '%s\n' "$CHANGED_FILES" | grep -Eq '^frontend/(src/|public/|index.html|package.json|package-lock.json)'; then
  FRONTEND_BUILD_NEEDED=1
fi

info "Application de la mise a jour..."
git merge --ff-only "$TARGET"
ok "Code mis a jour: $OLD_REV -> $NEW_REV"

if [ "$REQ_CHANGED" -eq 1 ]; then
  if [ -x venv/bin/pip ]; then
    info "Mise a jour des dependances Python..."
    venv/bin/pip install -r requirements.txt
  else
    warn "venv/bin/pip introuvable, dependances Python non mises a jour."
  fi
fi

if [ "$FRONTEND_DEPS_CHANGED" -eq 1 ]; then
  if command -v npm >/dev/null 2>&1 && [ -f frontend/package.json ]; then
    info "Mise a jour des dependances frontend..."
    (cd frontend && npm install)
  else
    warn "npm introuvable, dependances frontend non mises a jour."
  fi
fi

if [ "$FRONTEND_BUILD_NEEDED" -eq 1 ]; then
  if command -v npm >/dev/null 2>&1 && [ -f frontend/package.json ]; then
    info "Rebuild de l'interface web..."
    (cd frontend && npm run build)
  else
    warn "npm introuvable, frontend non rebuilde."
  fi
fi

if [ "$RESTART_SERVICE" -eq 1 ]; then
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files jarvis-vm.service >/dev/null 2>&1; then
    info "Redemarrage de jarvis-vm.service..."
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
      systemctl restart jarvis-vm.service
    elif sudo -n true >/dev/null 2>&1; then
      sudo systemctl restart jarvis-vm.service
    else
      warn "Droits sudo requis pour redemarrer le service. Lance: sudo systemctl restart jarvis-vm.service"
    fi
  else
    warn "Service jarvis-vm.service introuvable, redemarrage ignore."
  fi
fi

ok "Mise a jour terminee. Les cles API et reglages locaux ont ete conserves."
