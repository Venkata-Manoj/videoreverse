const dropZone = document.getElementById("drop-zone");
const videoInput = document.getElementById("video-input");
const fileNameEl = document.getElementById("file-name");
const fileListEl = document.getElementById("file-list");
const runBtn = document.getElementById("run-btn");
const statusLog = document.getElementById("status-log");
const resultsSection = document.getElementById("results-section");
const envBadge = document.getElementById("env-badge");
const modelGrid = document.getElementById("model-grid");
const modelSearch = document.getElementById("model-search");
const modelCount = document.getElementById("model-count");
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
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = model.id;
    cb.dataset.label = model.label;
    cb.addEventListener("change", updateModelCount);
    label.appendChild(cb);
    label.appendChild(document.createTextNode(model.label));
    modelGrid.appendChild(label);
  });
  updateModelCount();

  config.gemini_models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    if (model === "gemini-2.5-flash") option.selected = true;
    geminiModel.appendChild(option);
  });

  document.getElementById("select-all-models").addEventListener("click", () => {
    modelGrid.querySelectorAll("input[type=checkbox]").forEach((cb) => {
      cb.checked = true;
      cb.closest("label").classList.remove("filtered-hidden");
    });
    if (modelSearch) modelSearch.value = "";
    updateModelCount();
  });

  document.getElementById("deselect-all-models").addEventListener("click", () => {
    modelGrid.querySelectorAll("input[type=checkbox]:checked").forEach((cb) => { cb.checked = false; });
    updateModelCount();
  });

  modelSearch.addEventListener("input", () => {
    const q = modelSearch.value.toLowerCase();
    modelGrid.querySelectorAll("label").forEach((label) => {
      const text = label.textContent.toLowerCase();
      label.classList.toggle("filtered-hidden", q && !text.includes(q));
    });
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

  if (appWorker) {
    formatWithWorker(output);
  } else {
    document.getElementById("tab-raw").textContent = JSON.stringify(output, null, 2);
  }

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

function collectSelectedModels() {
  return [...modelGrid.querySelectorAll("input[type=checkbox]:checked")].map((cb) => cb.value);
}

function updateModelCount() {
  const all = modelGrid.querySelectorAll("input[type=checkbox]").length;
  const checked = collectSelectedModels().length;
  modelCount.textContent = `${checked} of ${all} selected`;
  const chips = document.getElementById("model-chips");
  chips.innerHTML = collectSelectedModels().map((id) => {
    const cb = modelGrid.querySelector(`input[value="${id}"]`);
    const label = cb ? cb.dataset.label || id : id;
    return `<span class="model-chip">${label} <span class="remove" data-model="${id}">&times;</span></span>`;
  }).join("");
  chips.querySelectorAll(".remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cb = modelGrid.querySelector(`input[value="${btn.dataset.model}"]`);
      if (cb) { cb.checked = false; updateModelCount(); }
    });
  });
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
  if (document.getElementById("aggressive-blur").checked) form.append("aggressive_blur_filter", "true");

  const maxDuration = document.getElementById("max-duration").value;
  if (maxDuration) form.append("max_duration", maxDuration);

  const blurThreshold = document.getElementById("blur-threshold").value;
  if (blurThreshold && parseInt(blurThreshold) !== 100) form.append("blur_threshold", blurThreshold);

  const selectedModels = collectSelectedModels();
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

/* =========================================
   URL Input
   ========================================= */

const urlInput = document.getElementById("video-url");
const urlRunBtn = document.getElementById("url-run-btn");

