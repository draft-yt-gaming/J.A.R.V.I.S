#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_URL="https://github.com/draft-yt-gaming/J.A.R.V.I.S.git"
APP_DIR="/opt/jarvis"
APP_USER="jarvis"
SERVICE_NAME="jarvis-vm.service"

info() { printf "${CYAN}[proxmox]${NC} %s\n" "$*"; }
ok() { printf "${GREEN}[ok]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[attention]${NC} %s\n" "$*"; }
fail() { printf "${RED}[erreur]${NC} %s\n" "$*" >&2; exit 1; }

ask() {
  local prompt="$1"
  local default="$2"
  local value
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default] : " value
    printf '%s' "${value:-$default}"
  else
    read -r -p "$prompt : " value
    printf '%s' "$value"
  fi
}

ask_yes_no() {
  local prompt="$1"
  local default="$2"
  local value suffix
  suffix="y/N"
  [ "$default" = "y" ] && suffix="Y/n"
  read -r -p "$prompt [$suffix] : " value
  value="${value:-$default}"
  case "${value,,}" in
    y|yes|o|oui) return 0 ;;
    *) return 1 ;;
  esac
}

ask_password() {
  local first second
  while true; do
    read -r -s -p "Mot de passe root du CT (5 caracteres minimum) : " first
    echo
    if [ "${#first}" -lt 5 ]; then
      warn "Proxmox demande au moins 5 caracteres. Reessaie avec un mot de passe plus long."
      continue
    fi
    read -r -s -p "Confirmer le mot de passe root du CT : " second
    echo
    if [ "$first" != "$second" ]; then
      warn "Les deux mots de passe ne correspondent pas."
      continue
    fi
    printf '%s' "$first"
    return 0
  done
}

next_ctid() {
  local id=120
  while pct status "$id" >/dev/null 2>&1; do
    id=$((id + 1))
  done
  printf '%s' "$id"
}

pick_default_storage() {
  pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $1 != "" {print $1; exit}'
}

pick_default_template_storage() {
  pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 && $1 != "" {print $1; exit}'
}

list_proxmox_bridges() {
  ip -o link show 2>/dev/null | awk -F': ' '$2 ~ /^vmbr[[:alnum:]_.-]+$/ {print $2}' | sort -V
}

ask_bridge() {
  local bridges=() choice i
  mapfile -t bridges < <(list_proxmox_bridges)
  if [ "${#bridges[@]}" -eq 0 ]; then
    warn "Aucun bridge vmbr detecte automatiquement."
    ask 'Bridge reseau Proxmox' 'vmbr0'
    return 0
  fi

  echo "Bridges reseau detectes :" >&2
  for i in "${!bridges[@]}"; do
    printf '  %s = %s\n' "$((i + 1))" "${bridges[$i]}" >&2
  done

  while true; do
    read -r -p "Choix du bridge reseau (numero ou nom) [1] : " choice
    choice="${choice:-1}"
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#bridges[@]}" ]; then
      printf '%s' "${bridges[$((choice - 1))]}"
      return 0
    fi
    for bridge in "${bridges[@]}"; do
      if [ "$choice" = "$bridge" ]; then
        printf '%s' "$choice"
        return 0
      fi
    done
    warn "Choix invalide. Mets un numero de la liste ou le nom exact du bridge."
  done
}

pick_debian_template() {
  pveam update >/dev/null
  pveam available --section system | awk '/debian-12-standard_.*amd64.*\.tar\.(zst|gz)/ {print $2}' | sort -V | tail -1
}

require_root() {
  [ "${EUID:-$(id -u)}" -eq 0 ] || fail "Lance ce script en root sur l'hote Proxmox : bash scripts/proxmox_create_lxc.sh"
  command -v pct >/dev/null 2>&1 || fail "pct introuvable. Ce script doit tourner sur un hote Proxmox VE."
  command -v pveam >/dev/null 2>&1 || fail "pveam introuvable. Ce script doit tourner sur un hote Proxmox VE."
  command -v pvesm >/dev/null 2>&1 || fail "pvesm introuvable. Ce script doit tourner sur un hote Proxmox VE."
}

