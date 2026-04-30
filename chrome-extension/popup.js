const DEFAULT_SERVER_URL = "http://192.168.2.102:8080";

const button = document.getElementById("summarize-button");
const result = document.getElementById("result");
const serverInput = document.getElementById("server-url");
const accessTokenInput = document.getElementById("access-token");
const pageTitle = document.getElementById("page-title");
const pageUrl = document.getElementById("page-url");
const speakButton = document.getElementById("speak-button");
const pauseButton = document.getElementById("pause-button");
const stopButton = document.getElementById("stop-button");
const speechStatus = document.getElementById("speech-status");
const copySelectionButton = document.getElementById("copy-selection-button");
const selectionStatus = document.getElementById("selection-status");

let currentTab = null;
let latestSummary = "";
let summaryAudio = null;
let summaryAudioUrl = "";

function setResult(message) {
  result.textContent = message;
}

function setSpeechStatus(message) {
  speechStatus.textContent = message;
}

function hostLooksLocal(hostname) {
  const host = String(hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
  return (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host.startsWith("192.168.") ||
    host.startsWith("10.") ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(host)
  );
}

function defaultSchemeForServer(rawValue) {
  if (/:443(?:\/|$)/.test(rawValue) || /:8443(?:\/|$)/.test(rawValue)) return "https";
  if (/:8080(?:\/|$)/.test(rawValue)) return "http";
  return hostLooksLocal(rawValue.split(/[/:]/)[0]) ? "http" : "https";
}

function normalizeServerUrl(value) {
  const rawValue = (value || DEFAULT_SERVER_URL).trim();
  if (!rawValue) return DEFAULT_SERVER_URL;

  const withScheme = /^https?:\/\//i.test(rawValue)
    ? rawValue
    : `${defaultSchemeForServer(rawValue)}://${rawValue}`;

  try {
    return new URL(withScheme).origin.replace(/\/+$/, "");
  } catch (_error) {
    return rawValue.replace(/\/+$/, "");
  }
}

function getAccessToken() {
  return String(accessTokenInput?.value || "").trim();
}

function buildJsonHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = getAccessToken();
  if (token) headers["X-Jarvis-Extension-Token"] = token;
  return headers;
}

function extensionErrorMessage(status, payload) {
  if (status === 403) {
    return payload.detail || "Acces refuse: ajoute le token extension si tu utilises un domaine public.";
  }
  return payload.detail || payload.error || `Erreur HTTP ${status}`;
}

function revokeSummaryAudio() {
  if (summaryAudio) {
    summaryAudio.pause();
    summaryAudio.src = "";
    summaryAudio = null;
  }
  if (summaryAudioUrl) {
    URL.revokeObjectURL(summaryAudioUrl);
    summaryAudioUrl = "";
  }
}

function resetSpeechControls(message = "Lecture vocale prete apres resume") {
  pauseButton.textContent = "⏯";
  speakButton.disabled = !latestSummary.trim();
  pauseButton.disabled = true;
  stopButton.disabled = true;
  setSpeechStatus(message);
}

function stopSpeech() {
  if (summaryAudio) {
    summaryAudio.pause();
    summaryAudio.currentTime = 0;
  }
  resetSpeechControls(latestSummary ? "Lecture arretee" : "Lecture vocale prete apres resume");
}

async function ensureSummaryAudio() {
  if (summaryAudio) return summaryAudio;
  if (!latestSummary.trim()) throw new Error("Aucun resume a lire.");

  setSpeechStatus("Creation de la voix Jarvis...");
  const response = await fetch(`${normalizeServerUrl(serverInput.value)}/api/extension/tts`, {
    method: "POST",
    credentials: "include",
    headers: buildJsonHeaders(),
    body: JSON.stringify({ text: latestSummary }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(extensionErrorMessage(response.status, payload));
  }

  const audioBlob = await response.blob();
  summaryAudioUrl = URL.createObjectURL(audioBlob);
  summaryAudio = new Audio(summaryAudioUrl);
  summaryAudio.addEventListener("play", () => {
    pauseButton.textContent = "⏯";
    pauseButton.disabled = false;
    stopButton.disabled = false;
    setSpeechStatus("Voix Jarvis en cours");
  });
  summaryAudio.addEventListener("pause", () => {
    if (summaryAudio && summaryAudio.currentTime > 0 && summaryAudio.currentTime < summaryAudio.duration) {
      pauseButton.textContent = "▶";
      setSpeechStatus("Lecture en pause");
    }
  });
  summaryAudio.addEventListener("ended", () => {
    resetSpeechControls("Lecture terminee");
  });
  summaryAudio.addEventListener("error", () => {
    resetSpeechControls("Erreur audio Jarvis");
  });
  return summaryAudio;
}

async function speakSummary() {
  try {
    const audio = await ensureSummaryAudio();
    audio.currentTime = 0;
    await audio.play();
  } catch (error) {
    setSpeechStatus(`Erreur: ${error.message}`);
  }
}

function toggleSpeechPause() {
  if (!summaryAudio) return;
  if (summaryAudio.paused) {
    void summaryAudio.play();
  } else {
    summaryAudio.pause();
  }
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER_URL, accessToken: "" });
  serverInput.value = normalizeServerUrl(stored.serverUrl);
  accessTokenInput.value = stored.accessToken || "";
}

