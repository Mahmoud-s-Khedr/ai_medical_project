(function () {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const TABS = {
    dashboard: { title: "Today's Tasks", subtitle: "Run complete end-to-end user and integration workflows." },
    auth: { title: "Authentication", subtitle: "Sign in or register to access protected APIs." },
    security: { title: "Account Security", subtitle: "Change password and execute password reset lifecycle endpoints." },
    ocr: { title: "OCR Scan", subtitle: "Upload package photo and evaluate confidence-driven results." },
    medicines: { title: "Medicine Lookup", subtitle: "Search, inspect details, and review interaction risks." },
    history: { title: "Medicine History", subtitle: "Track current/past medicine usage and timeline updates." },
    integrations: { title: "Integrations", subtitle: "Manage apps/keys and approve or reject access requests." },
    external: { title: "External API Simulation", subtitle: "Use API key auth to request and fetch approved user data." },
    exports: { title: "Exports", subtitle: "Run XML export of authenticated user medicine history." },
  };

  const state = {
    access: localStorage.getItem("demo_access") || "",
    refresh: localStorage.getItem("demo_refresh") || "",
    user: null,
    lastRefresh: "Never",
    historyRows: [],
    pendingDeleteHistoryId: null,
    cameraStream: null,
    cameraCaptureBlob: null,
    cameraSnapshotUrl: "",
    externalApiKey: localStorage.getItem("demo_external_api_key") || "",
  };

  function showToast(message, type = "success") {
    const toast = $("#toast");
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3200);
  }

  function pretty(data) {
    if (typeof data === "string") return data;
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

  // Contract guard for POST /api/integrations/keys/: backend expects `app_id` (not `app`).
  function mapApiKeyCreatePayload(raw) {
    const payload = cleanObject(raw);
    if (payload.app !== undefined) {
      payload.app_id = Number(payload.app);
      delete payload.app;
    }
    return payload;
  }

  // Contract guard for PATCH /api/integrations/apps/{id}/: partial update should send only intended fields.
  function mapAppPatchPayload(raw) {
    const payload = {};
    if (raw.name) payload.name = raw.name;
    if (raw.description) payload.description = raw.description;
    if (Object.prototype.hasOwnProperty.call(raw, "is_active")) payload.is_active = true;
    return payload;
  }

  // Contract guard for DataAccessRequest response: requester field is `requester_username`.
  function mapInboxRow(row) {
    return Object.assign({}, row, {
      requester_display: row.requester_username || "N/A",
    });
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

  async function parsePayload(response) {
    const ctype = response.headers.get("content-type") || "";
    if (ctype.includes("application/json")) {
      try {
        return await response.json();
      } catch (_error) {
        return null;
      }
    }
    try {
      return await response.text();
    } catch (_error) {
      return null;
    }
  }

  async function request(path, options = {}, retry = true) {
    const headers = Object.assign({}, options.headers || {});
    const isFormData = options.body instanceof FormData;
    if (!isFormData && !(options.body instanceof Blob) && !(options.body instanceof ArrayBuffer)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    if (state.access) headers.Authorization = `Bearer ${state.access}`;

    const response = await fetch(path, Object.assign({}, options, { headers }));

    if (response.status === 401 && retry && state.refresh) {
      const refreshed = await refreshToken();
      if (refreshed) return request(path, options, false);
    }

    const payload = await parsePayload(response);
    if (!response.ok) {
      const error = new Error(normalizeError(payload));
      error.payload = payload;
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  async function requestExternal(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (!state.externalApiKey) throw new Error("Set API key mode first.");

    const isFormData = options.body instanceof FormData;
    if (!isFormData && !(options.body instanceof Blob) && !(options.body instanceof ArrayBuffer)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    headers["X-API-Key"] = state.externalApiKey;

    const response = await fetch(path, Object.assign({}, options, { headers }));
    const payload = await parsePayload(response);

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

  function setExternalApiKey(value) {
    state.externalApiKey = value || "";
    if (state.externalApiKey) localStorage.setItem("demo_external_api_key", state.externalApiKey);
    else localStorage.removeItem("demo_external_api_key");
    renderSession();
  }

  function renderSession() {
    const authLabel = state.user?.username ? `Signed in: ${state.user.username}` : state.access ? "Authenticated" : "Guest session";
    const role = state.user?.is_staff ? "Staff" : state.user ? "User" : "Unauthenticated";
    $("#sessionChip").textContent = authLabel;
    $("#tokenChip").textContent = state.access ? `Token: Active (${state.lastRefresh})` : "Token: Missing";
    $("#roleChip").textContent = `Role: ${role}`;
    $("#apiKeyModeChip").textContent = state.externalApiKey ? "API Key Mode: On" : "API Key Mode: Off";

    $("#readinessList").innerHTML = `
      <li>${state.access ? "JWT session active" : "Sign in before protected workflows"}</li>
      <li>${state.externalApiKey ? "External API key mode active" : "Set external API key to test /api/external routes"}</li>
      <li>OCR route: <code>/api/uploads/ocr-search/</code></li>
      <li>Integration route set: <code>/api/integrations/*</code></li>
    `;
  }

  function asList(payload) {
    if (Array.isArray(payload)) return payload;
    return payload?.results || [];
  }

  function activateTab(tabName) {
    const info = TABS[tabName] || TABS.dashboard;
    $("#contextTitle").textContent = info.title;
    $("#contextSubtitle").textContent = info.subtitle;

    $$(".rail-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tabName));
    $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.id === `tab-${tabName}`));

    if (location.hash !== `#${tabName}`) history.replaceState(null, "", `#${tabName}`);
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
      return `
        <article class="card">
          <div class="metric"><strong>${m.trade_name || m.name}</strong><span class="badge medium">${score}%</span></div>
          <div class="score"><span style="width:${score}%"></span></div>
          <div>${m.active_ingredient || "N/A"}</div>
          <div>${m.strength || "N/A"} • ${m.dosage_form || "N/A"}</div>
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
          </article>
        `).join("")
      : '<div class="empty">No interactions detected for this medicine.</div>';

    $("#medicineDetailPanel").innerHTML = `
      <article class="card stack">
        <h3>Drug Details</h3>
        <div class="metric"><strong>${medicine.trade_name || "N/A"}</strong><span class="chip">${medicine.strength || "N/A"}</span></div>
        <div><strong>Active ingredient:</strong> ${medicine.active_ingredient || "N/A"}</div>
        <div><strong>Dosage form:</strong> ${medicine.dosage_form || "N/A"}</div>
        <div><strong>Drug class:</strong> ${medicine.drug_class || "N/A"}</div>
      </article>
      <article class="card stack">
        <h3>Interactions</h3>
        <div><strong>Total conflicts:</strong> ${interactions?.total_conflicts ?? 0}</div>
        ${interactionSection}
      </article>
    `;
  }

  function historyStatusClass(status) {
    return status === "current" ? "active" : "inactive";
  }

  function renderHistoryList(items) {
    state.historyRows = items;
    if (!items.length) {
      $("#historyList").innerHTML = '<div class="empty">No medicine history entries yet.</div>';
      return;
    }

    $("#historyList").innerHTML = items.map((row) => `
      <article class="card">
        <div class="metric">
          <strong>${row.medicine_name}</strong>
          <span class="badge ${historyStatusClass(row.status)}">${row.status}</span>
        </div>
        <div>Dose: ${row.dose || "N/A"}</div>
        <div>Start: ${row.start_date || "N/A"} • End: ${row.end_date || "N/A"}</div>
        <div>Notes: ${row.notes || "-"}</div>
        <div class="action-row">
          <button class="btn ghost" data-history-edit="${row.id}" type="button">Mark Past</button>
          <button class="btn danger" data-history-delete="${row.id}" type="button">Delete</button>
        </div>
      </article>
    `).join("");
  }

  function renderInbox(items) {
    if (!items.length) {
      $("#inboxList").innerHTML = '<div class="empty">No incoming access requests.</div>';
      return;
    }

    $("#inboxList").innerHTML = items.map((rawRow) => {
      const row = mapInboxRow(rawRow);
      return `
      <article class="card">
        <div class="metric">
          <strong>Request #${row.id}</strong>
          <span class="badge ${row.status === "approved" ? "active" : row.status === "pending" ? "medium" : "inactive"}">${row.status}</span>
        </div>
        <div><strong>App:</strong> ${row.app_name || row.app}</div>
        <div><strong>Requester:</strong> ${row.requester_display}</div>
        <div><strong>Purpose:</strong> ${row.purpose || "-"}</div>
        <div><strong>Decision note:</strong> ${row.decision_note || "-"}</div>
      </article>
    `;
    }).join("");
  }

  async function loadMe() {
    const data = await request("/api/auth/me/");
    state.user = data;
    $("#meOutput").textContent = pretty(data);
    renderSession();
  }

  async function loadMedicines(search = "") {
    setLoading("#medicineList", true);
    $("#medicineList").innerHTML = placeholderSkeleton(4);
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    try {
      const data = await request(`/api/medicines/${query}`);
      renderMedicineList(asList(data));
    } finally {
      setLoading("#medicineList", false);
    }
  }

  function buildHistoryQuery(filters) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    const query = params.toString();
    return query ? `?${query}` : "";
  }

  async function loadHistory(filters = {}) {
    setLoading("#historyList", true);
    $("#historyList").innerHTML = placeholderSkeleton(4);
    try {
      const query = buildHistoryQuery(filters);
      const data = await request(`/api/medicine-history/${query}`);
      renderHistoryList(asList(data));
    } finally {
      setLoading("#historyList", false);
    }
  }

  async function loadApps() {
    const data = await request("/api/integrations/apps/");
    $("#appsOutput").textContent = pretty(data);
  }

  async function loadKeys() {
    const data = await request("/api/integrations/keys/");
    $("#keysOutput").textContent = pretty(data);
  }

  async function loadInbox() {
    $("#inboxList").innerHTML = placeholderSkeleton(3);
    const data = await request("/api/integrations/access-requests/inbox/");
    renderInbox(Array.isArray(data) ? data : asList(data));
  }

  function bindNavigation() {
    $$(".rail-btn").forEach((btn) => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));
    $$('[data-jump]').forEach((btn) => btn.addEventListener("click", () => activateTab(btn.dataset.jump)));
    window.addEventListener("hashchange", initializeFromHash);
  }

  function bindAuth() {
    $$(".seg-btn").forEach((btn) => btn.addEventListener("click", () => renderAuthMode(btn.dataset.authMode)));

    $("#loginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        const data = await request("/api/auth/token/", { method: "POST", body: JSON.stringify(payload) });
        setAuth(data.access, data.refresh);
        await loadMe();
        showToast("Logged in successfully.", "success");
        activateTab("dashboard");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#registerForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        const data = await request("/api/auth/register/", { method: "POST", body: JSON.stringify(payload) });
        setAuth(data.access, data.refresh);
        state.user = data.user;
        $("#meOutput").textContent = pretty(data.user);
        renderSession();
        showToast("Account created and signed in.", "success");
        activateTab("dashboard");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#logoutBtn").addEventListener("click", async () => {
      try {
        if (state.access && state.refresh) {
          await request("/api/auth/logout/", { method: "POST", body: JSON.stringify({ refresh: state.refresh }) });
        }
      } catch (_error) {
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

  function bindSecurity() {
    $("#changePasswordForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        await request("/api/auth/me/change-password/", { method: "POST", body: JSON.stringify(payload) });
        event.currentTarget.reset();
        showToast("Password changed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#passwordResetRequestForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        await request("/api/auth/password-reset/", { method: "POST", body: JSON.stringify(payload) });
        showToast("Password reset request sent.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#passwordResetConfirmForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        await request("/api/auth/password-reset/confirm/", { method: "POST", body: JSON.stringify(payload) });
        event.currentTarget.reset();
        showToast("Password reset confirmed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });
  }

  function bindOCR() {
    const fileInput = $("#ocrImageInput");
    const ocrForm = $("#ocrForm");
    const preview = $("#cameraPreview");
    const snapshot = $("#cameraSnapshot");
    const canvas = $("#cameraCanvas");
    const cameraStatus = $("#cameraStatus");

    function setCameraStatus(text) {
      cameraStatus.textContent = text;
    }

    function clearCameraCapture() {
      state.cameraCaptureBlob = null;
      if (state.cameraSnapshotUrl) {
        URL.revokeObjectURL(state.cameraSnapshotUrl);
        state.cameraSnapshotUrl = "";
      }
      snapshot.src = "";
      snapshot.classList.add("hidden");
      if (!state.cameraStream) preview.classList.add("hidden");
    }

    function stopCamera() {
      if (!state.cameraStream) return;
      state.cameraStream.getTracks().forEach((track) => track.stop());
      state.cameraStream = null;
      preview.srcObject = null;
      preview.classList.add("hidden");
      setCameraStatus("Camera is off");
    }

    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (file) {
        $("#ocrFileMeta").textContent = `${file.name} • ${(file.size / 1024).toFixed(1)} KB`;
        clearCameraCapture();
      } else {
        $("#ocrFileMeta").textContent = "PNG/JPG up to backend limit";
      }
    });

    $("#startCameraBtn").addEventListener("click", async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        showToast("Camera API is not supported in this browser.", "error");
        return;
      }
      try {
        stopCamera();
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
        state.cameraStream = stream;
        preview.srcObject = stream;
        preview.classList.remove("hidden");
        setCameraStatus("Camera is live");
      } catch (error) {
        setCameraStatus("Camera access denied");
        showToast(error.message || "Could not access camera.", "error");
      }
    });

    $("#stopCameraBtn").addEventListener("click", stopCamera);

    $("#captureCameraBtn").addEventListener("click", async () => {
      if (!state.cameraStream || !preview.videoWidth || !preview.videoHeight) {
        showToast("Start camera before capture.", "error");
        return;
      }
      canvas.width = preview.videoWidth;
      canvas.height = preview.videoHeight;
      const context = canvas.getContext("2d");
      if (!context) {
        showToast("Canvas is not available for capture.", "error");
        return;
      }
      context.drawImage(preview, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
      if (!blob) {
        showToast("Failed to capture image.", "error");
        return;
      }
      if (state.cameraSnapshotUrl) URL.revokeObjectURL(state.cameraSnapshotUrl);
      state.cameraCaptureBlob = blob;
      state.cameraSnapshotUrl = URL.createObjectURL(blob);
      snapshot.src = state.cameraSnapshotUrl;
      snapshot.classList.remove("hidden");
      setCameraStatus(`Captured ${(blob.size / 1024).toFixed(1)} KB`);
      $("#ocrFileMeta").textContent = "Using captured camera image";
      fileInput.value = "";
    });

    $("#clearCameraBtn").addEventListener("click", () => {
      clearCameraCapture();
      $("#ocrFileMeta").textContent = "PNG/JPG up to backend limit";
      setCameraStatus(state.cameraStream ? "Camera is live" : "Camera is off");
    });

    ocrForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData();
      const topK = new FormData(form).get("top_k");
      if (topK !== null && topK !== "") formData.set("top_k", String(topK));

      const selectedFile = fileInput.files?.[0] || null;
      if (selectedFile) formData.set("image", selectedFile, selectedFile.name);
      else if (state.cameraCaptureBlob) formData.set("image", state.cameraCaptureBlob, `camera-capture-${Date.now()}.jpg`);
      else {
        showToast("Select an image or capture one from camera.", "error");
        return;
      }

      setLoading(form, true);
      $("#ocrMatches").innerHTML = placeholderSkeleton(3);
      try {
        const result = await request("/api/uploads/ocr-search/", { method: "POST", body: formData });
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

    window.addEventListener("beforeunload", stopCamera);

    $("#ocrMatches").addEventListener("click", async (event) => {
      const detailId = event.target.getAttribute("data-ocr-detail");
      if (!detailId) return;
      setLoading("#medicineDetailPanel", true);
      try {
        const [medicine, interactions] = await Promise.all([
          request(`/api/medicines/${detailId}/`),
          request(`/api/medicines/${detailId}/interactions/`),
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
      $("#medicineSearchForm input[name=search]").value = "";
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
        const [medicine, interactions] = await Promise.all([
          request(`/api/medicines/${targetId}/`),
          request(`/api/medicines/${targetId}/interactions/`),
        ]);
        renderMedicineDetail(medicine, interactions);
      } catch (error) {
        $("#medicineDetailPanel").innerHTML = `<div class="empty">${error.message}</div>`;
      } finally {
        setLoading("#medicineDetailPanel", false);
      }
    });
  }

  function bindHistory() {
    $("#historyForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const raw = parseForm(event.currentTarget);
      const payload = cleanObject(raw);
      if (payload.medicine_id) payload.medicine_id = Number(payload.medicine_id);

      setLoading(event.currentTarget, true);
      try {
        await request("/api/medicine-history/", { method: "POST", body: JSON.stringify(payload) });
        event.currentTarget.reset();
        await loadHistory(cleanObject(parseForm($("#historyFilterForm"))));
        showToast("Medicine history entry created.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#historyFilterForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await loadHistory(cleanObject(parseForm(event.currentTarget)));
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#clearHistoryFilters").addEventListener("click", async () => {
      $("#historyFilterForm").reset();
      try {
        await loadHistory({});
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#historyList").addEventListener("click", async (event) => {
      const idToDelete = event.target.getAttribute("data-history-delete");
      const idToMarkPast = event.target.getAttribute("data-history-edit");

      try {
        if (idToMarkPast) {
          const today = new Date().toISOString().slice(0, 10);
          await request(`/api/medicine-history/${idToMarkPast}/`, {
            method: "PATCH",
            body: JSON.stringify({ status: "past", end_date: today }),
          });
          await loadHistory(cleanObject(parseForm($("#historyFilterForm"))));
          showToast("Entry moved to past.", "success");
        }

        if (idToDelete) {
          const selected = state.historyRows.find((r) => String(r.id) === String(idToDelete));
          state.pendingDeleteHistoryId = idToDelete;
          $("#confirmText").textContent = `Delete history for ${selected?.medicine_name || "this medicine"}?`;
          $("#confirmModal").showModal();
        }
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  }

  function bindIntegrations() {
    $("#appCreateForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        await request("/api/integrations/apps/", { method: "POST", body: JSON.stringify(payload) });
        event.currentTarget.reset();
        await loadApps();
        showToast("Developer app created.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#appEditForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const raw = parseForm(event.currentTarget);
        const appId = raw.id;
        if (!appId) throw new Error("App ID is required.");
        const payload = mapAppPatchPayload(raw);
        await request(`/api/integrations/apps/${appId}/`, { method: "PATCH", body: JSON.stringify(payload) });
        await loadApps();
        showToast("Developer app updated.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#deleteAppBtn").addEventListener("click", async () => {
      const appId = $("#appEditForm input[name=id]").value;
      if (!appId) {
        showToast("App ID is required.", "error");
        return;
      }
      try {
        await request(`/api/integrations/apps/${appId}/`, { method: "DELETE" });
        await loadApps();
        showToast("Developer app deleted.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#refreshAppsBtn").addEventListener("click", async () => {
      try {
        await loadApps();
        showToast("Apps refreshed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#keyCreateForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = mapApiKeyCreatePayload(parseForm(event.currentTarget));
        const created = await request("/api/integrations/keys/", { method: "POST", body: JSON.stringify(payload) });
        $("#keyWarning").classList.remove("hidden");
        $("#keyWarning").textContent = "Raw API key is shown once below. Save it now; backend stores only hash/prefix.";
        $("#keysOutput").textContent = pretty(created);
        if (created?.api_key) {
          $("#apiKeyModeForm input[name=api_key]").value = created.api_key;
          setExternalApiKey(created.api_key);
        }
        await loadKeys();
        showToast("API key created.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#keyRevokeForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const keyId = Number(new FormData(event.currentTarget).get("key_id"));
        await request(`/api/integrations/keys/${keyId}/revoke/`, { method: "POST" });
        await loadKeys();
        showToast("API key revoked.", "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#refreshKeysBtn").addEventListener("click", async () => {
      try {
        await loadKeys();
        showToast("Keys refreshed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#refreshInboxBtn").addEventListener("click", async () => {
      try {
        await loadInbox();
        showToast("Inbox refreshed.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    $("#inboxDecisionForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const raw = cleanObject(parseForm(event.currentTarget));
        const requestId = Number(raw.request_id);
        const decision = raw.decision;
        const payload = raw.decision_note ? { decision_note: raw.decision_note } : {};
        const result = await request(`/api/integrations/access-requests/${requestId}/${decision}/`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        await loadInbox();
        showToast(`Request #${result.id} ${result.status}.`, "success");
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });
  }

  function bindExternal() {
    $("#apiKeyModeForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const raw = new FormData(event.currentTarget).get("api_key") || "";
      const value = String(raw).trim();
      setExternalApiKey(value);
      showToast(value ? "API key mode enabled." : "API key mode cleared.", "success");
    });

    $("#clearApiKeyModeBtn").addEventListener("click", () => {
      $("#apiKeyModeForm").reset();
      setExternalApiKey("");
      showToast("API key mode cleared.", "success");
    });

    $("#externalRequestForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        const result = await requestExternal("/api/external/access-requests/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        $("#externalOutput").textContent = pretty(result);
        showToast("External access request created.", "success");
      } catch (error) {
        $("#externalOutput").textContent = error.payload ? pretty(error.payload) : error.message;
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });

    $("#externalFetchForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setLoading(event.currentTarget, true);
      try {
        const payload = cleanObject(parseForm(event.currentTarget));
        const query = payload.format === "xml" ? "?format=xml" : "";
        const result = await requestExternal(`/api/external/medicine-history/${encodeURIComponent(payload.username)}/${query}`);
        $("#externalOutput").textContent = pretty(result);
        showToast(`External history fetched (${payload.format}).`, "success");
      } catch (error) {
        $("#externalOutput").textContent = error.payload ? pretty(error.payload) : error.message;
        showToast(error.message, "error");
      } finally {
        setLoading(event.currentTarget, false);
      }
    });
  }

  function bindExports() {
    $("#runExportBtn").addEventListener("click", async () => {
      setLoading("#runExportBtn", true);
      try {
        const result = await request("/api/integrations/medicine-history/export.xml");
        $("#exportOutput").textContent = pretty(result);
        showToast("XML export fetched.", "success");
      } catch (error) {
        $("#exportOutput").textContent = error.payload ? pretty(error.payload) : error.message;
        showToast(error.message, "error");
      } finally {
        setLoading("#runExportBtn", false);
      }
    });
  }

  function bindDeleteModal() {
    $("#cancelDeleteBtn").addEventListener("click", () => {
      state.pendingDeleteHistoryId = null;
      $("#confirmModal").close();
    });

    $("#confirmDeleteBtn").addEventListener("click", async () => {
      if (!state.pendingDeleteHistoryId) return;
      try {
        await request(`/api/medicine-history/${state.pendingDeleteHistoryId}/`, { method: "DELETE" });
        state.pendingDeleteHistoryId = null;
        $("#confirmModal").close();
        await loadHistory(cleanObject(parseForm($("#historyFilterForm"))));
        showToast("History entry deleted.", "success");
      } catch (error) {
        showToast(error.message, "error");
      }
    });
  }

  async function preloadAuthedData() {
    if (!state.access) return;
    try {
      await loadMe();
      await Promise.all([loadMedicines(""), loadHistory({}), loadApps(), loadKeys(), loadInbox()]);
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  function bootstrap() {
    renderSession();
    bindNavigation();
    bindAuth();
    bindSecurity();
    bindOCR();
    bindMedicines();
    bindHistory();
    bindIntegrations();
    bindExternal();
    bindExports();
    bindDeleteModal();

    renderAuthMode("login");
    initializeFromHash();

    if (state.externalApiKey) {
      $("#apiKeyModeForm input[name=api_key]").value = state.externalApiKey;
    }

    preloadAuthedData();
  }

  bootstrap();
})();
