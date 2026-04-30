import { createOrb, type OrbState } from "./orb";
import { injectVisionButton, captureFrame } from "./screen_capture";
import "./style.css";

type WebResultItem = {
  title?: string;
  snippet?: string;
  link?: string;
  source?: string;
};

type WebImageItem = {
  src?: string;
  alt?: string;
};

type WsMessage = {
  state?: string;
  action?: string;
  muted?: boolean;
  volume?: number;
  id?: string;
  text?: string;
  audio_b64?: string;
  query?: string;
  video_id?: string;
  items?: WebResultItem[];
  images?: WebImageItem[];
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort?: () => void;
  addEventListener: (type: string, listener: EventListenerOrEventListenerObject) => void;
};

type BrowserSpeechRecognitionCtor = new () => BrowserSpeechRecognition;

type ServiceHealth = {
  state: "ok" | "error" | "missing";
  detail?: string;
};

type AuthStatus = {
  authenticated: boolean;
  user: { id: string; username?: string; global_name?: string } | null;
  assistant_name: string;
  login_url: string;
  logout_url: string;
  discord_configured: boolean;
  config_flags: Record<string, boolean>;
  service_health: Record<string, ServiceHealth>;
  ws_auth_token?: string;
};

type SettingsResponse = {
  settings: Record<string, string | boolean>;
  config_flags: Record<string, boolean>;
  service_health: Record<string, ServiceHealth>;
};

type DashboardField = {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "checkbox";
  section: string;
  placeholder?: string;
};

type SectionMeta = {
  title: string;
  description: string;
};

const DASHBOARD_FIELDS: DashboardField[] = [
  { key: "assistant_name", label: "Nom de l'assistant", type: "text", section: "General" },
  { key: "GEMINI_API_KEY", label: "Gemini API Key(s)", type: "password", section: "IA", placeholder: "Une ou plusieurs cles, separees par virgule" },
  { key: "XAI_API_KEY", label: "xAI API Key", type: "password", section: "IA" },
  { key: "GROQ_API_KEY", label: "Groq API Key", type: "password", section: "IA" },
  { key: "OLLAMA_ENABLED", label: "Activer Ollama", type: "checkbox", section: "IA" },
  { key: "OLLAMA_PREFER_LOCAL", label: "Preferer Ollama", type: "checkbox", section: "IA" },
  { key: "OLLAMA_URL", label: "Ollama URL", type: "url", section: "IA", placeholder: "http://127.0.0.1:11434" },
  { key: "OLLAMA_MODELS", label: "Modeles Ollama", type: "text", section: "IA", placeholder: "llama3.1:8b,mistral" },
  { key: "YOUTUBE_API_KEY", label: "YouTube API Key", type: "password", section: "Services" },
  { key: "EXTENSION_ACCESS_TOKEN", label: "Token extension Chrome", type: "password", section: "Services", placeholder: "Optionnel, requis hors reseau local" },
  { key: "EMBY_URL", label: "Emby URL", type: "url", section: "Media", placeholder: "http://192.168.x.x:8096" },
  { key: "EMBY_API_KEY", label: "Emby API Key", type: "password", section: "Media" },
  { key: "EMBY_USER_ID", label: "Emby User ID", type: "text", section: "Media" },
  { key: "EMBY_USERNAME", label: "Emby Username", type: "text", section: "Media" },
  { key: "SERPAPI_API_KEY", label: "SerpAPI Key", type: "password", section: "Services" },
  { key: "NASA_API_KEY", label: "NASA API Key", type: "password", section: "Services", placeholder: "Optionnel, DEMO_KEY sinon" },
  { key: "HA_URL", label: "Home Assistant URL", type: "url", section: "Home Assistant", placeholder: "http://192.168.x.x:8123" },
  { key: "HA_TOKEN", label: "Home Assistant Token", type: "password", section: "Home Assistant" },
  { key: "PROXMOX_URL", label: "Proxmox URL", type: "url", section: "Proxmox", placeholder: "https://192.168.x.x:8006" },
  { key: "PROXMOX_TOKEN_ID", label: "Proxmox Token ID", type: "text", section: "Proxmox" },
  { key: "PROXMOX_TOKEN_SECRET", label: "Proxmox Token Secret", type: "password", section: "Proxmox" },
  { key: "PROXMOX_VERIFY_SSL", label: "Verifier le certificat SSL", type: "checkbox", section: "Proxmox" },
  { key: "DISCORD_OWNER_ID", label: "Discord Owner ID", type: "text", section: "Discord" },
  { key: "DISCORD_CLIENT_ID", label: "Discord Client ID", type: "text", section: "Discord" },
  { key: "DISCORD_CLIENT_SECRET", label: "Discord Client Secret", type: "password", section: "Discord" },
  { key: "DISCORD_REDIRECT_URI", label: "Discord Redirect URI", type: "url", section: "Discord", placeholder: "http://IP:8080/auth/discord/callback" },
  { key: "DISCORD_PUBLIC_KEY", label: "Discord Public Key", type: "password", section: "Discord" },
  { key: "DISCORD_BOT_TOKEN", label: "Discord Bot Token", type: "password", section: "Discord" },
];

