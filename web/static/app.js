const dropZone = document.getElementById("drop-zone");
const videoInput = document.getElementById("video-input");
const fileNameEl = document.getElementById("file-name");
const fileListEl = document.getElementById("file-list");
const runBtn = document.getElementById("run-btn");
const statusLog = document.getElementById("status-log");
const resultsSection = document.getElementById("results-section");
const envBadge = document.getElementById("env-badge");
const modelsSelect = document.getElementById("models-select");
const geminiModel = document.getElementById("gemini-model");
const sampleMode = document.getElementById("sample-mode");
const resultActions = document.getElementById("result-actions");
const downloadJsonBtn = document.getElementById("download-json");
const downloadTxtBtn = document.getElementById("download-txt");
const copyPromptsBtn = document.getElementById("copy-prompts");

let selectedFiles = [];
let currentJobId = null;
let currentOutput = null;
let currentFiles = {};
let currentMode = "single";

const configProfiles = {
  fast: {
    settings: {
      sample_mode: "first-n",
      max_duration: 15,
      gemini_model: "gemini-2.5-flash",
      no_cache: true,
    },
  },
  quality: {
    settings: {
      sample_mode: "full",
      max_duration: null,
      gemini_model: "gemini-2.5-pro",
      no_cache: false,
    },
  },
  cheap: {
    settings: {
      sample_mode: "highlights",
      max_duration: 10,
      gemini_model: "gemini-2.5-flash",
      no_cache: true,
    },
  },
};

function log(message) {
  const p = document.createElement("p");
  p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  statusLog.appendChild(p);
  statusLog.scrollTop = statusLog.scrollHeight;
}

function resetUploadProgress() {
  const uploadProgress = document.getElementById("upload-progress");
  const progressBar = document.getElementById("upload-progress-bar");
  const etaEl = document.getElementById("upload-eta");
  const percentageEl = document.getElementById("upload-percentage");
  uploadProgress.classList.add("hidden");
  progressBar.style.width = "0%";
  progressBar.textContent = "0%";
  percentageEl.textContent = "0%";
  etaEl.textContent = "ETA: --";
}

function updateUploadProgress(percentage) {
  const uploadProgress = document.getElementById("upload-progress");
  const progressBar = document.getElementById("upload-progress-bar");
  const percentageEl = document.getElementById("upload-percentage");
  uploadProgress.classList.remove("hidden");
  progressBar.style.width = `${percentage}%`;
  progressBar.textContent = `${percentage}%`;
  percentageEl.textContent = `${percentage}%`;
}

function setStepState(stepId, state) {
  const li = document.querySelector(`#steps li[data-step="${stepId}"]`);
  if (!li) return;
  li.classList.remove("running", "done", "error", "pending");
  li.classList.add(state);
  const icon = li.querySelector(".step-icon");
  if (state === "running") icon.textContent = "o";
  else if (state === "done") icon.textContent = "v";
  else if (state === "error") icon.textContent = "x";
  else icon.textContent = "o";
}

function resetSteps() {
  document.querySelectorAll("#steps li").forEach((li) => {
    li.classList.remove("running", "done", "error");
    li.querySelector(".step-icon").textContent = "o";
  });
  statusLog.innerHTML = "";
}

function setFiles(files) {
  selectedFiles = files;
  currentMode = selectedFiles.length > 1 ? "batch" : "single";
  fileNameEl.textContent = selectedFiles.length === 1 ? selectedFiles[0].name : `${selectedFiles.length} files selected`;
  fileListEl.innerHTML = "";
  if (selectedFiles.length > 1) {
    fileListEl.classList.remove("hidden");
    selectedFiles.forEach((file) => {
      const item = document.createElement("li");
      item.textContent = file.name;
      fileListEl.appendChild(item);
    });
  } else {
    fileListEl.classList.add("hidden");
  }
  runBtn.disabled = selectedFiles.length === 0;
  runBtn.textContent = currentMode === "batch" ? `Start batch (${selectedFiles.length})` : "Start analysis";
}

function openPicker() {
  videoInput.click();
}

dropZone.addEventListener("click", openPicker);
dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    openPicker();
  }
});

videoInput.addEventListener("change", () => {
  setFiles(Array.from(videoInput.files || []));
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
  });
});