async function saveSettings() {
  const normalizedUrl = normalizeServerUrl(serverInput.value);
  serverInput.value = normalizedUrl;
  await chrome.storage.sync.set({ serverUrl: normalizedUrl, accessToken: getAccessToken() });
}

async function loadCurrentTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tabs[0] || null;
  pageTitle.textContent = currentTab?.title || "Onglet Chrome";
  pageUrl.textContent = currentTab?.url || "";
}

async function extractPage() {
  if (!currentTab?.id) throw new Error("Aucun onglet actif detecte.");
  const [{ result: page }] = await chrome.scripting.executeScript({
    target: { tabId: currentTab.id },
    files: ["content.js"],
  });
  if (!page?.text) throw new Error("Je n'arrive pas a lire le texte de cette page.");
  if (page.text.trim().length < 120) {
    throw new Error("Le texte lisible de cette page est trop court pour faire un resume fiable.");
  }
  return page;
}

async function copyPageSelection() {
  copySelectionButton.disabled = true;
  selectionStatus.textContent = "Lecture de la selection...";
  try {
    if (!currentTab?.id) throw new Error("Aucun onglet actif detecte.");
    const [{ result: selectedText }] = await chrome.scripting.executeScript({
      target: { tabId: currentTab.id },
      func: () => String(window.getSelection ? window.getSelection().toString() : "").trim(),
    });
    if (!selectedText) {
      throw new Error("Aucun texte selectionne dans la page.");
    }
    await navigator.clipboard.writeText(selectedText);
    selectionStatus.textContent = `${selectedText.length} caracteres copies`;
  } catch (error) {
    selectionStatus.textContent = `Erreur: ${error.message}`;
  } finally {
    copySelectionButton.disabled = false;
  }
}

async function summarizePage() {
  button.disabled = true;
  speakButton.disabled = true;
  revokeSummaryAudio();
  latestSummary = "";
  setResult("Lecture de la page...");
  setSpeechStatus("Resume en preparation");
  try {
    await saveSettings();
    const page = await extractPage();
    setResult("Jarvis prepare le resume...");
    const response = await fetch(`${normalizeServerUrl(serverInput.value)}/api/extension/summarize`, {
      method: "POST",
      credentials: "include",
      headers: buildJsonHeaders(),
      body: JSON.stringify(page),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(extensionErrorMessage(response.status, payload));
    }
    const suffix = payload.truncated ? "\n\nNote: page coupee car elle etait tres longue." : "";
    latestSummary = `${payload.summary || "Aucun resume recu."}${suffix}`;
    setResult(latestSummary);
    speakButton.disabled = !latestSummary.trim();
    resetSpeechControls("Pret a lire avec la voix Jarvis");
  } catch (error) {
    setResult(`Erreur: ${error.message}`);
    setSpeechStatus("Lecture vocale indisponible");
  } finally {
    button.disabled = false;
  }
}

serverInput.addEventListener("change", saveSettings);
accessTokenInput.addEventListener("change", saveSettings);
button.addEventListener("click", summarizePage);
copySelectionButton.addEventListener("click", copyPageSelection);
speakButton.addEventListener("click", speakSummary);
pauseButton.addEventListener("click", toggleSpeechPause);
stopButton.addEventListener("click", stopSpeech);

void loadSettings();
void loadCurrentTab();
