const DEFAULT_SERVER_URL = "http://192.168.2.102:8080";

const button = document.getElementById("summarize-button");
const result = document.getElementById("result");
const serverInput = document.getElementById("server-url");
const pageTitle = document.getElementById("page-title");
const pageUrl = document.getElementById("page-url");

let currentTab = null;

function setResult(message) {
  result.textContent = message;
}

function normalizeServerUrl(value) {
  return (value || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "");
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
  setResult("Lecture de la page...");
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
    setResult(`${payload.summary || "Aucun resume recu."}${suffix}`);
  } catch (error) {
    setResult(`Erreur: ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

serverInput.addEventListener("change", saveServerUrl);
button.addEventListener("click", summarizePage);

void loadSettings();
void loadCurrentTab();