async function startUrlJob() {
  const url = urlInput.value.trim();
  if (!url) {
    log("Please enter a video URL");
    return;
  }

  urlRunBtn.disabled = true;
  resetSteps();
  resultsSection.classList.add("hidden");
  currentOutput = null;
  currentFiles = {};
  currentJobId = null;
  updateActionButtons();

  const form = new FormData();
  form.append("url", url);
  form.append("sample_mode", sampleMode.value);
  form.append("gemini_model", geminiModel.value);
  if (document.getElementById("dry-run").checked) form.append("dry_run", "true");
  if (document.getElementById("use-fallback").checked) form.append("use_fallback", "true");
  if (document.getElementById("no-cache").checked) form.append("no_cache", "true");
  if (document.getElementById("no-transcribe").checked) form.append("no_transcribe", "true");
  if (document.getElementById("aggressive-blur").checked) form.append("aggressive_blur_filter", "true");

  const maxDuration = document.getElementById("max-duration").value;
  if (maxDuration) form.append("max_duration", maxDuration);

  const blurThreshold = document.getElementById("blur-threshold").value;
  if (blurThreshold && parseInt(blurThreshold) !== 100) form.append("blur_threshold", blurThreshold);

  const selectedModels = collectSelectedModels();
  if (selectedModels.length) form.append("models", selectedModels.join(","));

  try {
    log(`Downloading from URL: ${url}`);
    const response = await fetch("/api/run-url", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok) {
      log(data.error || "Failed to start URL job");
      urlRunBtn.disabled = false;
      return;
    }

    currentJobId = data.job_id;
    log(`Job ${data.job_id} - ${data.filename}`);

    const events = new EventSource(`/api/jobs/${data.job_id}/stream`);
    events.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.event === "stream_end") {
        events.close();
        urlRunBtn.disabled = false;
        return;
      }
      handleProgress(payload);
    };
    events.onerror = () => {
      events.close();
      urlRunBtn.disabled = false;
      log("Connection lost. Check server logs.");
    };
  } catch (err) {
    log(String(err));
    urlRunBtn.disabled = false;
  }
}

urlRunBtn.addEventListener("click", startUrlJob);
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") startUrlJob();
});

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

/* =========================================
   Web Worker
   ========================================= */

let appWorker = null;

function initWorker() {
  try {
    appWorker = new Worker("/static/app.worker.js");
    appWorker.onerror = () => { appWorker = null; };
    appWorker.onmessage = (e) => {
      const { type, data } = e.data;
      if (type === "formattedJson" && document.getElementById("tab-raw")) {
        document.getElementById("tab-raw").textContent = data;
      }
    };
  } catch {
    appWorker = null;
  }
}

function formatWithWorker(json) {
  if (appWorker) {
    appWorker.postMessage({ type: "formatJson", data: json });
  }
}

initWorker();

loadConfig().catch(() => {
  envBadge.textContent = "Cannot reach server";
  envBadge.className = "badge warn";
});

/* =========================================
   Job History (localStorage)
   ========================================= */

const HISTORY_KEY = "vidrev_job_history";
const MAX_HISTORY = 50;

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveToHistory(entry) {
  const history = getHistory();
  entry.timestamp = new Date().toISOString();
  history.unshift(entry);
  if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  renderHistory();
}

function addJobToHistory(jobId, filename, options, output, files) {
  const entry = {
    jobId,
    filename,
    options: { ...options },
    output: output || null,
    files: files || {},
    shots: output?.blueprint?.chronological_shots?.length || 0,
    models: output?.prompts ? Object.keys(output.prompts).length : 0,
    duration_s: output?.video_metadata?.duration_seconds || null,
    fallback: output?._meta?.fallback_active || false,
  };
  saveToHistory(entry);
}