dropZone.addEventListener("drop", (e) => {
  setFiles(Array.from(e.dataTransfer.files || []));
});

document.getElementById("config-profile").addEventListener("change", (e) => {
  const profile = e.target.value;
  const editable = profile === "custom";
  if (!editable) {
    const settings = configProfiles[profile].settings;
    document.getElementById("sample-mode").value = settings.sample_mode;
    document.getElementById("max-duration").value = settings.max_duration ?? "";
    document.getElementById("gemini-model").value = settings.gemini_model;
    document.getElementById("no-cache").checked = settings.no_cache;
  }
  document.getElementById("sample-mode").disabled = !editable;
  document.getElementById("max-duration").disabled = !editable;
  document.getElementById("gemini-model").disabled = !editable;
  document.getElementById("no-cache").disabled = !editable;
});

document.getElementById("save-profile").addEventListener("click", () => {
  const select = document.getElementById("config-profile");
  if (select.value !== "custom") {
    window.alert("Switch to Custom Settings before saving a profile.");
    return;
  }
  const profileName = window.prompt("Enter a name for this profile:");
  if (!profileName) return;
  const key = profileName.toLowerCase().replace(/\s+/g, "_");
  configProfiles[key] = {
    settings: {
      sample_mode: document.getElementById("sample-mode").value,
      max_duration: document.getElementById("max-duration").value || null,
      gemini_model: document.getElementById("gemini-model").value,
      no_cache: document.getElementById("no-cache").checked,
    },
  };
  const option = document.createElement("option");
  option.value = key;
  option.textContent = profileName;
  select.appendChild(option);
  select.value = key;
});

async function loadConfig() {
  const [health, config] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch("/api/config").then((r) => r.json()),
  ]);

  envBadge.textContent = health.gemini_configured ? `Ready - ${health.environment}` : "Missing GEMINI_API_KEY";
  envBadge.className = `badge ${health.gemini_configured ? "ok" : "warn"}`;

  config.models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.label;
    modelsSelect.appendChild(option);
  });

  config.gemini_models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    if (model === "gemini-2.5-flash") option.selected = true;
    geminiModel.appendChild(option);
  });
}

function showErrorDetails(errorDetails) {
  const modal = document.createElement("div");
  modal.className = "error-modal-backdrop";
  modal.innerHTML = `
    <div class="error-modal">
      <div class="error-modal-header">
        <h3>${errorDetails.code || "Error"}</h3>
        <button class="error-modal-close" type="button">&times;</button>
      </div>
      <div class="error-modal-body">
        <p><strong>Message:</strong> ${errorDetails.message || "Unknown error"}</p>
        ${errorDetails.details ? `<p><strong>Details:</strong> ${errorDetails.details}</p>` : ""}
        ${errorDetails.troubleshooting ? `
          <div class="error-troubleshooting">
            <h4>How to fix</h4>
            <ol>${(errorDetails.troubleshooting.steps || []).map((step) => `<li>${step}</li>`).join("")}</ol>
          </div>
        ` : ""}
      </div>
    </div>
  `;
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.classList.contains("error-modal-close")) {
      modal.remove();
    }
  });
  document.body.appendChild(modal);
}

function friendlyError(message) {
  if (!message) return "Unknown error";
  if (message.includes("503") || message.toLowerCase().includes("unavailable")) {
    return "Gemini is temporarily overloaded. Retries were attempted; try again later or keep fallback enabled.";
  }
  if (message.includes("GEMINI_API_KEY")) {
    return "Missing API key. Add GEMINI_API_KEY to your .env file.";
  }
  return message;
}

function collectPromptText(prompts) {
  return Object.values(prompts || {})
    .map((model) => {
      const lines = (model.shots || []).map((shot) => shot.prompt).join("\n\n");
      return `${model.label}\n${lines}`.trim();
    })
    .join("\n\n");
}