install_inside_container() {
  local ctid="$1"
  local http_port="$2"
  local https_port="$3"
  local ws_port="$4"
  local repo_url="$5"

  info "Installation de JARVIS dans le CT $ctid..."
  pct exec "$ctid" -- bash -s -- "$APP_DIR" "$APP_USER" "$SERVICE_NAME" "$http_port" "$https_port" "$ws_port" "$repo_url" <<'IN_CONTAINER'
set -euo pipefail
APP_DIR="$1"
APP_USER="$2"
SERVICE_NAME="$3"
HTTP_PORT="$4"
HTTPS_PORT="$5"
WS_PORT="$6"
REPO_URL="$7"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git openssl \
  python3 python3-venv python3-pip python3-dev build-essential pkg-config \
  portaudio19-dev libasound2-dev libffi-dev libssl-dev \
  nodejs npm ffmpeg espeak \
  libgl1 libglib2.0-0 libxcb-xinerama0 lsof

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
fi

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && python3 -m venv venv"
runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && ./venv/bin/pip install --upgrade pip setuptools wheel"
runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && ./venv/bin/pip install -r requirements.txt"

if [ -f "$APP_DIR/frontend/package.json" ]; then
  if [ -f "$APP_DIR/frontend/package-lock.json" ]; then
    runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR/frontend' && npm ci"
  else
    runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR/frontend' && npm install"
  fi
  runuser -u "$APP_USER" -- bash -lc "cd '$APP_DIR/frontend' && npm run build"
fi

if [ ! -f "$APP_DIR/.env" ]; then
  if [ -f "$APP_DIR/.env.example" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  else
    touch "$APP_DIR/.env"
  fi
  SESSION_SECRET="$(openssl rand -hex 32)"
  if grep -q '^JARVIS_SESSION_SECRET=' "$APP_DIR/.env"; then
    sed -i "s|^JARVIS_SESSION_SECRET=.*|JARVIS_SESSION_SECRET=$SESSION_SECRET|" "$APP_DIR/.env"
  else
    printf '\nJARVIS_SESSION_SECRET=%s\n' "$SESSION_SECRET" >> "$APP_DIR/.env"
  fi
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

cat > "/etc/systemd/system/$SERVICE_NAME" <<SERVICE
[Unit]
Description=Jarvis LXC Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=JARVIS_HEADLESS=1
Environment=JARVIS_BIND_HOST=0.0.0.0
Environment=JARVIS_HTTP_PORT=$HTTP_PORT
Environment=JARVIS_HTTPS_PORT=$HTTPS_PORT
Environment=JARVIS_WS_PORT=$WS_PORT
ExecStart=$APP_DIR/start_jarvis_vm.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
IN_CONTAINER
}

main() {
  require_root

  printf "${CYAN}"
  echo "============================================================"
  echo "       Assistant Proxmox - Creation CT J.A.R.V.I.S"
  echo "============================================================"
  printf "${NC}"
  echo "Ce script cree un container Debian LXC, installe JARVIS, build l'interface web"
  echo "et active le service systemd. Les API keys seront a remplir ensuite dans .env"
  echo "ou dans le dashboard JARVIS."
  echo ""

  local default_ctid default_storage default_tmpl_storage template
  default_ctid="$(next_ctid)"
  default_storage="$(pick_default_storage)"
  default_tmpl_storage="$(pick_default_template_storage)"
  [ -n "$default_storage" ] || default_storage="local-lvm"
  [ -n "$default_tmpl_storage" ] || default_tmpl_storage="local"

  CTID="$(ask 'ID du container Proxmox' "$default_ctid")"
  HOSTNAME="$(ask 'Nom du container' 'jarvis')"
  STORAGE="$(ask 'Storage disque CT' "$default_storage")"
  TEMPLATE_STORAGE="$(ask 'Storage des templates Proxmox' "$default_tmpl_storage")"
  DISK_GB="$(ask 'Taille disque en Go (16 Go conseille, plus si Ollama)' '16')"
  CORES="$(ask 'Nombre de CPU cores' '2')"
  MEMORY_MB="$(ask 'RAM en Mo (4096 conseille)' '4096')"
  SWAP_MB="$(ask 'Swap en Mo' '1024')"
  BRIDGE="$(ask_bridge)"
  NET_MODE="$(ask 'IP du CT: dhcp ou statique CIDR (ex: 192.168.1.50/24)' 'dhcp')"
  GATEWAY=""
  if [ "$NET_MODE" != "dhcp" ]; then
    GATEWAY="$(ask 'Passerelle reseau' '')"
    [ -n "$GATEWAY" ] || fail "Une passerelle est requise en IP statique."
  fi
  HTTP_PORT="$(ask 'Port HTTP JARVIS' '8080')"
  HTTPS_PORT="$(ask 'Port HTTPS JARVIS' '8443')"
  WS_PORT="$(ask 'Port WebSocket JARVIS' '8765')"
  PASSWORD="$(ask_password)"

  UNPRIVILEGED=1
  if ask_yes_no 'Creer un CT privilegie ? Non recommande pour JARVIS web' 'n'; then
    UNPRIVILEGED=0
  fi

  template="$(pick_debian_template)"
  [ -n "$template" ] || fail "Aucun template Debian 12 amd64 trouve via pveam. Lance 'pveam update' puis reessaie."

  echo ""
  info "Resume : CT $CTID / $HOSTNAME / ${CORES} CPU / ${MEMORY_MB} Mo RAM / ${DISK_GB} Go / reseau $NET_MODE"
  info "Template : $TEMPLATE_STORAGE:vztmpl/$template"
  if ! ask_yes_no 'Creer et installer ce container maintenant ?' 'y'; then
    warn "Creation annulee."
    exit 0
  fi

  info "Telechargement du template Debian si necessaire..."
  pveam download "$TEMPLATE_STORAGE" "$template"

  NET_CONF="name=eth0,bridge=$BRIDGE,ip=$NET_MODE"
  if [ -n "$GATEWAY" ]; then
    NET_CONF="$NET_CONF,gw=$GATEWAY"
  fi

  info "Creation du CT..."
  if pct status "$CTID" >/dev/null 2>&1; then
    fail "Le CT $CTID existe deja. Choisis un autre ID ou supprime l'ancien CT avant de relancer."
  fi

  if ! pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$template" \
    --hostname "$HOSTNAME" \
    --storage "$STORAGE" \
    --rootfs "$STORAGE:${DISK_GB}" \
    --cores "$CORES" \
    --memory "$MEMORY_MB" \
    --swap "$SWAP_MB" \
    --net0 "$NET_CONF" \
    --password "$PASSWORD" \
    --unprivileged "$UNPRIVILEGED" \
    --features nesting=1,keyctl=1 \
    --onboot 1 \
    --start 1; then
    warn "La creation du CT a echoue."
    if pct status "$CTID" >/dev/null 2>&1; then
      warn "Nettoyage du CT $CTID cree partiellement."
      pct destroy "$CTID" --purge 1 --force 1 >/dev/null 2>&1 || true
    fi
    exit 1
  fi

  info "Attente du reseau dans le CT..."
  sleep 8
  pct exec "$CTID" -- bash -lc 'for i in {1..30}; do ping -c1 -W1 github.com >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1' || fail "Le CT n'a pas acces a Internet. Verifie IP, bridge, DNS et gateway."

  install_inside_container "$CTID" "$HTTP_PORT" "$HTTPS_PORT" "$WS_PORT" "$REPO_URL"

  CT_IP="$(pct exec "$CTID" -- bash -lc "hostname -I | awk '{print \\$1}'" | tr -d '\r')"
  ok "Installation terminee."
  echo ""
  echo "Acces JARVIS :"
  echo "  HTTP  : http://${CT_IP:-IP_DU_CT}:$HTTP_PORT"
  echo "  HTTPS : https://${CT_IP:-IP_DU_CT}:$HTTPS_PORT"
  echo ""
  echo "Prochaines etapes :"
  echo "  1. Ouvre l'interface web JARVIS."
  echo "  2. Configure tes API keys dans le dashboard ou dans $APP_DIR/.env dans le CT."
  echo "  3. Pour mettre a jour plus tard : pct exec $CTID -- bash -lc 'cd $APP_DIR && bash scripts/update_jarvis.sh'"
  echo ""
  warn "Pour Ollama local, prevois plus de RAM/disque ou installe Ollama sur une machine separee."
}

main "$@"
