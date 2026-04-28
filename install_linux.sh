#!/bin/bash
# ======================================================
#   J.A.R.V.I.S — Installateur Linux
#   Testé sur : Ubuntu 22.04+, Debian 12+, Linux Mint 21+
# ======================================================
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "======================================================"
echo "        J.A.R.V.I.S — Installation Linux"
echo "======================================================"
echo -e "${NC}"

# ── 1. Vérification des droits ─────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] Recommandé : lancez avec sudo pour installer les dépendances système.${NC}"
    echo "    sudo bash install_linux.sh"
    echo ""
fi

# ── 2. Mise à jour des paquets système ─────────────────
echo -e "${CYAN}[1/7] Mise à jour des paquets système...${NC}"
if command -v apt-get &>/dev/null; then
    sudo apt-get update -q
    sudo apt-get install -y -q \
        python3 python3-pip python3-venv \
        portaudio19-dev python3-pyaudio \
        nodejs \
        libxcb-xinerama0 python3-xlib \
        espeak ffmpeg \
        lsof
    PKG_MGR="apt"
elif command -v dnf &>/dev/null; then
    sudo dnf install -y -q \
        python3 python3-pip \
        portaudio-devel \
        nodejs \
        python3-xlib \
        espeak ffmpeg \
        lsof
    PKG_MGR="dnf"
elif command -v pacman &>/dev/null; then
    sudo pacman -Sy --noconfirm \
        python python-pip \
        portaudio \
        nodejs \
        python-xlib \
        espeak ffmpeg \
        lsof
    PKG_MGR="pacman"
else
    echo -e "${YELLOW}[!] Gestionnaire de paquets non reconnu. Installez manuellement :${NC}"
    echo "    python3, python3-pip, python3-venv, portaudio, nodejs, npm, lsof"
fi
echo -e "${GREEN}[OK] Paquets système installés.${NC}"

# ── 3. Environnement virtuel Python ────────────────────
echo ""
echo -e "${CYAN}[2/7] Création de l'environnement virtuel Python...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}[OK] Environnement virtuel créé.${NC}"
else
    echo -e "${GREEN}[OK] Environnement virtuel déjà présent.${NC}"
fi

VENV_PY="./venv/bin/python"
VENV_PIP="./venv/bin/pip"

# ── 4. Mise à jour pip ─────────────────────────────────
echo ""
echo -e "${CYAN}[3/7] Mise à jour de pip...${NC}"
"$VENV_PIP" install --upgrade pip setuptools wheel -q

# ── 5. Installation des modules Python ─────────────────
echo ""
echo -e "${CYAN}[4/7] Installation des modules Python (quelques minutes)...${NC}"

echo "  → Modules IA (Gemini, OpenAI, Groq)..."
"$VENV_PIP" install -q \
    python-dotenv google-genai google-generativeai \
    groq openai flask flask-cors requests websockets \
    colorama tenacity

echo "  → Modules Audio / Vision..."
"$VENV_PIP" install -q \
    SpeechRecognition edge-tts pyttsx3 \
    pyautogui Pillow screeninfo psutil

echo "  → PyAudio et Pygame..."
"$VENV_PIP" install -q pygame pyaudio

echo "  → Google APIs..."
"$VENV_PIP" install -q \
    google-auth google-auth-oauthlib google-auth-httplib2 \
    google-api-python-client

if [ -f "requirements.txt" ]; then
    echo "  → requirements.txt..."
    "$VENV_PIP" install -q -r requirements.txt
fi

echo -e "${GREEN}[OK] Modules Python installés.${NC}"

# ── 6. Interface Web (npm) ──────────────────────────────
echo ""
echo -e "${CYAN}[5/7] Installation de l'interface Web (npm)...${NC}"
if command -v npm &>/dev/null; then
    if [ -f "frontend/package.json" ]; then
        cd frontend && npm install -q && cd ..
        USER_NAME=${SUDO_USER:-$USER}
        chown -R "$USER_NAME":"$(id -gn "$USER_NAME")" frontend/node_modules
        echo -e "${GREEN}[OK] Interface Web installée.${NC}"
    fi
else
    echo -e "${YELLOW}[!] npm non trouvé. Interface Web ignorée.${NC}"
fi

# ── 7. Personnalisation du prénom ───────────────────────
echo ""
echo -e "${CYAN}[6/7] Personnalisation...${NC}"
echo -e "Par défaut, JARVIS s'adresse à '${YELLOW}Mickael${NC}'."
read -p "Votre prénom (Entrée pour garder Mickael) : " PRENOM

if [ -n "$PRENOM" ] && [ "$PRENOM" != "Mickael" ] && [ "$PRENOM" != "mickael" ]; then
    PRENOM_LOWER=$(echo "$PRENOM" | tr '[:upper:]' '[:lower:]')
    sed -i "s/Mickael/$PRENOM/g; s/mickael/$PRENOM_LOWER/g" main2.py
    [ -f jarvis_agent.py ] && sed -i "s/Mickael/$PRENOM/g; s/mickael/$PRENOM_LOWER/g" jarvis_agent.py
    echo -e "${GREEN}[OK] JARVIS personnalisé pour ${PRENOM}.${NC}"
fi

# ── 8. Lanceur ──────────────────────────────────────────
echo ""




# ── 7. Création du lanceur ──────────────────────────────
echo "[7/7] Création du lanceur..."

USER_NAME=${SUDO_USER:-$USER}
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)

mkdir -p "$USER_HOME/.local/share/applications"

cat > "$USER_HOME/.local/share/applications/jarvis.desktop" <<EOL
[Desktop Entry]
Name=JARVIS
Exec=$PWD/start_jarvis.sh
Icon=utilities-terminal
Type=Application
Categories=Utility;
EOL

chown "$USER_NAME":"$(id -gn "$USER_NAME")" "$USER_HOME/.local/share/applications/jarvis.desktop"

echo "[OK] Lanceur créé."