function updateActionButtons() {
  const hasJson = Boolean(currentJobId && currentFiles.json);
  const hasTxt = Boolean(currentJobId && currentFiles.txt);
  const hasPrompts = Boolean(currentOutput && currentOutput.prompts);
  resultActions.classList.toggle("hidden", !hasJson && !hasTxt && !hasPrompts);
  downloadJsonBtn.disabled = !hasJson;
  downloadTxtBtn.disabled = !hasTxt;
  copyPromptsBtn.disabled = !hasPrompts;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showResults(output, meta = {}) {
  currentOutput = output;
  currentFiles = meta.files || currentFiles || {};
  resultsSection.classList.remove("hidden");

  const blueprint = output?.blueprint || {};
  const shots = blueprint.chronological_shots || [];
  const prompts = output?.prompts || {};
  const aesthetic = blueprint.global_aesthetic || {};
  const vm = output?.video_metadata || {};

  document.getElementById("summary").innerHTML = `
    <div class="stat"><strong>${shots.length}</strong><span>Shots detected</span></div>
    <div class="stat"><strong>${Object.keys(prompts).length}</strong><span>Model prompts</span></div>
    <div class="stat"><strong>${vm.duration_seconds ?? "?"}s</strong><span>Video length</span></div>
    <div class="stat"><strong>${meta.fallback ? "Yes" : "No"}</strong><span>Fallback used</span></div>
  `;

  const blueprintPanel = document.getElementById("tab-blueprint");
  blueprintPanel.innerHTML = `
    <p><strong>Style:</strong> ${aesthetic.art_style || "-"}</p>
    <p><strong>Lighting:</strong> ${aesthetic.lighting_setup || "-"}</p>
    <p><strong>Color:</strong> ${aesthetic.color_grading || "-"}</p>
  `;
  shots.forEach((shot, index) => {
    const card = document.createElement("div");
    card.className = "shot-card";
    card.innerHTML = `
      <h4>Shot ${index + 1} (${shot.duration_seconds ?? "?"}s)</h4>
      <p><strong>Camera:</strong> ${shot.camera_direction || "-"}</p>
      <p><strong>Action:</strong> ${shot.action_and_motion || "-"}</p>
      <p><strong>Setting:</strong> ${shot.environment_context || "-"}</p>
    `;
    blueprintPanel.appendChild(card);
  });

  const promptsPanel = document.getElementById("tab-prompts");
  promptsPanel.innerHTML = "";
  Object.values(prompts).forEach((model) => {
    const block = document.createElement("div");
    block.className = "prompt-block";
    const lines = (model.shots || []).map((shot) => shot.prompt).join("\n\n");
    block.innerHTML = `<h4>${model.label}</h4><pre>${escapeHtml(lines)}</pre>`;
    promptsPanel.appendChild(block);
  });

  document.getElementById("tab-raw").textContent = JSON.stringify(output, null, 2);

  if (meta.files) {
    log(`Saved: ${Object.values(meta.files).join(", ")}`);
  }
  updateActionButtons();
}

function showBatchSummary(result) {
  resultsSection.classList.remove("hidden");
  currentOutput = null;
  currentFiles = {};
  document.getElementById("summary").innerHTML = `
    <div class="stat"><strong>${result.completed}</strong><span>Completed</span></div>
    <div class="stat"><strong>${result.failed}</strong><span>Failed</span></div>
    <div class="stat"><strong>${result.total_files}</strong><span>Total files</span></div>
  `;
  document.getElementById("tab-blueprint").innerHTML = result.items
    .map((item) => `<div class="shot-card"><h4>${item.filename}</h4><p>Status: ${item.status}</p>${item.error ? `<p>${item.error}</p>` : ""}</div>`)
    .join("");
  document.getElementById("tab-prompts").innerHTML = "";
  document.getElementById("tab-raw").textContent = JSON.stringify(result, null, 2);
  updateActionButtons();
}

function handleProgress(data) {
  if (data.event === "step" && data.step && data.status) {
    if (data.status === "running") setStepState(data.step, "running");
    if (data.status === "done") setStepState(data.step, "done");
    if (data.message) log(`${data.filename ? `[${data.filename}] ` : ""}${data.step}: ${data.message}`);
  }

  if (data.event === "retry") {
    log(`${data.filename ? `[${data.filename}] ` : ""}${data.message || `Retrying ${data.step}`}`);
    if (data.detail) log(`Detail: ${data.detail}`);
  }

  if (data.event === "fallback") {
    log(`${data.filename ? `[${data.filename}] ` : ""}${data.message || "Using fallback blueprint"}`);
    if (data.detail) log(`Reason: ${data.detail}`);
  }

  if (data.event === "batch_started" || data.event === "batch_item") {
    log(data.message);
  }

  if (data.event === "pipeline_start") {
    log(data.filename ? `Pipeline started: ${data.filename}` : "Pipeline started");
  }

  if (data.event === "pipeline_complete") {
    currentFiles = data.files || {};
    if (currentMode === "single") {
      log(data.fallback ? "Pipeline complete (fallback blueprint)" : "Pipeline complete");
      showResults(data.output, data);
    } else if (data.filename) {
      log(`Completed output for ${data.filename}`);
    }
  }

  if (data.event === "batch_complete") {
    log(data.message);
    showBatchSummary(data.result);
  }

  if (data.event === "pipeline_error") {
    if (data.message && typeof data.message === "object") {
      log(`Error: ${data.message.code}: ${data.message.message}`);
      showErrorDetails(data.message);
    } else {
      log(`Error: ${friendlyError(String(data.message || ""))}`);
    }
    document.querySelectorAll("#steps li.running").forEach((li) => {
      setStepState(li.dataset.step, "error");
    });
  }
}

function buildFormData(files) {
  const form = new FormData();
  const fieldName = files.length > 1 ? "videos" : "video";
  files.forEach((file) => form.append(fieldName, file));
  form.append("sample_mode", sampleMode.value);
  form.append("gemini_model", geminiModel.value);
  if (document.getElementById("dry-run").checked) form.append("dry_run", "true");
  if (document.getElementById("use-fallback").checked) form.append("use_fallback", "true");
  if (document.getElementById("no-cache").checked) form.append("no_cache", "true");
  if (document.getElementById("no-transcribe").checked) form.append("no_transcribe", "true");

  const maxDuration = document.getElementById("max-duration").value;
  if (maxDuration) form.append("max_duration", maxDuration);

  const selectedModels = [...modelsSelect.selectedOptions].map((option) => option.value);
  if (selectedModels.length) form.append("models", selectedModels.join(","));
  return form;
}

async function startJob() {
  if (!selectedFiles.length) return;

  runBtn.disabled = true;
  resetSteps();
  resetUploadProgress();
  resultsSection.classList.add("hidden");
  currentOutput = null;
  currentFiles = {};
  currentJobId = null;
  updateActionButtons();

  const form = buildFormData(selectedFiles);
  const endpoint = selectedFiles.length > 1 ? "/api/run-batch" : "/api/run";

  try {
    updateUploadProgress(15);
    const response = await fetch(endpoint, { method: "POST", body: form });
    updateUploadProgress(100);
    const data = await response.json();
    if (!response.ok) {
      log(data.error || "Failed to start");
      if (data.error_details) showErrorDetails(data.error_details);
      runBtn.disabled = false;
      return;
    }

    currentJobId = data.job_id;
    if (selectedFiles.length > 1) {
      log(`Batch job ${data.job_id} - ${data.count} files`);
    } else {
      log(`Job ${data.job_id} - ${data.filename}`);
    }

    const events = new EventSource(`/api/jobs/${data.job_id}/stream`);
    events.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.event === "stream_end") {
        events.close();
        runBtn.disabled = false;
        if (payload.status === "error" && currentMode === "batch") {
          log("Batch finished with some failures.");
        }
        return;
      }
      handleProgress(payload);
    };
    events.onerror = () => {
      events.close();
      runBtn.disabled = false;
      log("Connection lost. Check server logs.");
    };
  } catch (error) {
    log(String(error));
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", startJob);

downloadJsonBtn.addEventListener("click", () => {
  if (currentJobId && currentFiles.json) {
    window.location.href = `/api/jobs/${currentJobId}/download/json`;
  }
});

downloadTxtBtn.addEventListener("click", () => {
  if (currentJobId && currentFiles.txt) {
    window.location.href = `/api/jobs/${currentJobId}/download/txt`;
  }
});

copyPromptsBtn.addEventListener("click", async () => {
  if (!currentOutput?.prompts) return;
  await navigator.clipboard.writeText(collectPromptText(currentOutput.prompts));
  log("Copied prompts to clipboard");
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    button.classList.add("active");
    const active = button.dataset.tab;
    ["blueprint", "prompts", "raw"].forEach((name) => {
      document.getElementById(`tab-${name}`).classList.toggle("hidden", name !== active);
    });
  });
});

loadConfig().catch(() => {
  envBadge.textContent = "Cannot reach server";
  envBadge.className = "badge warn";
});
