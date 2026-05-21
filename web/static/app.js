const dropZone = document.getElementById("drop-zone");
const videoInput = document.getElementById("video-input");
const fileNameEl = document.getElementById("file-name");
const runBtn = document.getElementById("run-btn");
const statusLog = document.getElementById("status-log");
const resultsSection = document.getElementById("results-section");
const envBadge = document.getElementById("env-badge");
const modelsSelect = document.getElementById("models-select");
const geminiModel = document.getElementById("gemini-model");
const sampleMode = document.getElementById("sample-mode");

let selectedFile = null;

function log(message) {
  const p = document.createElement("p");
  p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  statusLog.appendChild(p);
  statusLog.scrollTop = statusLog.scrollHeight;
}

function setStepState(stepId, state) {
  const li = document.querySelector(`#steps li[data-step="${stepId}"]`);
  if (!li) return;
  li.classList.remove("running", "done", "error", "pending");
  li.classList.add(state);
  const icon = li.querySelector(".step-icon");
  if (state === "running") icon.textContent = "◉";
  else if (state === "done") icon.textContent = "✓";
  else if (state === "error") icon.textContent = "✕";
  else icon.textContent = "○";
}

function resetSteps() {
  document.querySelectorAll("#steps li").forEach((li) => {
    li.classList.remove("running", "done", "error");
    li.querySelector(".step-icon").textContent = "○";
  });
  statusLog.innerHTML = "";
}

function setFile(file) {
  selectedFile = file;
  fileNameEl.textContent = file ? file.name : "";
  runBtn.disabled = !file;
}

dropZone.addEventListener("click", () => videoInput.click());
dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    videoInput.click();
  }
});
videoInput.addEventListener("change", () => {
  if (videoInput.files[0]) setFile(videoInput.files[0]);
});

["dragenter", "dragover"].forEach((ev) => {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((ev) => {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
  });
});
dropZone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

async function loadConfig() {
  const [health, config] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch("/api/config").then((r) => r.json()),
  ]);

  envBadge.textContent = health.gemini_configured
    ? `Ready · ${health.environment}`
    : "Missing GEMINI_API_KEY";
  envBadge.className = "badge " + (health.gemini_configured ? "ok" : "warn");

  config.models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.label;
    modelsSelect.appendChild(opt);
  });

  config.gemini_models.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    if (g === "gemini-2.5-flash") opt.selected = true;
    geminiModel.appendChild(opt);
  });
}

function handleProgress(data) {
  if (data.event === "step" && data.step && data.status) {
    if (data.status === "running") setStepState(data.step, "running");
    if (data.status === "done") setStepState(data.step, "done");
    if (data.message) log(`${data.step}: ${data.message}`);
  }
  if (data.event === "retry") {
    log(data.message || `Retrying ${data.step}…`);
  }
  if (data.event === "fallback") {
    log(data.message || "Using fallback blueprint");
  }
  if (data.event === "pipeline_start") {
    log("Pipeline started");
  }
  if (data.event === "pipeline_complete") {
    log(data.fallback ? "Pipeline complete (fallback blueprint — lower quality)" : "Pipeline complete");
    showResults(data.output, data);
  }
  if (data.event === "pipeline_error") {
    const short = friendlyError(data.message);
    log(`Error: ${short}`);
    document.querySelectorAll("#steps li.running").forEach((li) => {
      setStepState(li.dataset.step, "error");
    });
  }
}

function friendlyError(message) {
  if (!message) return "Unknown error";
  if (message.includes("503") || message.toLowerCase().includes("unavailable")) {
    return "Gemini is temporarily overloaded. Retries were attempted; enable fallback or try again in a few minutes.";
  }
  if (message.includes("GEMINI_API_KEY")) {
    return "Missing API key — add GEMINI_API_KEY to your .env file.";
  }
  return message.length > 200 ? message.slice(0, 200) + "…" : message;
}

function showResults(output, meta) {
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

  const bpPanel = document.getElementById("tab-blueprint");
  bpPanel.innerHTML = `
    <p><strong>Style:</strong> ${aesthetic.art_style || "—"}</p>
    <p><strong>Lighting:</strong> ${aesthetic.lighting_setup || "—"}</p>
    <p><strong>Color:</strong> ${aesthetic.color_grading || "—"}</p>
  `;
  shots.forEach((shot, i) => {
    const card = document.createElement("div");
    card.className = "shot-card";
    card.innerHTML = `
      <h4>Shot ${i + 1} (${shot.duration_seconds ?? "?"}s)</h4>
      <p><strong>Camera:</strong> ${shot.camera_direction || "—"}</p>
      <p><strong>Action:</strong> ${shot.action_and_motion || "—"}</p>
      <p><strong>Setting:</strong> ${shot.environment_context || "—"}</p>
    `;
    bpPanel.appendChild(card);
  });

  const prPanel = document.getElementById("tab-prompts");
  prPanel.innerHTML = "";
  Object.entries(prompts).forEach(([, model]) => {
    const block = document.createElement("div");
    block.className = "prompt-block";
    const lines = (model.shots || []).map((s) => s.prompt).join("\n\n");
    block.innerHTML = `<h4>${model.label}</h4><pre>${escapeHtml(lines)}</pre>`;
    prPanel.appendChild(block);
  });

  document.getElementById("tab-raw").textContent = JSON.stringify(output, null, 2);

  if (meta.files) {
    log(`Saved: ${Object.values(meta.files).join(", ")}`);
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    const id = btn.dataset.tab;
    ["blueprint", "prompts", "raw"].forEach((name) => {
      document.getElementById(`tab-${name}`).classList.toggle("hidden", name !== id);
    });
  });
});

runBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  runBtn.disabled = true;
  resetSteps();
  resultsSection.classList.add("hidden");

  const form = new FormData();
  form.append("video", selectedFile);
  form.append("sample_mode", sampleMode.value);
  form.append("gemini_model", geminiModel.value);
  if (document.getElementById("dry-run").checked) form.append("dry_run", "true");
  if (document.getElementById("use-fallback").checked) form.append("use_fallback", "true");

  const maxDur = document.getElementById("max-duration").value;
  if (maxDur) form.append("max_duration", maxDur);

  const selected = [...modelsSelect.selectedOptions].map((o) => o.value);
  if (selected.length) form.append("models", selected.join(","));

  try {
    const startRes = await fetch("/api/run", { method: "POST", body: form });
    const startData = await startRes.json();
    if (!startRes.ok) {
      log(startData.error || "Failed to start");
      runBtn.disabled = false;
      return;
    }

    log(`Job ${startData.job_id} — ${startData.filename}`);

    const es = new EventSource(`/api/jobs/${startData.job_id}/stream`);
    es.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.event === "stream_end") {
        es.close();
        runBtn.disabled = false;
        if (data.status === "error") log("Job finished with errors.");
        return;
      }
      handleProgress(data);
    };
    es.onerror = () => {
      es.close();
      log("Connection lost. Check server logs.");
      runBtn.disabled = false;
    };
  } catch (err) {
    log(String(err));
    runBtn.disabled = false;
  }
});

loadConfig().catch(() => {
  envBadge.textContent = "Cannot reach server";
  envBadge.className = "badge warn";
});
