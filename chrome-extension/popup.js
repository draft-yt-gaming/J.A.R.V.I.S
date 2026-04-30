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
let summaryAudio = null;
let summaryAudioUrl = "";

function setResult(message) {
  result.textContent = message;
}

function setSpeechStatus(message) {
  speechStatus.textContent = message;
}

function normalizeServerUrl(value) {
  return (value || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "");
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: latestSummary }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || payload.error || `Erreur HTTP ${response.status}`);
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
  revokeSummaryAudio();
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
    resetSpeechControls("Pret a lire avec la voix Jarvis");
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

void loadSettings();
void loadCurrentTab();