function renderHistory() {
  const history = getHistory();
  const listEl = document.getElementById("history-list");
  const countEl = document.getElementById("history-count");
  if (!listEl) return;
  if (countEl) countEl.textContent = `${history.length} job${history.length !== 1 ? "s" : ""}`;

  if (history.length === 0) {
    listEl.innerHTML = '<p class="history-empty">No previous jobs. Run an analysis and it will appear here.</p>';
    return;
  }

  listEl.innerHTML = history
    .map((entry, idx) => {
      const time = new Date(entry.timestamp).toLocaleString();
      const meta = [
        time,
        entry.shots ? `${entry.shots} shots` : null,
        entry.models ? `${entry.models} models` : null,
        entry.fallback ? "fallback" : null,
      ]
        .filter(Boolean)
        .join(" · ");
      return `
      <div class="history-item" role="listitem" data-index="${idx}" tabindex="0">
        <div class="history-item-info">
          <span class="history-item-filename">${escapeHtml(entry.filename)}</span>
          <span class="history-item-meta">${escapeHtml(meta)}</span>
        </div>
        <div class="history-item-actions">
          <button class="btn small secondary history-rerun" data-index="${idx}" type="button" title="Re-run with same settings">⟳</button>
          <button class="btn small secondary history-compare" data-index="${idx}" type="button" title="Select for comparison">⇄</button>
        </div>
      </div>`;
    })
    .join("");

  listEl.querySelectorAll(".history-rerun").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.index, 10);
      rerunHistoryJob(idx);
    });
  });

  listEl.querySelectorAll(".history-compare").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.index, 10);
      toggleCompareSelection(idx);
    });
  });
}

function rerunHistoryJob(index) {
  const history = getHistory();
  const entry = history[index];
  if (!entry) return;

  const opts = entry.options || {};
  if (opts.sample_mode) sampleMode.value = opts.sample_mode;
  if (opts.gemini_model) geminiModel.value = opts.gemini_model;
  if (opts.max_duration) document.getElementById("max-duration").value = opts.max_duration;
  if (opts.no_cache) document.getElementById("no-cache").checked = true;
  if (opts.no_transcribe) document.getElementById("no-transcribe").checked = true;
  if (opts.blur_threshold) document.getElementById("blur-threshold").value = opts.blur_threshold;
  if (opts.aggressive_blur_filter) document.getElementById("aggressive-blur").checked = true;

  if (opts.models && Array.isArray(opts.models)) {
    modelGrid.querySelectorAll("input[type=checkbox]").forEach((cb) => {
      cb.checked = opts.models.includes(cb.value);
    });
    updateModelCount();
  }

  selectedFiles = [];
  currentMode = "single";
  fileNameEl.textContent = entry.filename + " (file not loaded — re-upload required)";
  runBtn.disabled = true;
  log(`Settings loaded from history: ${entry.filename}`);
}

document.getElementById("clear-history-btn")?.addEventListener("click", () => {
  if (confirm("Clear all job history? This cannot be undone.")) {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
    log("Job history cleared");
  }
});

/* =========================================
   Comparison Tool
   ========================================= */

let compareSelection = [];

function toggleCompareSelection(index) {
  const history = getHistory();
  if (index < 0 || index >= history.length) return;

  const itemEl = document.querySelector(`.history-item[data-index="${index}"]`);
  if (!itemEl) return;

  if (compareSelection.includes(index)) {
    compareSelection = compareSelection.filter((i) => i !== index);
    itemEl.classList.remove("selected");
  } else {
    if (compareSelection.length >= 2) {
      const oldIdx = compareSelection.shift();
      const oldEl = document.querySelector(`.history-item[data-index="${oldIdx}"]`);
      if (oldEl) oldEl.classList.remove("selected");
    }
    compareSelection.push(index);
    itemEl.classList.add("selected");
  }

  if (compareSelection.length === 2) {
    openComparison(compareSelection[0], compareSelection[1]);
  }
}

function openComparison(leftIdx, rightIdx) {
  const history = getHistory();
  const left = history[leftIdx];
  const right = history[rightIdx];
  if (!left || !right) return;

  const modal = document.getElementById("compare-modal");
  const leftSelect = document.getElementById("compare-left-select");
  const rightSelect = document.getElementById("compare-right-select");

  function populateSelect(select, history, selectedIdx) {
    select.innerHTML = history
      .map((h, i) => `<option value="${i}" ${i === selectedIdx ? "selected" : ""}>${escapeHtml(h.filename)}</option>`)
      .join("");
  }

  populateSelect(leftSelect, history, leftIdx);
  populateSelect(rightSelect, history, rightIdx);

  modal.classList.remove("hidden");
  renderComparison();
}

