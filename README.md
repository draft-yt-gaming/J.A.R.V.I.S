# J.A.R.V.I.S

Assistant IA personnel en Python, orienté usage domestique et auto-hebergé.

Ce fork reprend l'idee du projet presente par TechEnClair puis l'etend avec une interface web moderne, des integrations personnelles et un mode VM/headless plus adapte a un usage quotidien.

Projet source d'origine :
https://www.techenclair.fr/pages/jarvis.html

## Apercu

J.A.R.V.I.S tourne comme un service local et peut etre pilote depuis :
- l'interface web
- le micro du navigateur
- des commandes texte
- un acces distant via tunnel HTTP

Le backend gere les appels IA, la memoire, les integrations externes et les actions locales. Le frontend fournit l'orb, le micro, le mini-player, la vision navigateur et le dashboard d'administration.

## Fonctionnalites principales

- Assistant conversationnel avec fallback multi-modeles Gemini
- Gestion de plusieurs cles Gemini dans un seul champ de configuration
- Fallback HTTP pour l'interface web quand le WebSocket n'est pas joignable derriere un tunnel
- Memoire persistante separee par utilisateur/client
- Dashboard web avec etat des services et edition des reglages
- Protection du dashboard par OAuth Discord
- Controle Home Assistant
- Support Proxmox
- Integrations Emby, YouTube, Blagues API, SerpAPI, Groq, xAI selon configuration
- Vision navigateur et capture d'ecran
- Vision camera locale via OpenCV
- Mini-player YouTube integre dans l'interface
- Service systemd dedie au mode VM/headless

## Architecture du projet

- `main2.py` : backend principal, logique IA, API web, WebSocket, integrations
- `frontend/` : interface web Vite/TypeScript
- `mobile/` : ancienne interface mobile / ressources annexes
- `start_jarvis.sh` : lancement local classique
- `start_jarvis_vm.sh` : lancement VM/headless
- `jarvis_agent.py` : agent auxiliaire
- `generated_images/` : images generees
- `jarvis_memoire.json` : memoire persistante runtime
- `jarvis_runtime_settings.json` : reglages sauvegardes par le dashboard

## Prerequis

- Debian/Linux recommande
- Python 3.11 recommande
- Node.js + npm pour builder le frontend
- Un environnement virtuel Python dans `venv/`

Paquets systeme souvent utiles sur Debian :

```bash
apt-get update
apt-get install -y python3-venv python3-pip python3-dev build-essential pkg-config \
  portaudio19-dev libasound2-dev libffi-dev libssl-dev nodejs npm
```

## Installation

### 1. Cloner le projet

```bash
git clone git@github.com:draft-yt-gaming/J.A.R.V.I.S.git
cd J.A.R.V.I.S
```

### 2. Installer les dependances Python

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Installer les dependances frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Configurer l'environnement

Creer un fichier `.env` a la racine. Exemple minimal :

```env
GEMINI_API_KEY=VOTRE_CLE_OU_PLUSIEURS_CLES_SEPAREES_PAR_VIRGULE
YOUTUBE_API_KEY=VOTRE_CLE
XAI_API_KEY=VOTRE_CLE
GROQ_API_KEY=VOTRE_CLE
SERPAPI_API_KEY=VOTRE_CLE

HA_URL=http://homeassistant.local:8123
HA_TOKEN=VOTRE_TOKEN

PROXMOX_URL=https://proxmox.local:8006
PROXMOX_TOKEN_ID=VOTRE_ID
PROXMOX_TOKEN_SECRET=VOTRE_SECRET
PROXMOX_VERIFY_SSL=false

DISCORD_OWNER_ID=VOTRE_ID_DISCORD
DISCORD_CLIENT_ID=VOTRE_CLIENT_ID
DISCORD_CLIENT_SECRET=VOTRE_CLIENT_SECRET
DISCORD_REDIRECT_URI=http://IP_OU_DOMAINE:8080/auth/discord/callback

JARVIS_SESSION_SECRET=UN_SECRET_LONG_ET_ALEATOIRE
```

