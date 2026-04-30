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
- APIs publiques gratuites separees de l IA : Open-Meteo, Open Food Facts, Nager.Date, Wikipedia, OpenStreetMap, Open Library et NASA APOD
- Vision navigateur et capture d'ecran
- Vision camera locale via OpenCV
- Mini-player YouTube integre dans l'interface
- Recherche musicale via YouTube Data API si `YOUTUBE_API_KEY` est configuree, avec fallback automatique sur la recherche actuelle
- Service systemd dedie au mode VM/headless
- Compatibilite web app Apple/iOS/iPadOS avec manifest, icones, HTTPS local et interfaces mobile/tablette adaptees

## Architecture du projet

- `main2.py` : backend principal, logique IA, API web, WebSocket, integrations
- `frontend/` : interface web Vite/TypeScript
- `mobile/` : ancienne interface mobile / ressources annexes
- `start_jarvis.sh` : lancement local classique
- `start_jarvis_vm.sh` : lancement VM/headless
- `.env.example` : modele versionne des variables de configuration
- `scripts/update_jarvis.sh` : mise a jour depuis GitHub sans ecraser les reglages locaux
- `scripts/proxmox_create_lxc.sh` : assistant de creation d'un CT/LXC JARVIS sur Proxmox
- `scripts/check_env_updates.py` : detection des nouvelles cles de configuration apres mise a jour
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


## Performances recommandees

Les besoins changent beaucoup selon les modules actives. Les API cloud comme Gemini, Groq, xAI, YouTube, SerpAPI, Open-Meteo ou NASA font surtout travailler Internet et consomment peu de CPU local. Les modules locaux comme le micro, le TTS, la vision et surtout Ollama demandent plus de ressources.

| Usage | CPU conseille | RAM conseillee | Stockage | Notes |
| --- | --- | --- | --- | --- |
| Installation minimale, commandes texte, APIs cloud | 2 coeurs | 2 Go | 4 Go libres | Suffisant pour une VM legere si le frontend est deja build. |
| VM web quotidienne avec dashboard, micro navigateur, TTS Edge et mini-player | 2 a 4 coeurs | 4 Go | 8 Go libres | Profil recommande pour l'usage standard auto-heberge. |
| Vision navigateur / capture ecran / camera locale | 4 coeurs | 4 a 8 Go | 10 Go libres | Plus confortable si plusieurs captures ou traitements image sont utilises. |
| Ollama local petits modeles 3B/4B quantifies | 4 coeurs | 8 Go | 15 a 30 Go libres | Possible sans GPU, mais les reponses peuvent etre lentes. |
| Ollama local modeles 7B/8B quantifies | 6 a 8 coeurs | 16 Go | 30 a 60 Go libres | GPU NVIDIA/Apple Silicon conseille pour une experience fluide. |
| Ollama local gros modeles 13B+ | 8 coeurs+ | 32 Go+ | 60 Go+ | A reserver a une machine dediee ou une carte graphique adaptee. |

Notes par integration :
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `XAI_API_KEY`, `YOUTUBE_API_KEY`, `SERPAPI_API_KEY`, `NASA_API_KEY` : tres peu de charge locale, surtout besoin d'une connexion stable.
- `HA_URL` / `HA_TOKEN`, Proxmox et Emby : charge locale faible, mais le reseau local doit etre fiable.
- Extension Chrome : charge faible cote serveur, sauf si beaucoup d'utilisateurs generent des resumes/TTS en meme temps.
- TTS Edge : consomme peu localement mais depend du service distant et genere des fichiers audio temporaires.
- WebApp iPhone/iPad : le micro doit etre ouvert en HTTPS ; la charge principale reste cote serveur Jarvis.
- Ollama : c'est le seul module qui peut vraiment changer la taille de la machine necessaire. Choisir le modele selon la RAM disponible.


### Mesures observees sur la VM de test