function renderComparison() {
  const leftIdx = parseInt(document.getElementById("compare-left-select").value, 10);
  const rightIdx = parseInt(document.getElementById("compare-right-select").value, 10);
  const history = getHistory();
  const left = history[leftIdx];
  const right = history[rightIdx];
  if (!left || !right) return;

  const outputDiv = document.getElementById("compare-output");
  outputDiv.classList.remove("hidden");

  function buildBlueprintColumn(data) {
    if (!data?.blueprint) return "<p>No blueprint data</p>";
    const b = data.blueprint;
    const aesthetic = b.global_aesthetic || {};
    const shots = b.chronological_shots || [];
    return `
      <p><strong>Style:</strong> ${aesthetic.art_style || "-"}</p>
      <p><strong>Lighting:</strong> ${aesthetic.lighting_setup || "-"}</p>
      <p><strong>Color:</strong> ${aesthetic.color_grading || "-"}</p>
      <p><strong>Shots:</strong> ${shots.length}</p>
      ${shots
        .map(
          (s, i) => `
        <div style="margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid var(--border)">
          <strong>Shot ${i + 1}</strong> (${s.duration_seconds ?? "?"}s)<br>
          Camera: ${s.camera_direction || "-"}<br>
          Action: ${s.action_and_motion || "-"}<br>
          Setting: ${s.environment_context || "-"}
        </div>`
        )
        .join("")}
    `;
  }

  function buildPromptsColumn(data) {
    if (!data?.prompts) return "<p>No prompt data</p>";
    const prompts = data.prompts;
    return Object.values(prompts)
      .map((model) => {
        const lines = (model.shots || []).map((shot) => shot.prompt).join("\n\n");
        return `<h4 style="margin:0.5rem 0 0.25rem">${escapeHtml(model.label)}</h4><pre>${escapeHtml(lines || "—")}</pre>`;
      })
      .join("");
  }

  document.getElementById("compare-blueprint").innerHTML = `
    <div class="compare-column">
      <h4>${escapeHtml(left.filename)}</h4>
      ${buildBlueprintColumn(left.output || {})}
    </div>
    <div class="compare-column">
      <h4>${escapeHtml(right.filename)}</h4>
      ${buildBlueprintColumn(right.output || {})}
    </div>`;

  document.getElementById("compare-prompts").innerHTML = `
    <div class="compare-column">
      <h4>${escapeHtml(left.filename)}</h4>
      ${buildPromptsColumn(left.output || {})}
    </div>
    <div class="compare-column">
      <h4>${escapeHtml(right.filename)}</h4>
      ${buildPromptsColumn(right.output || {})}
    </div>`;
}

document.getElementById("compare-left-select")?.addEventListener("change", renderComparison);
document.getElementById("compare-right-select")?.addEventListener("change", renderComparison);
document.getElementById("compare-btn")?.addEventListener("click", renderComparison);

document.querySelectorAll(".compare-close").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.getElementById("compare-modal").classList.add("hidden");
    document.querySelectorAll(".history-item.selected").forEach((el) => el.classList.remove("selected"));
    compareSelection = [];
  });
});

document.querySelectorAll("[data-compare-tab]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-compare-tab]").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.compareTab;
    document.getElementById("compare-blueprint").classList.toggle("hidden", target !== "blueprint");
    document.getElementById("compare-prompts").classList.toggle("hidden", target !== "prompts");
  });
});

/* =========================================
   Template Editor
   ========================================= */

let templateCache = {};

async function loadTemplateEditor() {
  try {
    const res = await fetch("/api/templates");
    const data = await res.json();
    templateCache = data.templates || {};
    const select = document.getElementById("template-model-select");
    select.innerHTML = (data.models || [])
      .map((m) => `<option value="${m}">${escapeHtml(templateCache[m]?.label || m)}</option>`)
      .join("");
    select.value = data.models[0] || "";
    loadTemplateField();
  } catch (err) {
    console.error("Failed to load templates:", err);
  }
}