Notes :
- `GEMINI_API_KEY` accepte une ou plusieurs cles separees par virgule, point-virgule ou retour ligne.
- Les reglages peuvent ensuite etre modifies depuis le dashboard et sont enregistres dans `jarvis_runtime_settings.json`.
- En mode public, pense a adapter `DISCORD_REDIRECT_URI` a ton domaine reel.

## Lancement

### Mode local classique

```bash
bash start_jarvis.sh
```

### Mode VM / headless

```bash
bash start_jarvis_vm.sh
```

Par defaut en mode VM :
- HTTP : `http://0.0.0.0:8080`
- WebSocket : `ws://0.0.0.0:8765`

Variables d'environnement utiles :
- `JARVIS_HEADLESS=1`
- `JARVIS_BIND_HOST=0.0.0.0`
- `JARVIS_HTTP_PORT=8080`
- `JARVIS_WS_PORT=8765`

## Service systemd

Exemple utilise sur la VM Debian :

```ini
[Unit]
Description=Jarvis VM Web Service
After=network.target

[Service]
Type=simple
User=draft
WorkingDirectory=/home/draft/jarvis-vm
Environment=JARVIS_HEADLESS=1
Environment=JARVIS_BIND_HOST=0.0.0.0
Environment=JARVIS_WS_PORT=8765
Environment=JARVIS_HTTP_PORT=8080
ExecStart=/home/draft/jarvis-vm/start_jarvis_vm.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Commandes utiles :

```bash
systemctl restart jarvis-vm.service
systemctl status jarvis-vm.service
journalctl -u jarvis-vm.service -n 100 --no-pager
```

## Acces distant et Cloudflare Tunnel

Le projet peut etre publie via un tunnel HTTP vers le port `8080`.

Important :
- l'interface tente d'abord le WebSocket sur `:8765`
- si le WebSocket n'est pas accessible derriere le tunnel, le frontend bascule automatiquement sur un fallback HTTP (`/api/command` et `/api/client/events`)

Cela permet a l'interface de continuer a recevoir les reponses meme quand seul le port HTTP est expose publiquement.

## Dashboard et securite

Le dashboard peut fonctionner en mode libre, mais le mode recommande est la protection via OAuth Discord.

Fonctions protegees/proprietaire :
- modification des reglages du dashboard
- acces au debug web
- certaines commandes sensibles (Home Assistant, Proxmox, Emby)

## Memoire persistante

La memoire n'est plus globale.

Elle est separee par scope utilisateur :
- `discord:<id>` pour le proprietaire authentifie
- `client:<id>` pour les visiteurs web non authentifies

Le fichier runtime `jarvis_memoire.json` stocke donc plusieurs blocs utilisateurs.

## Frontend

Depuis `frontend/` :

```bash
npm install
npm run dev
npm run build
```

Le build genere `frontend/dist/`, servi ensuite par Flask en mode VM/headless.

## Fichiers runtime a ne pas versionner

Ces fichiers ne devraient pas contenir d'informations sensibles dans le depot :
- `.env`
- `venv/`
- `frontend/node_modules/`
- `__pycache__/`
- `*.pyc`
- `jarvis_memoire.json`
- `jarvis_runtime_settings.json`
- `frontend/.vite/`
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- fichiers audio/image temporaires Jarvis
- images generees dans `generated_images/`

## Limitations / remarques

- La vision ecran/camera depend fortement de Gemini quand elle est active.
- Si Ollama n'est pas lance localement, le fallback LLM local echouera.
- Certains comportements restent personnalises pour l'environnement de l'auteur.
- Le repo peut contenir a la fois le code source frontend et les assets buildes de `frontend/dist/`.

## Auteur

draft-yt-gaming