Mesures realisees sur la VM Debian du projet : 2 vCPU KVM/QEMU, 3.8 Go de RAM, disque 19 Go. Elles donnent un ordre d'idee, pas une garantie de performance universelle.

| Mesure | Resultat observe |
| --- | --- |
| Jarvis au repos, memoire systemd | environ 137 Mo |
| Process Python au repos, RSS | environ 186 a 190 Mo |
| RAM disponible sur la VM apres demarrage | environ 3.3 Go disponibles |
| Taille du projet complet | environ 913 Mo |
| `venv/` Python | environ 616 Mo |
| `frontend/node_modules/` | environ 79 Mo |
| `frontend/dist/` servi par Flask | environ 676 Ko |

Benchmark local sans appel IA externe, depuis `127.0.0.1` :

| Scenario | Resultat observe | Note |
| --- | --- | --- |
| 60 requetes sur `/` | environ 827 req/s, latence moyenne 1.2 ms | Page web deja build. |
| 60 requetes sur `/manifest.webmanifest` | environ 882 req/s, latence moyenne 1.1 ms | Fichier statique tres leger. |
| 250 requetes concurrentes sur `/api/auth/status` avec 10 workers | environ 988 req/s, latence moyenne 9.8 ms | Cache services chaud. |
| Premiere verification `/api/auth/status` apres cache froid | pic possible autour de 2 s | Peut tester les services configures, donc ce n'est pas la latence normale. |

Ces tests ne mesurent pas les temps de reponse Gemini/Groq/xAI/SerpAPI/YouTube, car ils dependent surtout des APIs externes et du reseau. Pour Ollama, la charge depend presque entierement du modele local choisi.

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/draft-yt-gaming/J.A.R.V.I.S.git
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

Creer un fichier `.env` a la racine. Le fichier `.env.example` contient la liste versionnee des variables possibles et reste mis a jour par Git.

```bash
cp .env.example .env
```

Exemple minimal :

```env
GEMINI_API_KEY=VOTRE_CLE_OU_PLUSIEURS_CLES_SEPAREES_PAR_VIRGULE
# Optionnelle : si absente ou invalide, Jarvis garde la recherche YouTube actuelle.
YOUTUBE_API_KEY=VOTRE_CLE
XAI_API_KEY=VOTRE_CLE
GROQ_API_KEY=VOTRE_CLE
SERPAPI_API_KEY=VOTRE_CLE
NASA_API_KEY=VOTRE_CLE  # optionnelle, DEMO_KEY sinon

# Optionnel : modeles IA locaux via Ollama
OLLAMA_ENABLED=false
OLLAMA_PREFER_LOCAL=false
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODELS=llama3.1:8b,llama3:8b,mistral:instruct

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
EXTENSION_ACCESS_TOKEN=UN_TOKEN_POUR_EXTENSION_PUBLIQUE
```

Notes :
- `GEMINI_API_KEY` accepte une ou plusieurs cles separees par virgule, point-virgule ou retour ligne.
- Les reglages peuvent ensuite etre modifies depuis le dashboard et sont enregistres dans `jarvis_runtime_settings.json`.
- En mode public, pense a adapter `DISCORD_REDIRECT_URI` a ton domaine reel.


## Mise a jour

Les cles API et les reglages locaux ne sont pas versionnes dans Git : `.env`, `jarvis_runtime_settings.json` et `jarvis_memoire.json` restent sur la machine. Pour recuperer la derniere version sans les remettre a la main :

```bash
bash scripts/update_jarvis.sh
```

Le script :
- fonctionne avec un clone HTTPS public, sans cle SSH GitHub ;
- sauvegarde `.env`, `jarvis_runtime_settings.json` et `jarvis_memoire.json` dans `.jarvis_backups/` ;
- compare `.env.example` avec `.env` et les reglages du dashboard pour signaler les nouvelles cles a ajouter ;
- recupere la derniere version de la branche `main` sur GitHub ;
- refuse de continuer si des fichiers suivis ont ete modifies localement, sauf avec `--force` ;
- met a jour `requirements.txt` et/ou le frontend seulement si les fichiers concernes ont change ;
- redemarre `jarvis-vm.service` quand le service existe.

