# 🤖 J.A.R.V.I.S

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-Private-lightgrey?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Assistant-purple?style=for-the-badge)

Assistant IA personnel avec automatisations, intégrations API et
interface locale.

Ce projet est basé sur le projet de TechEnClair :\
https://www.techenclair.fr/pages/jarvis.html\
Il a été repris, amélioré et adapté selon mes besoins.

------------------------------------------------------------------------

## ✨ Aperçu

JARVIS est un assistant IA modulaire capable de gérer des API, contrôler
des services locaux et automatiser des tâches.

------------------------------------------------------------------------

## 🚀 Fonctionnalités

-   🧠 Agent IA principal intelligent\
-   💾 Système de mémoire\
-   🔌 Intégrations API (Gemini, Groq, XAI, etc.)\
-   🏠 Contrôle Home Assistant\
-   💬 Bot Discord intégré\
-   🖥️ Support Proxmox\
-   📱 Interface web + mobile\
-   ⚙️ Automatisation avancée

------------------------------------------------------------------------

## 🖼️ Interface

Ajoute ici tes screenshots : - assets/dashboard.png -
assets/interface.png

------------------------------------------------------------------------

## 📦 Installation

### 1. Cloner le projet

``` bash
git clone https://github.com/draft-yt-gaming/J.A.R.V.I.S.git
cd J.A.R.V.I.S
```

### 2. Installer les dépendances

``` bash
pip install -r requirements.txt
```

### 3. Lancer JARVIS

``` bash
bash start_jarvis.sh
```

------------------------------------------------------------------------

## ⚙️ Configuration

Créer un fichier `.env` :

    GEMINI_API_KEY=VOTRE_CLE
    BLAGUES_API_TOKEN=VOTRE_TOKEN
    YOUTUBE_API_KEY=VOTRE_CLE
    XAI_API_KEY=VOTRE_CLE

    HA_URL=http://homeassistant.local:8123
    HA_TOKEN=VOTRE_TOKEN

    SERPAPI_API_KEY=VOTRE_CLE
    GROQ_API_KEY=VOTRE_CLE

    PROXMOX_URL=https://proxmox.local:8006
    PROXMOX_TOKEN_ID=VOTRE_ID
    PROXMOX_TOKEN_SECRET=VOTRE_SECRET
    PROXMOX_VERIFY_SSL=false

    DISCORD_OWNER_ID=VOTRE_ID
    DISCORD_CLIENT_ID=VOTRE_ID
    DISCORD_CLIENT_SECRET=VOTRE_SECRET
    DISCORD_REDIRECT_URI=http://localhost:8080/auth/discord/callback

    JARVIS_SESSION_SECRET=VOTRE_SECRET

------------------------------------------------------------------------

## 🧱 Architecture

    backend/
    frontend/
    mobile/
    venv/
    jarvis_agent.py
    main2.py
    start_jarvis.sh
    requirements.txt
    .env

------------------------------------------------------------------------

## 🔒 Sécurité

-   Ne jamais publier `.env`
-   Ajouter au `.gitignore` :

```{=html}
<!-- -->
```
    .env
    venv/
    __pycache__/

------------------------------------------------------------------------

## 🧠 Origine du projet

Basé sur : https://www.techenclair.fr/pages/jarvis.html\
Projet repris, amélioré et personnalisé.

------------------------------------------------------------------------

## 👤 Auteur

draft-yt-gaming
