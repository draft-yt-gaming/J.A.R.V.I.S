const DEFAULT_SERVER_URL = "http://192.168.2.102:8080";

const button = document.getElementById("summarize-button");
const result = document.getElementById("result");
const serverInput = document.getElementById("server-url");
const pageTitle = document.getElementById("page-title");
const pageUrl = document.getElementById("page-url");
const speakButton = document.getElementById("speak-button");
const pauseButton = document.getElementById("pause-button");
const stopButton = document.getElementById("stop-button");
const speechStatus = document.getElementById("speech-status");

let currentTab = null;
let latestSummary = "";
let speechPaused = false;

function setResult(message) {
  result.textContent = message;
}

function setSpeechStatus(message) {
  speechStatus.textContent = message;
}

function normalizeServerUrl(value) {
  return (value || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "");
}

function getFrenchVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  return voices.find((voice) => voice.lang?.toLowerCase().startsWith("fr")) || voices[0] || null;
}

function stopSpeech() {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  speechPaused = false;
  pauseButton.textContent = "⏯";
  pauseButton.disabled = true;
  stopButton.disabled = true;
  if (latestSummary) setSpeechStatus("Lecture arretee");
}

function speakSummary() {
  if (!latestSummary.trim()) {
    setSpeechStatus("Aucun resume a lire");
    return;
  }
  if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    setSpeechStatus("Lecture vocale indisponible dans ce navigateur");
    return;
  }

  stopSpeech();
  const utterance = new SpeechSynthesisUtterance(latestSummary);
  const voice = getFrenchVoice();
  if (voice) utterance.voice = voice;
  utterance.lang = voice?.lang || "fr-FR";
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onstart = () => {
    speechPaused = false;
    pauseButton.disabled = false;
    stopButton.disabled = false;
    setSpeechStatus("Lecture en cours");
  };
  utterance.onend = () => {
    speechPaused = false;
    pauseButton.textContent = "⏯";
    pauseButton.disabled = true;
    stopButton.disabled = true;
    setSpeechStatus("Lecture terminee");
  };
  utterance.onerror = () => {
    speechPaused = false;
    pauseButton.disabled = true;
    stopButton.disabled = true;
    setSpeechStatus("Erreur de lecture vocale");
  };
  window.speechSynthesis.speak(utterance);
}

function toggleSpeechPause() {
  if (!window.speechSynthesis?.speaking) return;
  if (speechPaused) {
    window.speechSynthesis.resume();
    speechPaused = false;
    pauseButton.textContent = "⏯";
    setSpeechStatus("Lecture en cours");
  } else {
    window.speechSynthesis.pause();
    speechPaused = true;
    pauseButton.textContent = "▶";
    setSpeechStatus("Lecture en pause");
  }
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER_URL });
  serverInput.value = normalizeServerUrl(stored.serverUrl);
}

async function saveServerUrl() {
  await chrome.storage.sync.set({ serverUrl: normalizeServerUrl(serverInput.value) });
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
  return page;
}

async function summarizePage() {
  button.disabled = true;
  speakButton.disabled = true;
  stopSpeech();
  latestSummary = "";
  setResult("Lecture de la page...");
  setSpeechStatus("Resume en preparation");
  try {
    await saveServerUrl();
    const page = await extractPage();
    setResult("Jarvis prepare le resume...");
    const response = await fetch(`${normalizeServerUrl(serverInput.value)}/api/extension/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(page),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || `Erreur HTTP ${response.status}`);
    }
    const suffix = payload.truncated ? "\n\nNote: page coupee car elle etait tres longue." : "";
    latestSummary = `${payload.summary || "Aucun resume recu."}${suffix}`;
    setResult(latestSummary);
    speakButton.disabled = !latestSummary.trim();
    setSpeechStatus("Pret a lire le resume");
  } catch (error) {
    setResult(`Erreur: ${error.message}`);
    setSpeechStatus("Lecture vocale indisponible");
  } finally {
    button.disabled = false;
  }
}

serverInput.addEventListener("change", saveServerUrl);
button.addEventListener("click", summarizePage);
speakButton.addEventListener("click", speakSummary);
pauseButton.addEventListener("click", toggleSpeechPause);
stopButton.addEventListener("click", stopSpeech);
window.speechSynthesis?.addEventListener?.("voiceschanged", getFrenchVoice);

void loadSettings();
void loadCurrentTab();