Options utiles :

```bash
bash scripts/update_jarvis.sh --no-restart
bash scripts/update_jarvis.sh --branch main
```

Quand une nouvelle integration ajoute une variable, par exemple `GITHUB_API_KEY`, elle est ajoutee dans `.env.example`. Au prochain `bash scripts/update_jarvis.sh`, Jarvis affiche les nouvelles cles absentes de l'installation locale sans modifier le `.env`.

Aucune API hebergee en plus n'est necessaire pour ce fonctionnement : GitHub sert de canal de mise a jour. Une API publique ne devient utile que si tu veux plus tard afficher une annonce de version dans l'interface ou gerer des canaux `stable` / `beta`.

## Ollama local

Jarvis peut utiliser des modeles locaux exposes par Ollama. Cette integration est separee des fournisseurs cloud :
- `OLLAMA_ENABLED=true` active l'integration ;
- `OLLAMA_URL` pointe vers le serveur Ollama, par defaut `http://127.0.0.1:11434` ;
- `OLLAMA_MODELS` contient une liste de modeles separee par virgule, point-virgule ou retour ligne ;
- `OLLAMA_PREFER_LOCAL=true` force Jarvis a essayer Ollama avant Gemini/Groq pour les reponses IA generales ;
- si `OLLAMA_PREFER_LOCAL=false`, Ollama sert de fallback offline quand les fournisseurs cloud echouent.

Exemple d'installation locale :

```bash
ollama pull llama3.1:8b
ollama serve
```

Puis configure `OLLAMA_ENABLED=true` et `OLLAMA_MODELS=llama3.1:8b` dans le dashboard ou dans `.env`.


## Installation Proxmox CT/LXC

JARVIS peut tourner dans un container LXC Proxmox pour l'usage web/headless. C'est plus leger qu'une VM, tant que l'on ne depend pas d'un bureau Linux local, d'un micro USB branche au serveur ou d'un passthrough GPU complexe.

Un assistant interactif est fourni pour etre lance **sur l'hote Proxmox**, en root, avec une seule commande :

```bash
bash -c "$(curl -fsSL https://jarvis.drafthome.fr/install/proxmox-lxc.sh)"
```

Variante plus prudente si tu veux lire le script avant execution :

```bash
curl -fsSL https://jarvis.drafthome.fr/install/proxmox-lxc.sh -o /tmp/jarvis-proxmox-lxc.sh
less /tmp/jarvis-proxmox-lxc.sh
bash /tmp/jarvis-proxmox-lxc.sh
```


Le fichier est servi directement par JARVIS via `/install/proxmox-lxc.sh`, ce qui evite de dependre d'un acces raw GitHub public.

Si le depot est deja clone sur l'hote Proxmox, tu peux aussi lancer :

```bash
bash scripts/proxmox_create_lxc.sh
```

Le script pose les questions dans le terminal : ID du CT, nom, storage, disque, CPU, RAM, bridge reseau, IP DHCP/statique, ports JARVIS et mot de passe root du CT. Il cree ensuite un CT Debian, installe les dependances, clone le depot en HTTPS, build le frontend, cree un `.env` depuis `.env.example`, genere `JARVIS_SESSION_SECRET`, installe le service `jarvis-vm.service` et le demarre.

Valeurs conseillees pour un CT standard :
- 2 CPU cores ;
- 4096 Mo RAM ;
- 1024 Mo swap ;
- 16 Go disque ;
- CT non privilegie ;
- features Proxmox `nesting=1,keyctl=1`.

Apres installation, les API keys restent a configurer dans le dashboard JARVIS ou dans `/opt/jarvis/.env` a l'interieur du CT.

Commande de mise a jour depuis l'hote Proxmox :

```bash
pct exec ID_DU_CT -- bash -lc 'cd /opt/jarvis && bash scripts/update_jarvis.sh'
```

