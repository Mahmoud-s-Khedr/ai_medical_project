(function () {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const TABS = {
    dashboard: { title: "Today's Tasks", subtitle: "Pick a workflow to run an end-to-end demo quickly." },
    ocr: { title: "OCR Scan", subtitle: "Upload package photo and evaluate confidence-driven results." },
    medicines: { title: "Medicine Lookup", subtitle: "Search, inspect details, and evaluate interactions." },
    reminders: { title: "Medication Reminders", subtitle: "Create schedules and log adherence events." },
    medical: { title: "Medical Record", subtitle: "Maintain core profile and clinical history." },
    auth: { title: "Authentication", subtitle: "Manage login and account creation." },
  };

  const state = {
    access: localStorage.getItem("demo_access") || "",
    refresh: localStorage.getItem("demo_refresh") || "",
    user: null,
    lastRefresh: "Never",
    activeTab: "dashboard",
    reminders: [],
    pendingDeleteReminderId: null,
  };

  function showToast(message, type = "success") {
    const toast = $("#toast");
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3200);
  }

  function pretty(data) {
    return JSON.stringify(data, null, 2);
  }

  function parseForm(form) {
    const out = Object.fromEntries(new FormData(form).entries());
    Object.keys(out).forEach((k) => {
      if (out[k] === "") out[k] = null;
    });
    return out;
  }

  function cleanObject(obj) {
    const copy = {};
    Object.entries(obj).forEach(([k, v]) => {
      if (v !== null && v !== "") copy[k] = v;
    });
    return copy;
  }

  function clearFormErrors(formId) {
    const el = $(formId);
    if (el) el.textContent = "";
  }

  function renderFormErrors(formId, payload) {
    const el = $(formId);
    if (!el) return;
    const lines = [];
    Object.entries(payload || {}).forEach(([k, v]) => {
      if (Array.isArray(v)) lines.push(`${k}: ${v.join(", ")}`);
      else if (typeof v === "string") lines.push(`${k}: ${v}`);
    });
    el.textContent = lines.join(" | ");
  }

  function normalizeError(payload) {
    if (!payload) return "Unknown error.";
    if (typeof payload === "string") return payload;
    if (payload.detail) return payload.detail;
    if (payload.error) return payload.error;

    const lines = [];
    Object.entries(payload).forEach(([k, v]) => {
      if (Array.isArray(v)) lines.push(`${k}: ${v.join(", ")}`);
      else if (typeof v === "string") lines.push(`${k}: ${v}`);
    });
    return lines.join(" | ") || "Request failed.";
  }

  function setLoading(target, loading) {
    const el = typeof target === "string" ? $(target) : target;
    if (!el) return;
    el.classList.toggle("loading", loading);
  }

  function placeholderSkeleton(count = 3) {
    return Array.from({ length: count }).map(() => '<div class="skeleton"></div>').join("");
  }

  async function api(path, options = {}, retry = true) {
    const headers = Object.assign({}, options.headers || {});
    const isFormData = options.body instanceof FormData;
    if (!isFormData && !(options.body instanceof Blob) && !(options.body instanceof ArrayBuffer)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    if (state.access) headers.Authorization = `Bearer ${state.access}`;

    const response = await fetch(path, Object.assign({}, options, { headers }));

    if (response.status === 401 && retry && state.refresh) {
      const refreshed = await refreshToken();
      if (refreshed) return api(path, options, false);
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = null;
    }

    if (!response.ok) {
      const error = new Error(normalizeError(payload));
      error.payload = payload;
      error.status = response.status;
      throw error;
    }

    return payload;
  }

  async function refreshToken() {
    try {
      const result = await fetch("/api/auth/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: state.refresh }),
      }).then((res) => res.json());

      if (!result.access) throw new Error("Refresh failed");
      state.access = result.access;
      state.lastRefresh = new Date().toLocaleTimeString();
      localStorage.setItem("demo_access", state.access);
      renderSession();
      return true;
    } catch (_error) {
      clearAuth();
      return false;
    }
  }

  function setAuth(access, refresh) {
    state.access = access;
    state.refresh = refresh;
    localStorage.setItem("demo_access", access || "");
    localStorage.setItem("demo_refresh", refresh || "");
    renderSession();
  }

  function clearAuth() {
    state.access = "";
    state.refresh = "";
    state.user = null;
    localStorage.removeItem("demo_access");
    localStorage.removeItem("demo_refresh");
    $("#meOutput").textContent = "Not loaded.";
    renderSession();
  }

  function renderSession() {
    const label = state.user?.username ? `Signed in: ${state.user.username}` : state.access ? "Authenticated" : "Guest session";
    $("#sessionChip").textContent = label;
    $("#tokenChip").textContent = state.access ? `Token: Active (${state.lastRefresh})` : "Token: Missing";
    $("#readinessList").innerHTML = `
      <li>${state.access ? "Authenticated and ready" : "Sign in before protected workflows"}</li>
      <li>OCR route available at <code>/api/uploads/ocr-search/</code></li>
      <li>Reminders and medical record are user-scoped modules</li>
    `;
  }

  function asList(payload) {
    if (Array.isArray(payload)) return payload;
    return payload?.results || [];
  }

  function activateTab(tabName) {
    state.activeTab = tabName;
    const info = TABS[tabName] || TABS.dashboard;
    $("#contextTitle").textContent = info.title;
    $("#contextSubtitle").textContent = info.subtitle;

    $$(".rail-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabName));
    $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.id === `tab-${tabName}`));

    if (location.hash !== `#${tabName}`) {
      history.replaceState(null, "", `#${tabName}`);
    }
  }

  function initializeFromHash() {
    const tab = location.hash.replace("#", "").trim();
    if (TABS[tab]) activateTab(tab);
  }

  function renderAuthMode(mode) {
    $$(".seg-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.authMode === mode));
    $$(".auth-mode").forEach((panel) => panel.classList.toggle("active", panel.dataset.authPanel === mode));
  }

  function renderOCRSummary(data) {
    const tier = data.match_confidence_tier || "low";
    const confidencePct = Math.round((Number(data.ocr_confidence) || 0) * 100);
    $("#ocrSummary").innerHTML = `
      <div class="stack">
        <div class="metric"><span class="chip">OCR Confidence</span><strong>${confidencePct}%</strong></div>
        <div class="metric"><span class="chip">Processing Time</span><span>${data.processing_time_ms ?? "-"} ms</span></div>
        <div class="metric"><span class="chip">Action</span><span>${data.action_hint || "-"}</span></div>
        <span class="badge ${tier}">Confidence: ${tier}</span>
        ${data.message ? `<div class="empty">${data.message}</div>` : ""}
      </div>
    `;

    const matches = Array.isArray(data.matched_items) ? data.matched_items : [];
    if (!matches.length) {
      $("#ocrMatches").innerHTML = '<div class="empty">No matched medicines.</div>';
      return;
    }

    $("#ocrMatches").innerHTML = matches.map((m) => {
      const score = Math.round((Number(m.score) || 0) * 100);
      const rankScore = Number(m._rank_score);
      const rankLabel = Number.isFinite(rankScore) ? rankScore.toFixed(4) : "N/A";
      return `
        <article class="card">
          <div class="metric"><strong>${m.trade_name || m.name}</strong><span class="badge medium">${score}%</span></div>
          <div class="score"><span style="width:${score}%"></span></div>
          <div>${m.active_ingredient || "N/A"}</div>
          <div>${m.strength || "N/A"} • ${m.dosage_form || "N/A"}</div>
          <div class="metric"><span class="chip">Rank score</span><span>${rankLabel}</span></div>
          <div class="metric"><span class="chip">Matched token</span><span>${m.matched_query || "N/A"}</span></div>
          ${m.id ? `<div class="action-row"><button class="btn ghost" data-ocr-detail="${m.id}" type="button">Show details</button></div>` : ""}
        </article>
      `;
    }).join("");
  }

  function renderMedicineList(items) {
    $("#medicineCountChip").textContent = `${items.length} results`;
    if (!items.length) {
      $("#medicineList").innerHTML = '<div class="empty">No medicines found.</div>';
      return;
    }

    $("#medicineList").innerHTML = items.map((item) => `
      <article class="card">
        <div class="metric">
          <strong>${item.trade_name}</strong>
          <span class="chip">${item.strength || "N/A"}</span>
        </div>
        <div>${item.active_ingredient || "N/A"}</div>
        <div class="action-row">
          <button class="btn ghost" data-med-detail="${item.id}" type="button">Details</button>
          <button class="btn secondary" data-med-interactions="${item.id}" type="button">Interactions</button>
        </div>
      </article>
    `).join("");
  }

  function renderMedicineDetail(medicine, interactions) {
    const conflicts = interactions?.conflicts || [];
    const interactionSection = conflicts.length
      ? conflicts.map((c) => `
          <article class="card">
            <div class="metric">
              <strong>${c.medicine.trade_name}</strong>
              <span class="badge ${c.risk_level === "high" ? "low" : "medium"}">${c.risk_level}</span>
            </div>
            <div>${c.conflict_reason || "No reason provided."}</div>
            <div>Type: ${c.conflict_type || "N/A"}</div>
            <div>Matched ingredient: ${c.matched_ingredient || "N/A"}</div>
          </article>
        `).join("")
      : '<div class="empty">No interactions detected for this medicine.</div>';

    $("#medicineDetailPanel").innerHTML = `
      <article class="card stack">
        <h3>Drug Details</h3>
        <div class="metric"><strong>${medicine.trade_name || "N/A"}</strong><span class="chip">${medicine.strength || "N/A"}</span></div>
        <div><strong>ID:</strong> ${medicine.id ?? "N/A"}</div>
        <div><strong>Active ingredient:</strong> ${medicine.active_ingredient || "N/A"}</div>
        <div><strong>Dosage form:</strong> ${medicine.dosage_form || "N/A"}</div>
        <div><strong>Drug class:</strong> ${medicine.drug_class || "N/A"}</div>
        <div><strong>Common side effects:</strong> ${medicine.common_side_effects || "N/A"}</div>
        <div><strong>Serious warning:</strong> ${medicine.serious_warning || "N/A"}</div>
        <div><strong>Similar active ingredients:</strong> ${medicine.similar_active_ingredients || "N/A"}</div>
        <div><strong>Similarity risk symptoms:</strong> ${medicine.similarity_risk_symptoms || "N/A"}</div>
        <div><strong>Switching note:</strong> ${medicine.switching_note || "N/A"}</div>
        <div><strong>Interaction notes:</strong> ${medicine.interaction_notes || "N/A"}</div>
      </article>
      <article class="card stack">
        <h3>Interactions</h3>
        <div><strong>Total conflicts:</strong> ${interactions?.total_conflicts ?? 0}</div>
        ${interactionSection}
      </article>
    `;
  }

  function renderReminderList(items) {
    state.reminders = items;
    if (!items.length) {
      $("#reminderList").innerHTML = '<div class="empty">No reminders yet.</div>';
      return;
    }

    $("#reminderList").innerHTML = items.map((item) => {
      const activeClass = item.is_active ? "active" : "inactive";
      return `
        <article class="card">
          <div class="metric">
            <strong>${item.medicine_name}</strong>
            <span class="badge ${activeClass}">${item.is_active ? "Active" : "Inactive"}</span>
          </div>
          <div>${item.dose} • ${(item.times || []).join(", ")}</div>
          <div>${item.start_date}${item.end_date ? ` → ${item.end_date}` : ""}</div>
          <div class="action-row">
            <button class="btn ghost" data-reminder-events="${item.id}" type="button">View Events</button>
            <button class="btn secondary" data-reminder-log="${item.id}" type="button">Log Event</button>
            <button class="btn ghost" data-reminder-toggle="${item.id}" data-active="${item.is_active}" type="button">Toggle</button>
            <button class="btn danger" data-reminder-delete="${item.id}" type="button">Delete</button>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderReminderEvents(events) {
    if (!events.length) {
      $("#reminderEventsPanel").innerHTML = '<div class="empty">No events for this reminder.</div>';
      return;
    }

    $("#reminderEventsPanel").innerHTML = events.map((ev) => `
      <article class="card">
        <div class="metric"><strong>${ev.status}</strong><span class="chip">${new Date(ev.scheduled_at).toLocaleString()}</span></div>
        <div>Taken: ${ev.taken_at ? new Date(ev.taken_at).toLocaleString() : "-"}</div>
        <div>${ev.notes || "No notes"}</div>
      </article>
    `).join("");
  }

  function renderMedicalSummary(summary) {
    const diagnoses = asList(summary.diagnoses || summary);
    const allergies = asList(summary.allergies || summary);
    const visits = asList(summary.visits || summary);
    const vitals = asList(summary.vitals || summary);
    const labs = asList(summary.lab_results || summary);

    $("#medicalSummaryPanel").innerHTML = `
      <div class="grid cards-4">
        <article class="card"><h3>Active Diagnoses</h3><p>${summary.active_diagnoses_count ?? 0}</p></article>
        <article class="card"><h3>Allergies</h3><p>${allergies.length}</p></article>
        <article class="card"><h3>Vitals Logged</h3><p>${vitals.length}</p></article>
        <article class="card"><h3>Visits</h3><p>${visits.length}</p></article>
      </div>
      <article class="card stack">
        <h3>Latest Vitals</h3>
        <div>${summary.latest_vitals ? `${summary.latest_vitals.recorded_at} • HR ${summary.latest_vitals.heart_rate ?? "-"}` : "No vitals yet."}</div>
      </article>
      <article class="card stack">
        <h3>Recent Diagnoses</h3>
        ${diagnoses.length ? diagnoses.slice(0, 5).map((d) => `<div>${d.condition_name} • ${d.status}</div>`).join("") : "<div class='empty'>No diagnoses yet.</div>"}
      </article>
      <article class="card stack">
        <h3>Recent Labs</h3>
        ${labs.length ? labs.slice(0, 5).map((l) => `<div>${l.test_name}: ${l.result_value} ${l.unit || ""}</div>`).join("") : "<div class='empty'>No labs yet.</div>"}
      </article>
    `;

    $("#medicalSummary").textContent = pretty(summary);
  }

  function toIsoFromDatetimeLocal(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date.toISOString();
  }

  async function loadMe() {
    const data = await api("/api/auth/me/");
    state.user = data;
    $("#meOutput").textContent = pretty(data);
    renderSession();
  }

  async function loadMedicines(search = "") {
    setLoading("#medicineList", true);
    $("#medicineList").innerHTML = placeholderSkeleton(4);
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    try {
      const data = await api(`/api/medicines/${query}`);
      renderMedicineList(asList(data));
    } finally {
      setLoading("#medicineList", false);
    }
  }

  async function loadReminders() {
    setLoading("#reminderList", true);
    $("#reminderList").innerHTML = placeholderSkeleton(3);
    try {
      const data = await api("/api/reminders/");
      renderReminderList(asList(data));
    } finally {
      setLoading("#reminderList", false);
    }
  }

  async function loadMedicalSummary() {
    setLoading("#medicalSummaryPanel", true);
    $("#medicalSummaryPanel").innerHTML = placeholderSkeleton(4);
    try {
      const data = await api("/api/medical-record/summary/");
      renderMedicalSummary(data);
    } finally {
      setLoading("#medicalSummaryPanel", false);
    }
  }

  async function fetchJson(form, endpoint, method = "POST") {
    const payload = cleanObject(parseForm(form));
    return api(endpoint, { method, body: JSON.stringify(payload) });
  }

  function bindNavigation() {
    $$(".rail-btn").forEach((btn) => {
      btn.addEventListener("click", () => activateTab(btn.dataset.tab));
    });

    $$('[data-jump]').forEach((btn) => {
      btn.addEventListener("click", () => activateTab(btn.dataset.jump));
    });

    window.addEventListener("hashchange", initializeFromHash);
  }

  function bindAuth() {
    $$(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => renderAuthMode(btn.dataset.authMode));
    });

    $("#loginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFormErrors("#loginErrors");
      setLoading(event.currentTarget, true);
      try {
        const data = await fetchJson(event.currentTarget, "/api/auth/token/");
        setAuth(data.access, data.refresh);
        await loadMe();
        showToast("Logged in successfully.", "success");
        activateTab("dashboard");
      } catch (error) {
        renderFormErrors("#loginErrors", error.payload);
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#registerForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFormErrors("#registerErrors");
      setLoading(event.currentTarget, true);
      try {
        const data = await fetchJson(event.currentTarget, "/api/auth/register/");
        setAuth(data.access, data.refresh);
        state.user = data.user;
        $("#meOutput").textContent = pretty(data.user);
        renderSession();
        showToast("Account created and signed in.", "success");
        activateTab("dashboard");
      } catch (error) {
        renderFormErrors("#registerErrors", error.payload);
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#logoutBtn").addEventListener("click", async () => {
      try {
        if (state.access && state.refresh) {
          await api("/api/auth/logout/", { method: "POST", body: JSON.stringify({ refresh: state.refresh }) });
        }
      } catch (_error) {
        // Intentional no-op; local session is still cleared.
      } finally {
        clearAuth();
        showToast("Logged out.", "success");
      }
    });

    $("#refreshMeBtn").addEventListener("click", async () => {
      try {
        await loadMe();
        showToast("Profile refreshed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  }

  function bindOCR() {
    const fileInput = $("#ocrImageInput");
    const startCameraBtn = $("#ocrStartCameraBtn");
    const captureBtn = $("#ocrCaptureBtn");
    const retakeBtn = $("#ocrRetakeBtn");
    const cameraMeta = $("#ocrCameraMeta");
    const video = $("#ocrCameraPreview");
    const canvas = $("#ocrCameraCanvas");
    const ctx = canvas.getContext("2d");
    let cameraStream = null;
    let capturedBlob = null;

    const resetCaptured = () => {
      capturedBlob = null;
      canvas.classList.add("hidden");
      if (cameraStream) video.classList.remove("hidden");
      if (!fileInput.files?.length) {
        fileInput.required = true;
      }
    };

    const stopCamera = () => {
      if (!cameraStream) return;
      cameraStream.getTracks().forEach((t) => t.stop());
      cameraStream = null;
      video.srcObject = null;
      video.classList.add("hidden");
      if (!capturedBlob) {
        cameraMeta.textContent = "Camera is off";
      }
      startCameraBtn.textContent = "Start Camera";
    };

    const startCamera = async () => {
      if (cameraStream) {
        stopCamera();
        return;
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        cameraMeta.textContent = "Camera API not supported in this browser";
        showToast("This browser does not support camera capture.", "error");
        return;
      }
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        video.srcObject = cameraStream;
        await video.play();
        video.classList.remove("hidden");
        canvas.classList.add("hidden");
        cameraMeta.textContent = "Live camera ready";
        startCameraBtn.textContent = "Stop Camera";
      } catch (error) {
        cameraMeta.textContent = "Camera access denied/unavailable";
        showToast(`Camera error: ${error.message}`, "error");
      }
    };

    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (file) {
        $("#ocrFileMeta").textContent = `${file.name} • ${(file.size / 1024).toFixed(1)} KB`;
        resetCaptured();
      } else {
        $("#ocrFileMeta").textContent = "PNG/JPG up to backend limit";
      }
    });

    startCameraBtn.addEventListener("click", startCamera);

    captureBtn.addEventListener("click", () => {
      if (!cameraStream || !video.videoWidth || !video.videoHeight) {
        showToast("Start camera before capture.", "error");
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (!blob) {
          showToast("Capture failed.", "error");
          return;
        }
        capturedBlob = blob;
        canvas.classList.remove("hidden");
        video.classList.add("hidden");
        fileInput.value = "";
        fileInput.required = false;
        $("#ocrFileMeta").textContent = "Using captured camera image";
        cameraMeta.textContent = `Captured ${(blob.size / 1024).toFixed(1)} KB`;
      }, "image/jpeg", 0.92);
    });

    retakeBtn.addEventListener("click", () => {
      resetCaptured();
      if (cameraStream) {
        cameraMeta.textContent = "Live camera ready";
      } else {
        cameraMeta.textContent = "Camera is off";
      }
      $("#ocrFileMeta").textContent = "PNG/JPG up to backend limit";
    });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopCamera();
    });
    window.addEventListener("beforeunload", stopCamera);

    $("#ocrForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      if (capturedBlob) {
        formData.set("image", capturedBlob, `camera-capture-${Date.now()}.jpg`);
      }
      setLoading(form, true);
      $("#ocrMatches").innerHTML = placeholderSkeleton(3);
      try {
        const result = await api("/api/uploads/ocr-search/", { method: "POST", body: formData });
        $("#ocrOutput").textContent = pretty(result);
        renderOCRSummary(result);
        showToast(`OCR complete (${result.match_confidence_tier}).`, "success");
      } catch (error) {
        $("#ocrSummary").innerHTML = `<div class="empty">${error.message}</div>`;
        $("#ocrMatches").innerHTML = '<div class="empty">OCR failed. Try another image.</div>';
        showToast(error.message, "error");
      } finally {
        setLoading(form, false);
      }
    });

    $("#ocrMatches").addEventListener("click", async (event) => {
      const detailId = event.target.getAttribute("data-ocr-detail");
      if (!detailId) return;

      setLoading("#medicineDetailPanel", true);
      try {
        const [medicine, interactions] = await Promise.all([
          api(`/api/medicines/${detailId}/`),
          api(`/api/medicines/${detailId}/interactions/`),
        ]);
        renderMedicineDetail(medicine, interactions);
        activateTab("medicines");
      } catch (error) {
        $("#medicineDetailPanel").innerHTML = `<div class="empty">${error.message}</div>`;
        showToast(error.message, "error");
      } finally {
        setLoading("#medicineDetailPanel", false);
      }
    });
  }

  function bindMedicines() {
    $("#medicineSearchForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const value = new FormData(event.currentTarget).get("search") || "";
      try {
        await loadMedicines(String(value));
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#clearMedicineSearch").addEventListener("click", async () => {
      const input = $("#medicineSearchForm input[name=search]");
      input.value = "";
      try {
        await loadMedicines("");
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#medicineList").addEventListener("click", async (event) => {
      const detailId = event.target.getAttribute("data-med-detail");
      const interactionId = event.target.getAttribute("data-med-interactions");
      if (!detailId && !interactionId) return;

      setLoading("#medicineDetailPanel", true);
      try {
        const targetId = detailId || interactionId;
        if (!targetId) return;
        const [medicine, interactions] = await Promise.all([
          api(`/api/medicines/${targetId}/`),
          api(`/api/medicines/${targetId}/interactions/`),
        ]);
        renderMedicineDetail(medicine, interactions);
      } catch (error) {
        $("#medicineDetailPanel").innerHTML = `<div class="empty">${error.message}</div>`;
      } finally {
        setLoading("#medicineDetailPanel", false);
      }
    });
  }

  function openEventModal(reminderId) {
    const modal = $("#eventModal");
    const form = $("#eventForm");
    form.reset();
    form.elements.reminder_id.value = String(reminderId);
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    form.elements.scheduled_at.value = local;
    modal.showModal();
  }

  function bindReminderModal() {
    $("#cancelEventModal").addEventListener("click", () => $("#eventModal").close());

    $("#eventForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const values = parseForm(form);
      const reminderId = values.reminder_id;
      const payload = {
        status: values.status,
        scheduled_at: toIsoFromDatetimeLocal(values.scheduled_at),
        notes: values.notes || "",
      };
      if (values.status === "taken") {
        payload.taken_at = toIsoFromDatetimeLocal(values.taken_at) || payload.scheduled_at;
      }

      setLoading(form, true);
      try {
        await api(`/api/reminders/${reminderId}/events/`, { method: "POST", body: JSON.stringify(payload) });
        const events = await api(`/api/reminders/${reminderId}/events/`);
        renderReminderEvents(events);
        $("#eventModal").close();
        showToast("Event logged.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(form, false);
      }
    });
  }

  function bindDeleteModal() {
    $("#cancelDeleteBtn").addEventListener("click", () => {
      state.pendingDeleteReminderId = null;
      $("#confirmModal").close();
    });

    $("#confirmDeleteBtn").addEventListener("click", async () => {
      if (!state.pendingDeleteReminderId) return;
      try {
        await api(`/api/reminders/${state.pendingDeleteReminderId}/`, { method: "DELETE" });
        state.pendingDeleteReminderId = null;
        $("#confirmModal").close();
        await loadReminders();
        $("#reminderEventsPanel").innerHTML = '<div class="empty">Pick a reminder and open events.</div>';
        showToast("Reminder deleted.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  }

  function bindReminders() {
    $("#reminderForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const raw = parseForm(form);
      const payload = cleanObject(raw);
      payload.times = String(raw.times || "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
      payload.is_active = form.querySelector("[name=is_active]").checked;

      setLoading(form, true);
      try {
        await api("/api/reminders/", { method: "POST", body: JSON.stringify(payload) });
        form.reset();
        form.querySelector("[name=times]").value = "08:00,20:00";
        form.querySelector("[name=timezone]").value = "Africa/Cairo";
        form.querySelector("[name=is_active]").checked = true;
        await loadReminders();
        showToast("Reminder created.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(form, false);
      }
    });

    $("#reminderList").addEventListener("click", async (event) => {
      const eventId = event.target.getAttribute("data-reminder-events");
      const logId = event.target.getAttribute("data-reminder-log");
      const toggleId = event.target.getAttribute("data-reminder-toggle");
      const deleteId = event.target.getAttribute("data-reminder-delete");

      try {
        if (eventId) {
          const events = await api(`/api/reminders/${eventId}/events/`);
          renderReminderEvents(events);
        }

        if (logId) {
          openEventModal(logId);
        }

        if (toggleId) {
          const active = event.target.getAttribute("data-active") === "true";
          await api(`/api/reminders/${toggleId}/`, { method: "PATCH", body: JSON.stringify({ is_active: !active }) });
          await loadReminders();
          showToast("Reminder updated.", "success");
        }

        if (deleteId) {
          const selected = state.reminders.find((r) => String(r.id) === String(deleteId));
          state.pendingDeleteReminderId = deleteId;
          $("#confirmText").textContent = `Delete reminder for ${selected?.medicine_name || "this medicine"}?`;
          $("#confirmModal").showModal();
        }
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  }

  function bindMedical() {
    $("#recordForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        await fetchJson(event.currentTarget, "/api/medical-record/", "PATCH");
        await loadMedicalSummary();
        showToast("Medical profile saved.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    const list = [
      ["#diagnosisForm", "/api/medical-record/diagnoses/", "Diagnosis added."],
      ["#allergyForm", "/api/medical-record/allergies/", "Allergy added."],
      ["#vitalForm", "/api/medical-record/vitals/", "Vitals added."],
      ["#visitForm", "/api/medical-record/visits/", "Visit added."],
    ];

    list.forEach(([selector, endpoint, toast]) => {
      $(selector).addEventListener("submit", async (event) => {
        event.preventDefault();
        setLoading(event.currentTarget, true);
        try {
          await fetchJson(event.currentTarget, endpoint);
          event.currentTarget.reset();
          await loadMedicalSummary();
          showToast(toast, "success");
        } catch (error) {
          showToast(error.message, "error");
        } finally {
          setLoading(event.currentTarget, false);
        }
      });
    });

    $("#labForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = cleanObject(parseForm(form));
      payload.is_abnormal = form.querySelector("[name=is_abnormal]").checked;
      setLoading(form, true);
      try {
        await api("/api/medical-record/lab-results/", { method: "POST", body: JSON.stringify(payload) });
        form.reset();
        await loadMedicalSummary();
        showToast("Lab result added.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(form, false);
      }
    });
  }

  async function preloadAuthedData() {
    if (!state.access) return;
    try {
      await loadMe();
      await Promise.all([loadMedicines(""), loadReminders(), loadMedicalSummary()]);
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  function bindGlobalHotkeys() {
    window.addEventListener("keydown", (event) => {
      if (event.key.toLowerCase() === "o" && event.altKey) {
        event.preventDefault();
        activateTab("ocr");
      }
    });
  }

  function bootstrap() {
    renderSession();
    bindNavigation();
    bindAuth();
    bindOCR();
    bindMedicines();
    bindReminders();
    bindReminderModal();
    bindDeleteModal();
    bindMedical();
    bindGlobalHotkeys();
    renderAuthMode("login");
    initializeFromHash();
    preloadAuthedData();
  }

  bootstrap();
})();