const WS_SCHEME = window.location.protocol === "https:" ? "wss" : "ws";
const WS_URL = `${WS_SCHEME}://${window.location.hostname}:8765`;
const RECONNECT_INTERVAL_MS = 2_000;
const HTTP_POLL_INTERVAL_MS = 1_000;

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const statusEl = document.getElementById("status-text") as HTMLDivElement;
const errorEl = document.getElementById("error-text") as HTMLDivElement;
const badgeEl = document.getElementById("connection-badge") as HTMLDivElement;
const badgeLabelEl = document.getElementById("connection-label") as HTMLSpanElement;
const assistantLabelEl = document.getElementById("assistant-label") as HTMLDivElement;
const muteButtonEl = document.getElementById("mute-button") as HTMLButtonElement;
const micButtonEl = document.getElementById("mic-button") as HTMLButtonElement;
const dashboardButtonEl = document.getElementById("dashboard-button") as HTMLButtonElement;
const userTextEl = document.getElementById("user-text") as HTMLDivElement;
const jarvisTextEl = document.getElementById("jarvis-text") as HTMLDivElement;
const dashboardPanelEl = document.getElementById("dashboard-panel") as HTMLDivElement;
const dashboardCloseEl = document.getElementById("dashboard-close") as HTMLButtonElement;
const dashboardMetaEl = document.getElementById("dashboard-meta") as HTMLDivElement;
const dashboardSummaryEl = document.getElementById("dashboard-summary") as HTMLDivElement;
const dashboardAuthStatusEl = document.getElementById("dashboard-auth-status") as HTMLDivElement;
const dashboardFlagsEl = document.getElementById("dashboard-config-flags") as HTMLDivElement;
const dashboardDebugPanelEl = document.getElementById("dashboard-debug-panel") as HTMLDivElement;
const dashboardDebugToggleEl = document.getElementById("dashboard-debug-toggle") as HTMLButtonElement;
const dashboardDebugOutputEl = document.getElementById("dashboard-debug-output") as HTMLPreElement;
const webDockEl = document.getElementById("web-dock") as HTMLDivElement;
const webHideButtonEl = document.getElementById("web-hide-button") as HTMLButtonElement;
const webDockTitleEl = document.getElementById("web-dock-title") as HTMLDivElement;
const webImageStripEl = document.getElementById("web-image-strip") as HTMLDivElement;
const webResultListEl = document.getElementById("web-result-list") as HTMLDivElement;
const musicDockEl = document.getElementById("music-dock") as HTMLDivElement;
const musicHideButtonEl = document.getElementById("music-hide-button") as HTMLButtonElement;
const musicSearchInputEl = document.getElementById("music-search-input") as HTMLInputElement;
const musicSearchButtonEl = document.getElementById("music-search-button") as HTMLButtonElement;
const musicStatusEl = document.getElementById("music-status") as HTMLDivElement;
const musicPlayerShellEl = document.getElementById("music-player-shell") as HTMLDivElement;
const musicPlayButtonEl = document.getElementById("music-play-button") as HTMLButtonElement;
const musicPauseButtonEl = document.getElementById("music-pause-button") as HTMLButtonElement;
const musicStopButtonEl = document.getElementById("music-stop-button") as HTMLButtonElement;
const dashboardFieldsEl = document.getElementById("dashboard-fields") as HTMLDivElement;
const dashboardFormEl = document.getElementById("dashboard-form") as HTMLFormElement;
const dashboardLoginEl = document.getElementById("dashboard-login") as HTMLButtonElement;
const dashboardLogoutEl = document.getElementById("dashboard-logout") as HTMLButtonElement;
const dashboardSaveEl = document.getElementById("dashboard-save") as HTMLButtonElement;

const orb = createOrb(canvas);
const CLIENT_ID_STORAGE_KEY = "jarvis_client_id";

function getClientId(): string {
  const existing = window.localStorage.getItem(CLIENT_ID_STORAGE_KEY);
  if (existing) return existing;
  const created = `client-${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`;
  window.localStorage.setItem(CLIENT_ID_STORAGE_KEY, created);
  return created;
}

const STATE_LABELS: Record<OrbState, string> = {
  idle: "",
  listening: "ecoute...",
  thinking: "reflexion...",
  speaking: "",
};

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let httpPollTimer: ReturnType<typeof setTimeout> | null = null;
let currentAudio: HTMLAudioElement | null = null;
let isListening = false;
let speechMode: "wake" | "manual" | null = null;
let manualCapturePending = false;
let preserveConversationOnManualStart = false;
let suppressRecognitionEnd = false;
let micSuspendedForPageLifecycle = false;
let lastWakeRestartAt = 0;
let currentAssistantName = "J.A.R.V.I.S";
let finalTranscriptBuffer = "";
let authStatus: AuthStatus | null = null;
let dashboardOpen = false;
let dashboardLoading = false;
let debugModeEnabled = false;
let debugPollTimer: ReturnType<typeof setTimeout> | null = null;
let debugInteractionLocked = false;
let pendingDebugLines: string[] | null = null;
let youtubeApiLoading = false;
let youtubePlayerReady = false;
let youtubePlayer: {
  loadVideoById: (videoId: string) => void;
  playVideo: () => void;
  pauseVideo: () => void;
  stopVideo: () => void;
  setVolume: (volume: number) => void;
} | null = null;
let pendingMusicLoad: { videoId: string; query: string } | null = null;

const MUSIC_DEFAULT_VOLUME = 60;
const MUSIC_DUCKED_VOLUME = 20;