Limites a connaitre :
- le micro iPhone/iPad/WebApp fonctionne, car il vient du navigateur et non du CT ;
- une camera ou un micro USB branches au serveur demandent une configuration LXC speciale ;
- Ollama peut tourner en CT pour CPU, mais les gros modeles et le GPU passthrough sont souvent plus simples en VM ou sur l'hote ;
- pour exposer JARVIS sur Internet, garder HTTPS/tunnel/reverse proxy et proteger le dashboard.

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



## APIs et tokens pris en charge

Jarvis separe les APIs specialisees des fournisseurs IA. Les APIs publiques ci-dessous sont interrogees avant Gemini/Groq uniquement quand la demande correspond clairement a leur domaine, afin d'eviter les melanges.

| Service / API | Usage dans Jarvis | Token requis | Variable / configuration |
| --- | --- | --- | --- |
| Gemini | Reponses IA principales, raisonnement, vision selon configuration | Oui | `GEMINI_API_KEY` |
| Groq | Fournisseur IA alternatif / rapide | Oui | `GROQ_API_KEY` |
| xAI / Grok | Fournisseur IA alternatif et verifications | Oui | `XAI_API_KEY` |
| Ollama | Modeles IA locaux, fallback offline ou priorite locale | Non | `OLLAMA_ENABLED`, `OLLAMA_URL`, `OLLAMA_MODELS`, `OLLAMA_PREFER_LOCAL` |
| YouTube Data API | Recherche musicale officielle pour le mini-player | Optionnel | `YOUTUBE_API_KEY` ; fallback scraping si absent ou invalide |
| SerpAPI | Recherche web visuelle avec liens/images | Oui | `SERPAPI_API_KEY` |
| Extension Chrome publique | Resume de page et voix Jarvis hors reseau local | Optionnel | `EXTENSION_ACCESS_TOKEN` ; requis seulement si l'extension passe par un domaine public sans session proprietaire |
| NASA APOD | Image astronomique du jour | Optionnel | `NASA_API_KEY` ; `DEMO_KEY` sinon |
| Open-Meteo | Meteo, temperature, pluie, vent | Non | Aucune cle |
| Open Food Facts | Produit, code-barres, Nutri-Score, allergenes | Non | Aucune cle |
| Nager.Date | Jours feries par pays | Non | Aucune cle |
| Wikipedia / Wikimedia | Resume encyclopedique | Non | Aucune cle |
| OpenStreetMap / Nominatim | Adresse et coordonnees | Non | Aucune cle, User-Agent obligatoire et usage leger |
| Open Library | Livres, auteurs, ISBN | Non | Aucune cle |
| Home Assistant | Controle domotique local | Oui | `HA_URL`, `HA_TOKEN` |
| Proxmox | Gestion VM/LXC, statut, actions | Oui | `PROXMOX_URL`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET` |
| Emby | Bibliotheque media personnelle | Oui | `EMBY_URL`, `EMBY_API_KEY`, puis `EMBY_USER_ID` ou `EMBY_USERNAME` |
| Discord OAuth | Protection du dashboard administrateur | Oui | `DISCORD_OWNER_ID`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI` |
| Blagues API | Blagues externes si configure | Oui | `BLAGUES_API_TOKEN` |

Exemples APIs publiques : `meteo demain a Paris`, `jours feries en France`, `wikipedia Nikola Tesla`, `nutriscore coca cola`, `isbn 9782070368228`, `image nasa du jour`, `coordonnees de la tour eiffel`.

## Web app mobile Apple/iOS/iPadOS

L'interface web peut etre ajoutee a l'ecran d'accueil d'un iPhone ou d'un iPad depuis Safari avec `Partager` puis `Sur l'ecran d'accueil`.

