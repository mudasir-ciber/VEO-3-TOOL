// Background Service Worker for Chained Evolution Studio (VEO 3)
// Full In-Browser Extension Architecture

const DEFAULT_TARGET_PROJECT_ID = "aa6e6e2c-c62d-43c6-88fe-56d75dff99e4";

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[VEO 3 Studio] Extension installed or updated:", details.reason);
  // Auto-open Studio Dashboard on first install
  if (details.reason === "install") {
    chrome.tabs.create({ url: chrome.runtime.getURL("studio.html") });
  }
});

// Listen for messages from Studio UI or Content Script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const action = message.action;

  if (action === "OPEN_STUDIO") {
    chrome.tabs.create({ url: chrome.runtime.getURL("studio.html") });
    sendResponse({ success: true });
    return true;
  }

  if (action === "OPEN_FLOW") {
    const url = message.url || `https://flow.google.com/project/${DEFAULT_TARGET_PROJECT_ID}`;
    chrome.tabs.create({ url });
    sendResponse({ success: true });
    return true;
  }

  if (action === "GET_FLOW_STATE") {
    scanFlowTabs().then(state => sendResponse(state));
    return true; // Keep channel open for async response
  }

  return true;
});

// Scan all open tabs to find and inspect Google Flow
async function scanFlowTabs() {
  try {
    const tabs = await chrome.tabs.query({});
    let targetTab = null;
    let mismatchTab = null;

    for (const tab of tabs) {
      if (!tab.url) continue;
      const url = tab.url.toLowerCase();
      if (url.includes("flow.google.com") || url.includes("labs.google.com/flow")) {
        if (url.includes(DEFAULT_TARGET_PROJECT_ID.toLowerCase())) {
          targetTab = tab;
          break;
        } else {
          mismatchTab = tab;
        }
      }
    }

    if (targetTab) {
      return {
        status: "FLOW_READY",
        tabId: targetTab.id,
        url: targetTab.url,
        verified: true
      };
    } else if (mismatchTab) {
      return {
        status: "FLOW_PROJECT_MISMATCH",
        tabId: mismatchTab.id,
        url: mismatchTab.url,
        verified: false
      };
    } else {
      return {
        status: "FLOW_TAB_NOT_FOUND",
        tabId: null,
        url: "",
        verified: false
      };
    }
  } catch (err) {
    console.error("[VEO 3 Studio] Tab scan error:", err);
    return { status: "ERROR", error: err.message };
  }
}
