document.addEventListener("DOMContentLoaded", async () => {
  const profileInput = document.getElementById("profileInput");
  const saveBtn = document.getElementById("saveBtn");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");

  // Load saved profile name
  chrome.storage.local.get(["profileName"], (res) => {
    if (res.profileName) {
      profileInput.value = res.profileName;
    } else {
      profileInput.value = "YOUTUBE";
    }
  });

  // Check Studio connection
  try {
    const res = await fetch("http://127.0.0.1:18999/status");
    if (res.ok) {
      statusDot.style.backgroundColor = "#10b981";
      statusText.textContent = "Connected to Studio";
    } else {
      statusDot.style.backgroundColor = "#f59e0b";
      statusText.textContent = "Studio Standby";
    }
  } catch (e) {
    statusDot.style.backgroundColor = "#94a3b8";
    statusText.textContent = "Waiting for Studio...";
  }

  // Save profile name
  saveBtn.addEventListener("click", () => {
    const val = profileInput.value.trim();
    if (val) {
      chrome.storage.local.set({ profileName: val }, () => {
        saveBtn.textContent = "Saved ✓";
        setTimeout(() => {
          saveBtn.textContent = "Save Profile Name";
        }, 1500);
      });
    }
  });
});