function loadTemplateField() {
  const modelId = document.getElementById("template-model-select").value;
  const field = document.getElementById("template-field-select").value;
  const textarea = document.getElementById("template-editor-textarea");
  const statusEl = document.getElementById("template-status");

  const model = templateCache[modelId];
  if (!model) {
    textarea.value = "// No template data available";
    textarea.disabled = true;
    return;
  }

  textarea.disabled = false;
  statusEl.textContent = "";
  statusEl.className = "template-status";

  if (field === "enhancement_rules") {
    textarea.value = JSON.stringify(model.enhancement_rules || {}, null, 2);
  } else {
    textarea.value = model[field] || "";
  }
}

document.getElementById("template-model-select")?.addEventListener("change", loadTemplateField);
document.getElementById("template-field-select")?.addEventListener("change", loadTemplateField);

document.getElementById("template-save-btn")?.addEventListener("click", async () => {
  const modelId = document.getElementById("template-model-select").value;
  const field = document.getElementById("template-field-select").value;
  const textarea = document.getElementById("template-editor-textarea");
  const statusEl = document.getElementById("template-status");

  let value = textarea.value;
  if (field === "enhancement_rules") {
    try {
      value = JSON.parse(value);
    } catch {
      statusEl.textContent = "Invalid JSON for enhancement rules";
      statusEl.className = "template-status error";
      return;
    }
  }

  try {
    const body = { [field]: value };
    const res = await fetch(`/api/templates/${modelId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      statusEl.textContent = err.error || "Save failed";
      statusEl.className = "template-status error";
      return;
    }
    statusEl.textContent = "Saved successfully";
    statusEl.className = "template-status saved";
    templateCache[modelId][field] = value;
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
    statusEl.className = "template-status error";
  }
});

document.getElementById("template-reset-btn")?.addEventListener("click", () => {
  loadTemplateField();
  document.getElementById("template-status").textContent = "";
  document.getElementById("template-status").className = "template-status";
});

/* Open template editor from header or elsewhere */
document.querySelectorAll("[data-open-template-editor]").forEach((el) => {
  el.addEventListener("click", () => {
    document.getElementById("template-modal").classList.remove("hidden");
    loadTemplateEditor();
  });
});

document.querySelectorAll(".template-close").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.getElementById("template-modal").classList.add("hidden");
  });
});

/* =========================================
   Monitoring Dashboard
   ========================================= */

async function loadMonitoring() {
  const grid = document.getElementById("monitoring-grid");
  if (!grid) return;

  try {
    const res = await fetch("/api/monitoring");
    const data = await res.json();

    document.getElementById("monitor-total-runs").textContent = data.total_pipeline_runs;
    document.getElementById("monitor-success-rate").textContent = `${data.success_rate}%`;
    document.getElementById("monitor-fallback-rate").textContent = `${data.fallback_rate}%`;
    document.getElementById("monitor-cache-rate").textContent = `${data.cache_hit_rate}%`;
    document.getElementById("monitor-total-retries").textContent = data.total_retries;
    document.getElementById("monitor-output-files").textContent = data.output_files;
    document.getElementById("monitor-output-size").textContent = `${data.output_size_mb} MB`;
    document.getElementById("monitor-active-jobs").textContent = data.hub_jobs;

    const timingDiv = document.getElementById("monitor-timing");
    const timingGrid = document.getElementById("monitor-timing-grid");
    const avg = data.average_timing_ms || {};

    if (Object.keys(avg).length > 0) {
      timingDiv.classList.remove("hidden");
      timingGrid.innerHTML = Object.entries(avg)
        .map(([key, val]) => {
          const label = key.replace("_ms", "").replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
          const display = key === "total_ms" && val >= 1000 ? `${(val / 1000).toFixed(1)}s` : `${val}ms`;
          return `<div class="monitor-stat"><strong>${display}</strong><span>${escapeHtml(label)}</span></div>`;
        })
        .join("");
    } else {
      timingDiv.classList.add("hidden");
    }

    const recentDiv = document.getElementById("monitor-recent");
    const recentTable = document.getElementById("monitor-recent-table");
    const runs = data.recent_runs || [];
    if (runs.length > 0) {
      recentDiv.classList.remove("hidden");
      recentTable.innerHTML = `<table class="monitor-table">
        <thead><tr><th>Time</th><th>Video</th><th>Type</th><th>Dur</th><th>Models</th><th>FB</th><th>Cache</th></tr></thead>
        <tbody>${runs.map(r => {
          const ts = (r.timestamp || "").slice(0, 19).replace("T", " ");
          const vid = (r.video_path || "").split("/").pop() || "-";
          const dur = r.total_ms ? (r.total_ms >= 1000 ? `${(r.total_ms/1000).toFixed(1)}s` : `${r.total_ms}ms`) : "-";
          return `<tr class="${r.success ? "" : "error-row"}">
            <td>${escapeHtml(ts)}</td>
            <td title="${escapeHtml(r.video_path || "")}">${escapeHtml(vid)}</td>
            <td>${escapeHtml(r.video_type || "-")}</td>
            <td>${dur}</td>
            <td>${r.models_compiled ?? "-"}</td>
            <td>${r.fallback_active ? "⚠️" : ""}</td>
            <td>${r.cache_hit ? "✅" : ""}</td>
          </tr>`;
        }).join("")}</tbody></table>`;
    } else {
      recentDiv.classList.add("hidden");
    }
  } catch (err) {
    console.error("Failed to load monitoring data:", err);
  }
}

document.getElementById("refresh-monitor-btn")?.addEventListener("click", loadMonitoring);

/* =========================================
   Extend pipeline complete to save history
   ========================================= */

// Save original handleProgress since we need to extend pipeline_complete
const _origHandleProgress = handleProgress;
handleProgress = function (data) {
  _origHandleProgress(data);

  // Save to history on pipeline complete
  if (data.event === "pipeline_complete" && currentMode === "single" && currentOutput) {
    addJobToHistory(currentJobId, data.filename || "unknown", {
      sample_mode: sampleMode.value,
      gemini_model: geminiModel.value,
      max_duration: document.getElementById("max-duration").value || "",
      no_cache: document.getElementById("no-cache").checked,
      no_transcribe: document.getElementById("no-transcribe").checked,
      blur_threshold: document.getElementById("blur-threshold").value || "",
      aggressive_blur_filter: document.getElementById("aggressive-blur").checked,
      models: collectSelectedModels(),
    }, currentOutput, data.files || {});
  }
};

/* =========================================
   Handle escape key for modals
   ========================================= */

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-backdrop:not(.hidden)").forEach((modal) => {
      modal.classList.add("hidden");
    });
    document.querySelectorAll(".history-item.selected").forEach((el) => el.classList.remove("selected"));
    compareSelection = [];
  }
});

/* =========================================
   Close modals on backdrop click
   ========================================= */

document.querySelectorAll(".modal-backdrop").forEach((modal) => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
      document.querySelectorAll(".history-item.selected").forEach((el) => el.classList.remove("selected"));
      compareSelection = [];
    }
  });
});

/* =========================================
   Initialization
   ========================================= */

renderHistory();

// Expose template editor open function globally
window.openTemplateEditor = function () {
  document.getElementById("template-modal").classList.remove("hidden");
  loadTemplateEditor();
};

// Add template editor button to header (after env badge)
const headerEl = document.querySelector(".header");
if (headerEl) {
  const editBtn = document.createElement("button");
  editBtn.className = "btn small secondary";
  editBtn.style.marginTop = "0";
  editBtn.textContent = "Templates";
  editBtn.setAttribute("data-open-template-editor", "");
  editBtn.setAttribute("aria-label", "Open template editor");
  headerEl.appendChild(editBtn);
  editBtn.addEventListener("click", () => {
    document.getElementById("template-modal").classList.remove("hidden");
    loadTemplateEditor();
  });
}

// Load monitoring on expand
document.getElementById("monitoring-details")?.addEventListener("toggle", () => {
  if (document.getElementById("monitoring-details").open) {
    loadMonitoring();
  }
});