La version mobile inclut :
- manifest PWA et icones Apple/Android ;
- affichage plein ecran `standalone` ;
- prise en charge des safe areas iPhone et iPad ;
- layout tablette iPad avec boutons tactiles plus grands, dashboard adapte et panneaux lateraux redimensionnes ;
- boutons tactiles, panneau micro et dashboard adaptes aux petits ecrans ;
- panneaux web et YouTube ajustes en feuilles mobiles ;
- separation des clients web pour eviter qu'une reponse lancee sur le PC s'affiche sur le telephone ;
- HTTPS local sur le port `8443`, necessaire pour que Safari iPhone/iPad autorise le micro.

Sur iPhone/iPad, utiliser `https://IP_DE_LA_VM:8443` plutot que `http://IP_DE_LA_VM:8080`. Le certificat local peut demander une validation manuelle la premiere fois.

## Resultats web visuels

Quand Jarvis effectue une recherche web, l'interface affiche un panneau lateral oppose au lecteur musique avec :
- une galerie d'images quand SerpAPI en fournit ;
- des cartes de resultats avec titres, extraits et liens cliquables ;
- un bouton pour masquer le panneau.

Les demandes de type `donne moi une recette de pate` gardent une reponse Jarvis directe et peuvent afficher en complement un panneau visuel avec sources, images et liens cliquables.

## Ecoute vocale

Depuis l'interface web, Jarvis peut recevoir une commande de deux facons :
- cliquer sur le bouton micro pour dicter directement une commande ;
- prononcer le nom configure de l'assistant pour activer le micro, puis dicter la commande comme apres un clic.

Le nom de reveil utilise la valeur `assistant_name` reglable dans le dashboard. Pendant que Jarvis parle, l'ecoute est suspendue puis relancee automatiquement pour eviter que l'assistant se reponde a lui-meme.

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


## Extension Chrome

Une extension Chrome non publiee est fournie dans `chrome-extension/`. Elle permet de lire le texte de l'onglet actif et de demander a Jarvis un resume de la page.

Le dossier `chrome-extension/` reste le code source de l'extension. Pour la distribuer plus simplement, GitHub Actions genere un ZIP telechargeable :
- en artifact quand le workflow `Package Chrome extension` est lance manuellement ;
- en asset de GitHub Release quand un tag `v...` est pousse.

Installation locale depuis le dossier source :

```text
1. Ouvrir chrome://extensions
2. Activer le mode developpeur
3. Cliquer sur Charger l'extension non empaquetee
4. Selectionner le dossier chrome-extension/ du projet
```

Installation depuis un ZIP GitHub Release :

```text
1. Telecharger jarvis-chrome-extension-*.zip dans la release GitHub
2. Dezipper le fichier dans un dossier local
3. Ouvrir chrome://extensions
4. Activer le mode developpeur
5. Cliquer sur Charger l'extension non empaquetee
6. Selectionner le dossier dezippe
```

Pour publier un nouvel asset d'extension :

```bash
git tag v0.1.1
git push origin v0.1.1
```

Le workflow attache alors `jarvis-chrome-extension-<version>.zip` aux assets de la release GitHub.

Par defaut, l'extension appelle `http://192.168.2.102:8080`. L'URL du serveur est modifiable directement dans le popup. Une adresse sans protocole est normalisee automatiquement : `jarvis.drafthome.fr` devient `https://jarvis.drafthome.fr`, tandis que les IP locales restent en HTTP sauf ports HTTPS (`443` ou `8443`).

Si l'extension est utilisee hors reseau local avec un domaine public, renseigner le meme token dans le dashboard (`EXTENSION_ACCESS_TOKEN`) et dans le champ `Token public` de l'extension. Sans token, les endpoints extension restent accessibles depuis le reseau local ou une session proprietaire authentifiee, mais pas ouverts publiquement.

Apres generation du resume, les boutons de lecture permettent d'ecouter, mettre en pause/reprendre ou arreter un MP3 genere par la VM avec la meme voix Edge TTS que Jarvis (`fr-FR-HenriNeural`). Le bouton `Copier selection` copie dans le presse-papiers le texte selectionne dans l'onglet actif.

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
