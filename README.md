# JARVIS

Assistant IA personnel avec intégrations API, automatisations et
interface locale.

------------------------------------------------------------------------

## Fonctionnalités

-   Agent IA principal
-   Gestion de mémoire
-   Intégrations API (Gemini, Groq, XAI, etc.)
-   Contrôle Home Assistant
-   Intégration Discord
-   Support Proxmox
-   Interface frontend + mobile

------------------------------------------------------------------------

## Installation

### 1. Cloner le projet

``` bash
git clone https://github.com/draft-yt-gaming/J.A.R.V.I.S.git
cd J.A.R.V.I.S
```

### 2. Installer les dépendances

``` bash
pip install -r requirements.txt
```

### 3. Lancer le projet

``` bash
bash start_jarvis.sh
```

------------------------------------------------------------------------

## Configuration (.env)

Créer un fichier `.env` à la racine du projet :

``` env
GEMINI_API_KEY=VOTRE_CLE_ICI
BLAGUES_API_TOKEN=VOTRE_TOKEN_ICI
YOUTUBE_API_KEY=VOTRE_CLE_ICI
XAI_API_KEY=VOTRE_CLE_ICI

HA_URL=http://homeassistant.local:8123
HA_TOKEN=VOTRE_TOKEN_ICI

SERPAPI_API_KEY=VOTRE_CLE_ICI
GROQ_API_KEY=VOTRE_CLE_ICI

PROXMOX_URL=https://proxmox.local:8006
PROXMOX_TOKEN_ID=VOTRE_TOKEN_ID
PROXMOX_TOKEN_SECRET=VOTRE_TOKEN_SECRET
PROXMOX_VERIFY_SSL=false

DISCORD_OWNER_ID=VOTRE_ID_ICI
DISCORD_CLIENT_ID=VOTRE_ID_ICI
DISCORD_CLIENT_SECRET=VOTRE_SECRET_ICI
DISCORD_REDIRECT_URI=http://localhost:8080/auth/discord/callback

JARVIS_SESSION_SECRET=VOTRE_SECRET_ICI
```

------------------------------------------------------------------------

## Structure du projet

    .
    ├── backend/
    ├── frontend/
    ├── mobile/
    ├── venv/
    ├── jarvis_agent.py
    ├── main2.py
    ├── start_jarvis.sh
    ├── requirements.txt
    └── .env (local uniquement)

------------------------------------------------------------------------

## Sécurité

-   Ne jamais push le fichier `.env`
-   Ajouter au `.gitignore` :

```{=html}
<!-- -->
```
    .env
    venv/
    __pycache__/

------------------------------------------------------------------------

## Auteur

draft-yt-gaming