declare global {
  interface Window {
    YT?: {
      Player: new (
        elementId: string,
        options: {
          height?: string;
          width?: string;
          videoId?: string;
          playerVars?: Record<string, string | number>;
          events?: Record<string, () => void>;
        },
      ) => {
        loadVideoById: (videoId: string) => void;
        playVideo: () => void;
        pauseVideo: () => void;
        stopVideo: () => void;
        setVolume: (volume: number) => void;
      };
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

const SECTION_META: Record<string, SectionMeta> = {
  General: {
    title: "General",
    description: "Identite principale et presentation de l'assistant.",
  },
  IA: {
    title: "IA",
    description: "Fournisseurs de modeles utilises par Jarvis pour raisonner et repondre.",
  },
  Services: {
    title: "Services",
    description: "Sources externes et connecteurs utilitaires relies au dashboard.",
  },
  Media: {
    title: "Media",
    description: "Connexion aux plateformes multimedia personnelles comme Emby.",
  },
  "Home Assistant": {
    title: "Home Assistant",
    description: "Acces domotique local pour piloter l'environnement depuis Jarvis.",
  },
  Proxmox: {
    title: "Proxmox",
    description: "Connexion a l'infrastructure de virtualisation et verification SSL.",
  },
  Discord: {
    title: "Discord",
    description: "Securisation du dashboard et passerelle OAuth d'administration.",
  },
};

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


function setWebDockVisible(visible: boolean): void {
  webDockEl.classList.toggle("is-hidden", !visible);
}

function safeExternalUrl(value: string): string {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function renderWebResults(query: string, items: WebResultItem[] = [], images: WebImageItem[] = []): void {
  webDockTitleEl.textContent = query || "Resultats web";
  webImageStripEl.innerHTML = images.length
    ? images.slice(0, 6).map((image) => {
      const src = escapeHtml(image.src || "");
      const alt = escapeHtml(image.alt || query || "image");
      return src ? `<img src="${src}" alt="${alt}" loading="lazy" />` : "";
    }).join("")
    : `<div class="web-empty-media">Aucune image</div>`;

  webResultListEl.innerHTML = items.length
    ? items.slice(0, 6).map((item) => {
      const title = escapeHtml(item.title || "Resultat web");
      const snippet = escapeHtml(item.snippet || "");
      const source = escapeHtml(item.source || "");
      const link = safeExternalUrl(item.link || "");
      const safeLink = escapeHtml(link);
      const titleHtml = link
        ? `<a href="${safeLink}" target="_blank" rel="noreferrer">${title}</a>`
        : `<strong>${title}</strong>`;
      return `
        <article class="web-result-card">
          <div class="web-result-title">${titleHtml}</div>
          ${source ? `<div class="web-result-source">${source}</div>` : ""}
          ${snippet ? `<p>${snippet}</p>` : ""}
        </article>
      `;
    }).join("")
    : `<div class="web-result-card"><strong>Aucun lien trouve</strong><p>Jarvis n'a pas recu de resultats cliquables pour cette recherche.</p></div>`;
  setWebDockVisible(true);
}

function createEyeIcon(hidden: boolean): string {
  if (hidden) {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M2.7 3.8 20.2 21.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M10.6 6.2A10.7 10.7 0 0 1 12 6.1c5.2 0 8.7 5.1 9.3 5.9a.8.8 0 0 1 0 .8 16.2 16.2 0 0 1-3.3 3.7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14.8 14.9a3 3 0 0 1-4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M9.2 18a10.8 10.8 0 0 1-6.5-5.2.8.8 0 0 1 0-.8A15.8 15.8 0 0 1 6.5 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
  }

  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.7 12a.8.8 0 0 1 0-.8C3.3 10.4 6.8 5.3 12 5.3s8.7 5.1 9.3 5.9a.8.8 0 0 1 0 .8c-.6.8-4.1 5.9-9.3 5.9S3.3 12.8 2.7 12Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/>
    </svg>
  `;
}

function applyState(state: OrbState): void {
  orb.setState(state);
  statusEl.textContent = STATE_LABELS[state];
}

function setMuted(muted: boolean): void {
  muteButtonEl.classList.toggle("is-muted", muted);
  muteButtonEl.setAttribute("aria-pressed", String(muted));
  muteButtonEl.setAttribute("aria-label", muted ? "Remettre le son" : "Couper le son");
  muteButtonEl.title = muted ? "Remettre le son" : "Couper le son";
}

function setMicListening(listening: boolean): void {
  micButtonEl.classList.toggle("is-listening", listening);
  micButtonEl.setAttribute("aria-pressed", String(listening));
  micButtonEl.setAttribute("aria-label", listening ? "Arreter l'ecoute" : "Parler a J.A.R.V.I.S");
  micButtonEl.title = listening ? "Arreter l'ecoute" : "Parler a J.A.R.V.I.S";
  setMusicDucking(listening && speechMode === "manual");
}

function normalizeWakeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function getWakeNames(): string[] {
  const configured = currentAssistantName || "J.A.R.V.I.S";
  const compact = configured.replace(/[.\s]+/g, "");
  const candidates = [configured, compact, "jarvis", "j a r v i s"];
  return [...new Set(candidates.map(normalizeWakeText).filter((name) => name.length >= 2))];
}

function heardWakeName(text: string): boolean {
  const normalizedText = normalizeWakeText(text);
  if (!normalizedText) return false;
  return getWakeNames().some((wakeName) => normalizedText.includes(wakeName));
}

function submitVoiceCommand(text: string): void {
  const command = text.trim();
  if (!command) {
    applyState("idle");
    return;
  }
  setConversation(command, "");
  applyState("thinking");
  if (!sendCommand(command)) {
    applyState("idle");
    showError("WebSocket non connecte");
  }
}

function setAssistantName(name: string): void {
  currentAssistantName = name || "J.A.R.V.I.S";
  assistantLabelEl.textContent = currentAssistantName;
  micButtonEl.setAttribute("aria-label", `Parler a ${currentAssistantName}`);
  micButtonEl.title = `Parler a ${currentAssistantName}`;
}

function setConversation(userText: string, jarvisText = ""): void {
  userTextEl.textContent = userText ? `"${userText}"` : "";
  jarvisTextEl.textContent = jarvisText;
}

function nettoyerTexteJarvis(text: string): string {
  return text.replace(/\{[^}]*\}/gs, "").replace(/\s{2,}/g, " ").trim();
}

function isAppleMobileDevice(): boolean {
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isLocalHttpHost(): boolean {
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function shouldBlockMobileMicroForHttps(): boolean {
  return isAppleMobileDevice() && !window.isSecureContext && !isLocalHttpHost();
}

function pageCanUseMicrophone(): boolean {
  return document.visibilityState === "visible" && !micSuspendedForPageLifecycle;
}

function shouldListenForUserReply(text: string): boolean {
  const normalized = nettoyerTexteJarvis(text).toLowerCase().trim();
  if (!normalized) return false;
  if (normalized.endsWith("?")) return true;
  return /\b(que voulez vous|que veux tu|dites moi|dis moi|repondez|répondez|j.attends votre reponse|j.attends ta reponse|j.attends votre réponse|j.attends ta réponse|voulez vous|veux tu|souhaitez vous|souhaites tu|lequel|laquelle|lesquels|lesquelles|quel choix|quelle option)\b/i.test(normalized);
}

function listenForUserReplyAfterSpeech(text: string): void {
  if (!pageCanUseMicrophone()) return;
  if (shouldListenForUserReply(text)) {
    window.setTimeout(() => startManualListening({ preserveConversation: true }), 250);
    return;
  }
  startWakeListening();
}

let errorTimer: ReturnType<typeof setTimeout> | null = null;

function showError(msg: string): void {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  if (errorTimer) clearTimeout(errorTimer);
  errorTimer = setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 4_000);
}

function setMusicStatus(message: string): void {
  musicStatusEl.textContent = message;
}

function setMusicPlayerVisible(visible: boolean): void {
  musicDockEl.classList.toggle("is-hidden", !visible);
}

function setMusicPlayerEmpty(empty: boolean): void {
  musicPlayerShellEl.classList.toggle("is-empty", empty);
  setMusicPlayerVisible(!empty);
}

function ensureYouTubeApi(): Promise<void> {
  if (window.YT) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve();
    };

    if (!youtubeApiLoading) {
      youtubeApiLoading = true;
      const script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(script);
    }
  });
}

async function ensureMusicPlayer(): Promise<void> {
  await ensureYouTubeApi();
  if (youtubePlayer || !window.YT) return;

  youtubePlayer = new window.YT.Player("music-player", {
    height: "100%",
    width: "100%",
    playerVars: {
      playsinline: 1,
      rel: 0,
      origin: window.location.origin,
    },
    events: {
      onReady: () => {
        youtubePlayerReady = true;
        youtubePlayer?.setVolume(MUSIC_DEFAULT_VOLUME);
        setMusicStatus("Player pret. Demande une musique a Jarvis.");
        if (pendingMusicLoad && youtubePlayer) {
          youtubePlayer.loadVideoById(pendingMusicLoad.videoId);
          youtubePlayer.setVolume(isListening ? MUSIC_DUCKED_VOLUME : MUSIC_DEFAULT_VOLUME);
          setMusicStatus(`Lecture YouTube: ${pendingMusicLoad.query}`);
          musicSearchInputEl.value = pendingMusicLoad.query;
          pendingMusicLoad = null;
        }
      },
    },
  });
}

async function loadMusicVideo(videoId: string, query: string): Promise<void> {
  await ensureMusicPlayer();
  if (!youtubePlayer) {
    throw new Error("youtube_player_unavailable");
  }
  setMusicPlayerEmpty(false);
  setMusicPlayerVisible(true);
  if (!youtubePlayerReady) {
    pendingMusicLoad = { videoId, query };
    setMusicStatus(`Chargement du player pour "${query}"...`);
    return;
  }
  youtubePlayer.loadVideoById(videoId);
  youtubePlayer.setVolume(isListening ? MUSIC_DUCKED_VOLUME : MUSIC_DEFAULT_VOLUME);
  setMusicStatus(`Lecture YouTube: ${query}`);
  musicSearchInputEl.value = query;
}

function playMusic(): void {
  youtubePlayer?.playVideo();
  setMusicStatus("Lecture en cours.");
}

function pauseMusic(): void {
  youtubePlayer?.pauseVideo();
  setMusicStatus("Lecture en pause.");
}

function stopMusic(): void {
  youtubePlayer?.stopVideo();
  setMusicStatus("Lecture arretee.");
  setMusicPlayerVisible(false);
}

function setMusicDucking(active: boolean): void {
  if (!youtubePlayer || !youtubePlayerReady) return;
  youtubePlayer.setVolume(active ? MUSIC_DUCKED_VOLUME : MUSIC_DEFAULT_VOLUME);
}

function setDashboardBusy(busy: boolean, label?: string): void {
  dashboardLoading = busy;
  dashboardSaveEl.disabled = busy;
  dashboardLoginEl.disabled = busy;
  dashboardLogoutEl.disabled = busy;
  dashboardSaveEl.textContent = label || "Enregistrer";
}

function applyDebugLines(lines: string[]): void {
  dashboardDebugOutputEl.textContent = lines.length ? lines.join("\n") : "Aucun log recent disponible.";
  const nearBottom = dashboardDebugOutputEl.scrollHeight - dashboardDebugOutputEl.scrollTop - dashboardDebugOutputEl.clientHeight < 24;
  if (nearBottom || dashboardDebugOutputEl.scrollTop === 0) {
    dashboardDebugOutputEl.scrollTop = dashboardDebugOutputEl.scrollHeight;
  }
}

function setDebugInteractionLocked(locked: boolean): void {
  debugInteractionLocked = locked;
  dashboardDebugPanelEl.classList.toggle("is-paused", locked);
  if (!locked && pendingDebugLines) {
    const lines = pendingDebugLines;
    pendingDebugLines = null;
    applyDebugLines(lines);
  }
}

function stopDebugPolling(): void {
  if (debugPollTimer) {
    clearTimeout(debugPollTimer);
    debugPollTimer = null;
  }
}

function renderDebugState(): void {
  dashboardDebugPanelEl.classList.toggle("is-active", debugModeEnabled);
  dashboardDebugToggleEl.setAttribute("aria-pressed", String(debugModeEnabled));
  dashboardDebugToggleEl.textContent = debugModeEnabled ? "Couper le debug" : "Activer le debug";
  if (!debugModeEnabled) {
    dashboardDebugOutputEl.textContent = "Mode debug inactif.";
  }
}

async function fetchDebugLogs(): Promise<void> {
  if (!dashboardOpen || !debugModeEnabled || !authStatus?.authenticated) return;
  try {
    const response = await fetch("/api/debug/logs?limit=180", { credentials: "same-origin" });
    if (response.status === 401) {
      stopDebugPolling();
      debugModeEnabled = false;
      renderDebugState();
      await fetchAuthStatus();
      return;
    }
    if (!response.ok) {
      throw new Error("debug_logs_failed");
    }
    const data = await response.json() as { lines?: string[] };
    const lines = Array.isArray(data.lines) ? data.lines : [];
    if (debugInteractionLocked) {
      pendingDebugLines = lines;
      return;
    }
    applyDebugLines(lines);
  } catch {
    if (!debugInteractionLocked) {
      dashboardDebugOutputEl.textContent = "Impossible de recuperer la console Jarvis.";
    }
  }
}

function scheduleDebugPolling(immediate = false): void {
  stopDebugPolling();
  if (!dashboardOpen || !debugModeEnabled || !authStatus?.authenticated) return;
  if (immediate) {
    void fetchDebugLogs();
  }
  debugPollTimer = setTimeout(() => {
    void fetchDebugLogs().finally(() => {
      scheduleDebugPolling(false);
    });
  }, 2000);
}

function setConnected(ok: boolean): void {
  badgeEl.classList.toggle("connected", ok);
  badgeEl.classList.toggle("disconnected", !ok);
  badgeLabelEl.textContent = ok ? "connecte" : "reconnexion";
  muteButtonEl.disabled = !ok;
}

async function handleServerMessage(data: WsMessage): Promise<void> {
  if (data.action === "request_screen_capture") {
    const frame = await captureFrame();
    if (frame && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "screen_frame", id: data.id, data: frame }));
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "screen_frame", id: data.id, error: "no_stream" }));
    }
    return;
  }

  if (data.action === "demo") {
    orb.triggerDemo();
    return;
  }

  if (data.action === "jarvis_audio") {
    const spokenText = nettoyerTexteJarvis(data.text || "");
    setConversation(userTextEl.textContent.replace(/^"|"$/g, ""), spokenText);
    if (data.audio_b64) {
      if (currentAudio) currentAudio.pause();
      if (recognition && isListening) {
        suppressRecognitionEnd = true;
        recognition.stop();
      }
      currentAudio = new Audio(`data:audio/mp3;base64,${data.audio_b64}`);
      applyState("speaking");
      void currentAudio.play().catch(() => {
        showError("Lecture audio navigateur impossible");
        applyState("idle");
        listenForUserReplyAfterSpeech(spokenText);
      });
      currentAudio.addEventListener("ended", () => {
        applyState("idle");
        currentAudio = null;
        listenForUserReplyAfterSpeech(spokenText);
      }, { once: true });
    } else {
      listenForUserReplyAfterSpeech(spokenText);
    }
    return;
  }

  if (data.action === "jarvis_response" && typeof data.text === "string") {
    const responseText = nettoyerTexteJarvis(data.text);
    setConversation(userTextEl.textContent.replace(/^"|"$/g, ""), responseText);
    listenForUserReplyAfterSpeech(responseText);
    return;
  }


  if (data.action === "web_results") {
    renderWebResults(data.query || "Recherche web", data.items || [], data.images || []);
    if (typeof data.text === "string") {
      setConversation(userTextEl.textContent.replace(/^"|"$/g, ""), nettoyerTexteJarvis(data.text));
    }
    return;
  }

  if (data.action === "music_search" && typeof data.video_id === "string" && typeof data.query === "string") {
    await loadMusicVideo(data.video_id, data.query);
    return;
  }

  if (data.action === "music_play") {
    playMusic();
    return;
  }

  if (data.action === "music_pause") {
    pauseMusic();
    return;
  }

  if (data.action === "music_stop") {
    stopMusic();
    return;
  }

  if (data.action === "set_volume" && typeof data.volume === "number") {
    orb.setVolume(data.volume);
    return;
  }

  if (data.action === "set_state" && data.state) {
    applyState(data.state as OrbState);
    return;
  }

  if (data.state) {
    applyState(data.state as OrbState);
  }
  if (typeof data.volume === "number") {
    orb.setVolume(data.volume);
  }
  if (typeof data.muted === "boolean") {
    setMuted(data.muted);
  }
}

function stopHttpPolling(): void {
  if (httpPollTimer) {
    clearTimeout(httpPollTimer);
    httpPollTimer = null;
  }
}

function scheduleHttpPolling(delay = HTTP_POLL_INTERVAL_MS): void {
  if (httpPollTimer) return;
  httpPollTimer = setTimeout(() => {
    httpPollTimer = null;
    void pollHttpEvents();
  }, delay);
}

async function pollHttpEvents(): Promise<void> {
  if (ws && ws.readyState === WebSocket.OPEN) {
    stopHttpPolling();
    return;
  }
  try {
    const response = await fetch("/api/client/events", { credentials: "same-origin" });
    if (!response.ok) throw new Error("http_poll_failed");
    const payload = (await response.json()) as { events?: WsMessage[] };
    setConnected(true);
    const events = Array.isArray(payload.events) ? payload.events : [];
    for (const event of events) {
      await handleServerMessage(event);
    }
  } catch {
    setConnected(false);
  } finally {
    scheduleHttpPolling();
  }
}

async function sendCommandHttp(text: string): Promise<boolean> {
  const response = await fetch("/api/command", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, client_id: getClientId() }),
  });
  return response.ok;
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_INTERVAL_MS);
}

function connect(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  ws = new WebSocket(WS_URL);

  ws.addEventListener("open", () => {
    stopHttpPolling();
    setConnected(true);
    ws?.send(JSON.stringify({
      type: "client_hello",
      client_id: getClientId(),
    }));
  });

  ws.addEventListener("message", async (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as WsMessage;
      await handleServerMessage(data);
    } catch {
      // ignore malformed messages
    }
  });

  ws.addEventListener("close", () => {
    setConnected(false);
    applyState("idle");
    scheduleHttpPolling(200);
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    setConnected(false);
    scheduleHttpPolling(200);
  });
}

function sendCommand(text: string): boolean {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "mobile_command",
      text,
      auth_token: authStatus?.authenticated ? authStatus.ws_auth_token || "" : "",
      client_id: getClientId(),
    }));
    return true;
  }

  void sendCommandHttp(text).then((ok) => {
    if (!ok) {
      applyState("idle");
      showError("Envoi HTTP impossible");
      return;
    }
    scheduleHttpPolling(150);
  }).catch(() => {
    applyState("idle");
    showError("Envoi HTTP impossible");
  });
  return true;
}

const speechWindow = window as Window & typeof globalThis & {
  SpeechRecognition?: BrowserSpeechRecognitionCtor;
  webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
};

const SpeechRecognitionCtor =
  speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;

let recognition: BrowserSpeechRecognition | null = null;

if (SpeechRecognitionCtor) {
  recognition = new SpeechRecognitionCtor();
  recognition.lang = "fr-FR";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.addEventListener("start", () => {
    isListening = true;
    setMicListening(speechMode === "manual");
    finalTranscriptBuffer = "";
    if (speechMode === "manual") {
      applyState("listening");
      if (preserveConversationOnManualStart) {
        preserveConversationOnManualStart = false;
      } else {
        setConversation("");
      }
    } else {
      preserveConversationOnManualStart = false;
    }
  });

  recognition.addEventListener("result", ((event: Event) => {
    const speechEvent = event as Event & {
      resultIndex: number;
      results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
    };
    let interim = "";
    let finalText = "";
    for (let i = speechEvent.resultIndex; i < speechEvent.results.length; i += 1) {
      const transcript = speechEvent.results[i][0].transcript;
      if (speechEvent.results[i].isFinal) {
        finalText += transcript;
      } else {
        interim += transcript;
      }
    }

    const heard = (finalText || interim).trim();
    if (speechMode === "manual" || manualCapturePending) {
      setConversation(heard, "");
    }

    if (!finalText.trim()) return;
    finalTranscriptBuffer = `${finalTranscriptBuffer} ${finalText}`.trim();

    if (manualCapturePending || speechMode === "manual") {
      const command = finalTranscriptBuffer.trim();
      manualCapturePending = false;
      suppressRecognitionEnd = true;
      recognition?.stop();
      submitVoiceCommand(command);
      return;
    }

    if (heardWakeName(finalTranscriptBuffer)) {
      suppressRecognitionEnd = true;
      recognition?.stop();
      window.setTimeout(startManualListening, 350);
      return;
    }

    if (finalTranscriptBuffer.length > 240) {
      finalTranscriptBuffer = finalTranscriptBuffer.slice(-160);
    }
  }) as EventListener);

  recognition.addEventListener("end", () => {
    isListening = false;
    setMicListening(false);
    setMusicDucking(false);
    if (suppressRecognitionEnd) {
      suppressRecognitionEnd = false;
      return;
    }
    if (speechMode === "manual") {
      speechMode = "wake";
      applyState("idle");
    }
    if (pageCanUseMicrophone()) {
      window.setTimeout(startWakeListening, 900);
    }
  });

  recognition.addEventListener("error", ((event: Event) => {
    const speechError = event as Event & { error?: string };
    isListening = false;
    setMicListening(false);
    applyState("idle");
    if (speechError.error !== "no-speech" && speechMode === "manual") {
      showError(`Micro navigateur: ${speechError.error || "erreur inconnue"}`);
    }
    if (speechMode !== "manual" && pageCanUseMicrophone()) {
      window.setTimeout(startWakeListening, 1500);
    }
  }) as EventListener);
} else {
  micButtonEl.disabled = true;
  micButtonEl.setAttribute("aria-label", "Micro indisponible");
  micButtonEl.title = "Micro indisponible";
}

function renderDashboardFields(settings: Record<string, string | boolean>): void {
  const sections = new Map<string, DashboardField[]>();
  for (const field of DASHBOARD_FIELDS) {
    const list = sections.get(field.section) || [];
    list.push(field);
    sections.set(field.section, list);
  }

  dashboardFieldsEl.innerHTML = "";
  for (const [section, fields] of sections.entries()) {
    const sectionEl = document.createElement("section");
    sectionEl.className = "dashboard-section";

    const sectionHeadEl = document.createElement("div");
    sectionHeadEl.className = "dashboard-section-head";

    const titleEl = document.createElement("h3");
    titleEl.textContent = SECTION_META[section]?.title || section;
    sectionHeadEl.appendChild(titleEl);

    const descriptionEl = document.createElement("p");
    descriptionEl.className = "dashboard-section-description";
    descriptionEl.textContent = SECTION_META[section]?.description || "";
    sectionHeadEl.appendChild(descriptionEl);

    sectionEl.appendChild(sectionHeadEl);

    const gridEl = document.createElement("div");
    gridEl.className = "dashboard-section-grid";

    for (const field of fields) {
      const rowEl = document.createElement("label");
      rowEl.className = `dashboard-field ${field.type === "checkbox" ? "is-checkbox" : ""}`;
      rowEl.htmlFor = `field-${field.key}`;

      const labelWrapEl = document.createElement("div");
      labelWrapEl.className = "dashboard-field-copy";

      const labelEl = document.createElement("span");
      labelEl.className = "dashboard-field-label";
      labelEl.textContent = field.label;
      labelWrapEl.appendChild(labelEl);

      const keyEl = document.createElement("code");
      keyEl.className = "dashboard-field-key";
      keyEl.textContent = field.key;
      labelWrapEl.appendChild(keyEl);

      rowEl.appendChild(labelWrapEl);

      const inputEl = document.createElement("input");
      inputEl.id = `field-${field.key}`;
      inputEl.name = field.key;
      inputEl.type = field.type === "checkbox" ? "checkbox" : field.type;
      if (field.placeholder) inputEl.placeholder = field.placeholder;

      if (field.type === "checkbox") {
        inputEl.checked = Boolean(settings[field.key]);
        rowEl.appendChild(inputEl);
      } else {
        inputEl.value = String(settings[field.key] ?? "");
        if (field.type === "password") {
          inputEl.autocomplete = "off";
        }

        if (field.type === "password") {
          const inputWrapEl = document.createElement("div");
          inputWrapEl.className = "dashboard-input-wrap";

          const toggleEl = document.createElement("button");
          toggleEl.type = "button";
          toggleEl.className = "dashboard-password-toggle";
          toggleEl.setAttribute("aria-label", "Afficher le contenu");
          toggleEl.title = "Afficher le contenu";
          toggleEl.innerHTML = createEyeIcon(true);
          toggleEl.addEventListener("click", (event) => {
            event.preventDefault();
            const hidden = inputEl.type === "password";
            inputEl.type = hidden ? "text" : "password";
            toggleEl.innerHTML = createEyeIcon(!hidden);
            toggleEl.setAttribute("aria-label", hidden ? "Masquer le contenu" : "Afficher le contenu");
            toggleEl.title = hidden ? "Masquer le contenu" : "Afficher le contenu";
          });

          inputWrapEl.appendChild(inputEl);
          inputWrapEl.appendChild(toggleEl);
          rowEl.appendChild(inputWrapEl);
        } else {
          rowEl.appendChild(inputEl);
        }
      }
      gridEl.appendChild(rowEl);
    }

    sectionEl.appendChild(gridEl);
    dashboardFieldsEl.appendChild(sectionEl);
  }
}

function renderConfigFlags(health: Record<string, ServiceHealth>): void {
  const labels: Record<string, string> = {
    gemini: "Gemini",
    youtube: "YouTube",
    xai: "xAI",
    home_assistant: "Home Assistant",
    serpapi: "SerpAPI",
    groq: "Groq",
    ollama: "Ollama",
    nasa: "NASA",
    emby: "Emby",
    proxmox: "Proxmox",
    discord: "Discord",
  };
  const stateLabels: Record<ServiceHealth["state"], string> = {
    ok: "ok",
    error: "erreur",
    missing: "absent",
  };

  dashboardFlagsEl.innerHTML = "";
  Object.entries(labels).forEach(([key, label]) => {
    const entry = health[key] || { state: "missing" as const };
    const pill = document.createElement("span");
    pill.className = `config-pill is-${entry.state}`;
    pill.textContent = `${label} ${stateLabels[entry.state]}`;
    if (entry.detail) {
      pill.title = entry.detail;
    }
    dashboardFlagsEl.appendChild(pill);
  });
}

function renderDashboardMeta(status: AuthStatus | null): void {
  const authLabel = status?.authenticated
    ? (status.user?.global_name || status.user?.username || "owner")
    : "Lecture seule";
  const authState = status?.authenticated ? "Session ouverte" : "Verrouille";

  dashboardMetaEl.innerHTML = `
    <div class="dashboard-meta-card">
      <span class="dashboard-meta-label">Assistant</span>
      <strong>${escapeHtml(status?.assistant_name || "J.A.R.V.I.S")}</strong>
    </div>
    <div class="dashboard-meta-card">
      <span class="dashboard-meta-label">Acces</span>
      <strong>${escapeHtml(authState)}</strong>
      <span class="dashboard-meta-subtle">${escapeHtml(authLabel)}</span>
    </div>
    <div class="dashboard-meta-card">
      <span class="dashboard-meta-label">Surface</span>
      <strong>VM Debian</strong>
      <span class="dashboard-meta-subtle">Port 8080 / websocket 8765</span>
    </div>
  `;
}

function renderDashboardSummary(status: AuthStatus | null, health: Record<string, ServiceHealth>): void {
  const total = Object.keys(health).length;
  const okCount = Object.values(health).filter((entry) => entry.state === "ok").length;
  const authMode = status?.discord_configured ? "Discord" : "Libre";
  const writeMode = status?.authenticated ? "Edition" : "Protege";

  dashboardSummaryEl.innerHTML = `
    <article class="dashboard-summary-card">
      <span class="dashboard-summary-label">Integrations saines</span>
      <strong>${okCount}/${total || 0}</strong>
      <p>Vert si l'API repond, rouge si elle echoue, noir si elle manque.</p>
    </article>
    <article class="dashboard-summary-card">
      <span class="dashboard-summary-label">Controle d'acces</span>
      <strong>${escapeHtml(authMode)}</strong>
      <p>${status?.discord_configured ? "Le dashboard est securise par OAuth Discord." : "Le dashboard reste utilisable sans passerelle Discord."}</p>
    </article>
    <article class="dashboard-summary-card">
      <span class="dashboard-summary-label">Mode actuel</span>
      <strong>${escapeHtml(writeMode)}</strong>
      <p>${status?.authenticated ? "Les changements peuvent etre enregistres tout de suite." : "Authentification requise pour modifier les reglages."}</p>
    </article>
  `;
}

async function fetchAuthStatus(): Promise<AuthStatus | null> {
  try {
    const response = await fetch("/api/auth/status", { credentials: "same-origin" });
    const data = await response.json() as AuthStatus;
    authStatus = data;
    setAssistantName(data.assistant_name);
    dashboardButtonEl.classList.toggle("is-authenticated", data.authenticated);
    renderDashboardMeta(data);
    renderDashboardSummary(data, data.service_health || {});
    renderConfigFlags(data.service_health || {});
    dashboardAuthStatusEl.textContent = data.authenticated
      ? `Connecte en tant que ${data.user?.global_name || data.user?.username || "owner"}`
      : (data.discord_configured
          ? "Dashboard protege par Discord. Connecte-toi pour modifier les reglages."
          : "Discord n'est pas encore configure sur le serveur.");
    dashboardLoginEl.style.display = data.authenticated || !data.discord_configured ? "none" : "inline-flex";
    dashboardLogoutEl.style.display = data.authenticated ? "inline-flex" : "none";
    dashboardSaveEl.style.display = data.authenticated ? "inline-flex" : "none";
    if (!data.authenticated) {
      dashboardFieldsEl.innerHTML = "";
      stopDebugPolling();
      debugModeEnabled = false;
      renderDebugState();
    }
    return data;
  } catch {
    showError("Impossible de recuperer l'etat du dashboard");
    return null;
  }
}

async function loadDashboardSettings(): Promise<void> {
  setDashboardBusy(true, "Chargement...");
  const response = await fetch("/api/settings", { credentials: "same-origin" });
  if (response.status === 401) {
    setDashboardBusy(false);
    await fetchAuthStatus();
    return;
  }
  if (!response.ok) {
    setDashboardBusy(false);
    throw new Error("settings_load_failed");
  }
  const data = await response.json() as SettingsResponse;
  renderDashboardFields(data.settings);
  renderConfigFlags(data.service_health || {});
  renderDashboardSummary(authStatus, data.service_health || {});
  setDashboardBusy(false);
}

async function saveDashboardSettings(): Promise<void> {
  setDashboardBusy(true, "Enregistrement...");
  const payload: Record<string, string | boolean> = {};
  DASHBOARD_FIELDS.forEach((field) => {
    const inputEl = document.getElementById(`field-${field.key}`) as HTMLInputElement | null;
    if (!inputEl) return;
    payload[field.key] = field.type === "checkbox" ? inputEl.checked : inputEl.value;
  });

  const response = await fetch("/api/settings", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) {
    setDashboardBusy(false);
    showError("Connexion Discord requise");
    await fetchAuthStatus();
    return;
  }
  if (!response.ok) {
    setDashboardBusy(false);
    throw new Error("settings_save_failed");
  }
  const data = await response.json() as SettingsResponse & { ok: boolean };
  renderDashboardFields(data.settings);
  renderConfigFlags(data.service_health || {});
  renderDashboardSummary(authStatus, data.service_health || {});
  setAssistantName(String(data.settings.assistant_name || "J.A.R.V.I.S"));
  setDashboardBusy(false);
  showError("Reglages enregistres");
}

function setDashboardOpen(open: boolean): void {
  dashboardOpen = open;
  dashboardPanelEl.classList.toggle("is-open", open);
  dashboardPanelEl.setAttribute("aria-hidden", String(!open));
  document.body.classList.toggle("dashboard-open", open);
  if (!open) {
    stopDebugPolling();
  } else if (debugModeEnabled) {
    scheduleDebugPolling(true);
  }
}

async function openDashboard(): Promise<void> {
  const status = await fetchAuthStatus();
  setDashboardOpen(true);
  if (!status) return;
  if (status.authenticated) {
    await loadDashboardSettings();
  }
}

function closeDashboard(): void {
  setDashboardOpen(false);
}

function handleUrlFeedback(): void {
  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");
  const shouldOpenDashboard = params.get("dashboard") === "1";

  if (error) {
    const messages: Record<string, string> = {
      discord_non_configure: "Discord n'est pas configure sur le serveur.",
      discord_state_invalide: "Retour Discord invalide.",
      discord_oauth_echec: "Connexion Discord echouee.",
      discord_acces_refuse: "Cet utilisateur Discord n'est pas autorise.",
    };
    showError(messages[error] || "Erreur Discord");
  }

  if (error || shouldOpenDashboard) {
    const cleanUrl = `${window.location.pathname}${window.location.hash}`;
    window.history.replaceState({}, document.title, cleanUrl);
  }

  if (shouldOpenDashboard) {
    void openDashboard();
  }
}

muteButtonEl.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "stop_audio" }));
  applyState("idle");
});

function startWakeListening(): void {
  if (!recognition || isListening || !pageCanUseMicrophone()) return;
  const now = Date.now();
  if (now - lastWakeRestartAt < 700) return;
  lastWakeRestartAt = now;
  speechMode = "wake";
  manualCapturePending = false;
  finalTranscriptBuffer = "";
  try {
    recognition.start();
  } catch {
    // Chrome peut refuser un redemarrage trop rapide; le prochain cycle retentera.
  }
}

function startManualListening(options: { preserveConversation?: boolean } = {}): void {
  if (!pageCanUseMicrophone()) return;
  if (shouldBlockMobileMicroForHttps()) {
    showError("Sur iPhone/iPad, ouvre J.A.R.V.I.S en HTTPS pour autoriser le micro.");
    return;
  }
  if (!recognition) return;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  finalTranscriptBuffer = "";
  manualCapturePending = true;
  speechMode = "manual";
  preserveConversationOnManualStart = Boolean(options.preserveConversation);
  if (isListening) {
    applyState("listening");
    setMicListening(true);
    setMusicDucking(true);
    if (preserveConversationOnManualStart) {
      preserveConversationOnManualStart = false;
    } else {
      setConversation("");
    }
    return;
  }
  try {
    recognition.start();
  } catch {
    preserveConversationOnManualStart = false;
    showError("Impossible de demarrer le micro");
  }
}

micButtonEl.addEventListener("click", () => {
  micSuspendedForPageLifecycle = false;
  startManualListening();
});

function stopBrowserMicrophoneForPageLifecycle(): void {
  micSuspendedForPageLifecycle = true;
  suppressRecognitionEnd = true;
  manualCapturePending = false;
  preserveConversationOnManualStart = false;
  speechMode = null;
  finalTranscriptBuffer = "";
  if (recognition && isListening) {
    try {
      if (recognition.abort) {
        recognition.abort();
      } else {
        recognition.stop();
      }
    } catch {
      // Safari peut deja avoir ferme la session micro.
    }
  }
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  isListening = false;
  setMicListening(false);
  setMusicDucking(false);
  applyState("idle");
}

function resumeBrowserMicrophoneAfterPageLifecycle(): void {
  micSuspendedForPageLifecycle = false;
  suppressRecognitionEnd = false;
  startWakeListening();
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    stopBrowserMicrophoneForPageLifecycle();
    return;
  }
  resumeBrowserMicrophoneAfterPageLifecycle();
});

window.addEventListener("pagehide", stopBrowserMicrophoneForPageLifecycle);
window.addEventListener("beforeunload", stopBrowserMicrophoneForPageLifecycle);

dashboardButtonEl.addEventListener("click", () => {
  if (dashboardOpen) {
    closeDashboard();
    return;
  }
  void openDashboard();
});

dashboardCloseEl.addEventListener("click", () => {
  closeDashboard();
});

dashboardPanelEl.addEventListener("click", (event) => {
  if (event.target === dashboardPanelEl) {
    closeDashboard();
  }
});

dashboardLoginEl.addEventListener("click", () => {
  window.location.href = "/auth/discord/login";
});

dashboardLogoutEl.addEventListener("click", () => {
  window.location.href = "/auth/logout";
});

dashboardFormEl.addEventListener("submit", (event) => {
  event.preventDefault();
  void saveDashboardSettings().catch(() => {
    showError("Impossible d'enregistrer les reglages");
  });
});

dashboardDebugToggleEl.addEventListener("click", () => {
  if (!authStatus?.authenticated) {
    showError("Connexion Discord requise");
    return;
  }
  debugModeEnabled = !debugModeEnabled;
  renderDebugState();
  scheduleDebugPolling(true);
});

dashboardDebugOutputEl.addEventListener("mouseenter", () => {
  setDebugInteractionLocked(true);
});

dashboardDebugOutputEl.addEventListener("mouseleave", () => {
  setDebugInteractionLocked(false);
});

dashboardDebugOutputEl.addEventListener("focusin", () => {
  setDebugInteractionLocked(true);
});

dashboardDebugOutputEl.addEventListener("focusout", () => {
  setDebugInteractionLocked(false);
});

musicSearchButtonEl.addEventListener("click", () => {
  const query = musicSearchInputEl.value.trim();
  if (!query) return;
  if (!sendCommand(`mets ${query}`)) {
    showError("WebSocket non connecte");
  } else {
    setMusicStatus(`Demande envoyee a Jarvis pour "${query}"...`);
  }
});

musicSearchInputEl.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  musicSearchButtonEl.click();
});

musicPlayButtonEl.addEventListener("click", () => {
  playMusic();
});

musicPauseButtonEl.addEventListener("click", () => {
  pauseMusic();
});

musicStopButtonEl.addEventListener("click", () => {
  stopMusic();
});

webHideButtonEl.addEventListener("click", () => {
  setWebDockVisible(false);
});

musicHideButtonEl.addEventListener("click", () => {
  stopMusic();
});

setConnected(false);
applyState("idle");
setMuted(false);
setMicListening(false);
setAssistantName("J.A.R.V.I.S");
setMusicStatus("Aucune musique chargee.");
setMusicPlayerVisible(false);
setMusicPlayerEmpty(true);
setWebDockVisible(false);
renderDebugState();
injectVisionButton();
scheduleHttpPolling(400);
connect();
if (pageCanUseMicrophone()) {
  startWakeListening();
}
void fetchAuthStatus();
handleUrlFeedback();
