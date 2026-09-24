// Popup Script for VEO 3 Bridge
document.addEventListener("DOMContentLoaded", async () => {
  const profileInput = document.getElementById("profileName");
  const btnSave = document.getElementById("btnSaveProfile");
  const instanceIdSpan = document.getElementById("instanceId");
  const appStatusSpan = document.getElementById("appStatus");
  const flowStatusSpan = document.getElementById("flowStatus");
  const projectStatusSpan = document.getElementById("projectStatus");
  const tabIdSpan = document.getElementById("tabId");
  const opStatusSpan = document.getElementById("operationalStatus");
  const btnRefresh = document.getElementById("btnRefresh");

  // Load stored profile identity
  chrome.storage.local.get(["profileName", "extensionInstanceId"], (data) => {
    if (data.profileName) {
      profileInput.value = data.profileName;
    }
    if (data.extensionInstanceId) {
      instanceIdSpan.textContent = data.extensionInstanceId;
    }
  });

  // Query background worker for live state
  function updateState() {
    chrome.runtime.sendMessage({ action: "GET_LIVE_STATUS" }, (res) => {
      if (!res) return;

      if (res.extensionInstanceId) {
        instanceIdSpan.textContent = res.extensionInstanceId;
      }
      if (res.profileName && !profileInput.value) {
        profileInput.value = res.profileName;
      }

      // Desktop App Status
      if (res.appConnected) {
        appStatusSpan.textContent = "CONNECTED ✓";
        appStatusSpan.className = "val green";
      } else {
        appStatusSpan.textContent = "WAITING / OFFLINE";
        appStatusSpan.className = "val yellow";
      }

      // Flow Tab Status
      if (res.flowTabFound) {
        flowStatusSpan.textContent = "CONNECTED ✓";
        flowStatusSpan.className = "val green";
      } else {
        flowStatusSpan.textContent = "NOT FOUND";
        flowStatusSpan.className = "val yellow";
      }

      // Project Status
      if (res.projectVerified) {
        projectStatusSpan.textContent = "VERIFIED ✓";
        projectStatusSpan.className = "val green";
      } else if (res.projectMismatch) {
        projectStatusSpan.textContent = "MISMATCH ⚠";
        projectStatusSpan.className = "val red";
      } else if (res.flowLoading) {
        projectStatusSpan.textContent = "LOADING...";
        projectStatusSpan.className = "val yellow";
      } else {
        projectStatusSpan.textContent = "--";
        projectStatusSpan.className = "val";
      }

      // Tab ID
      tabIdSpan.textContent = res.flowTabId ? res.flowTabId.toString() : "None";

      // Operational Status
      opStatusSpan.textContent = res.operationalStatus || "IDLE";
      if (res.operationalStatus === "PROCESSING") {
        opStatusSpan.className = "val yellow bold";
      } else {
        opStatusSpan.className = "val green bold";
      }
    });
  }

  // Save profile name
  btnSave.addEventListener("click", () => {
    const newName = profileInput.value.trim();
    if (!newName) return;

    chrome.storage.local.set({ profileName: newName }, () => {
      btnSave.textContent = "Saved!";
      setTimeout(() => { btnSave.textContent = "Save"; }, 1200);
      chrome.runtime.sendMessage({ action: "SET_PROFILE_NAME", profileName: newName }, () => {
        updateState();
      });
    });
  });

  // Refresh
  btnRefresh.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "SCAN_FLOW_TABS" }, () => {
      updateState();
    });
  });

  // Initial update + timer
  updateState();
  setInterval(updateState, 1500);
});
