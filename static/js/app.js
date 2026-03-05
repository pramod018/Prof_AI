document.addEventListener("DOMContentLoaded", () => {
  // ---- Cached DOM References ----
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");
  const loadingOverlay = document.getElementById("loadingOverlay");
  const loadingText = document.getElementById("loadingText");
  const textarea = document.getElementById("problemDescription");
  const charCount = document.getElementById("charCount");
  const queryResults = document.getElementById("queryResults");
  const summaryContent = document.getElementById("summaryContent");
  const ticketsList = document.getElementById("ticketsList");
  const searchResults = document.getElementById("searchResults");
  const searchTicketsList = document.getElementById("searchTicketsList");
  const ingestResults = document.getElementById("ingestResults");
  const ingestStatus = document.getElementById("ingestStatus");
  const syncResults = document.getElementById("syncResults");
  const syncStatus = document.getElementById("syncStatus");
  const syncHistory = document.getElementById("syncHistory");
  const playbookPanel = document.getElementById("sidebarPlaybook");
  const playbookTicketId = document.getElementById("playbookTicketId");
  const playbookSteps = document.getElementById("playbookSteps");
  const playbookDocs = document.getElementById("playbookDocs");
  const playbookCommands = document.getElementById("playbookCommands");
  const statusDot = document.querySelector("#statusIndicator .status-dot");
  const statusText = document.querySelector("#statusIndicator .status-text");

  // ---- Tab Navigation ----
  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      navBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      tabPanels.forEach((p) => p.classList.remove("active"));
      document.getElementById(`tab-${tab}`).classList.add("active");
      if (tab === "sync") loadSyncHistory();
    });
  });

  textarea.addEventListener("input", () => {
    charCount.textContent = textarea.value.length;
  });

  // ---- Helpers ----
  function showLoading(text) {
    loadingText.textContent = text;
    loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    loadingOverlay.classList.add("hidden");
  }

  const VALID_SEVERITIES = new Set(["p1", "p2", "p3", "p4"]);
  function severityClass(sev) {
    if (!sev) return "";
    const key = sev.toLowerCase();
    return VALID_SEVERITIES.has(key) ? key : "";
  }

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function markdownToHtml(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^# (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/^[-*] (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/gs, "<ul>$&</ul>");
    html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = `<p>${html}</p>`;
    html = html.replace(/<p>\s*<(h[234]|ul|ol)/g, "<$1");
    html = html.replace(/<\/(h[234]|ul|ol)>\s*<\/p>/g, "</$1>");
    return html;
  }

  // ---- Playbook ----
  function showPlaybook(ticket) {
    playbookTicketId.textContent =
      (ticket.ticket_id || "N/A") + " — " + (ticket.title || "");

    const steps = ticket.resolution_steps || [];
    playbookSteps.innerHTML = steps.length
      ? steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")
      : '<li class="playbook-empty">No steps recorded</li>';

    const docs = ticket.documents_used || [];
    playbookDocs.innerHTML = docs.length
      ? docs.map((d) => `<li>${escapeHtml(d)}</li>`).join("")
      : '<li class="playbook-empty">No documents recorded</li>';

    const cmds = ticket.commands_used || [];
    playbookCommands.innerHTML = cmds.length
      ? cmds.map((c) => `<div class="playbook-cmd">${escapeHtml(c)}</div>`).join("")
      : '<div class="playbook-empty">No commands recorded</div>';

    playbookPanel.classList.add("visible");
  }

  document.getElementById("playbookClose").addEventListener("click", () => {
    playbookPanel.classList.remove("visible");
  });

  // ---- Ticket Card Renderer ----
  function renderTicketCard(ticket, showDocument) {
    const card = document.createElement("div");
    card.className = "ticket-card";

    const scoreHtml = ticket.similarity_score != null
      ? `<span class="badge badge-score">${Math.round(ticket.similarity_score * 100)}% match</span>`
      : "";

    const hasPlaybook = (ticket.resolution_steps && ticket.resolution_steps.length) ||
                        (ticket.documents_used && ticket.documents_used.length) ||
                        (ticket.commands_used && ticket.commands_used.length);

    card.innerHTML = `
      <div class="ticket-header">
        <span class="ticket-id">${escapeHtml(ticket.ticket_id || "N/A")}</span>
        <div class="ticket-badges">
          <span class="badge badge-severity ${severityClass(ticket.severity)}">${escapeHtml(ticket.severity || "N/A")}</span>
          <span class="badge badge-source">${escapeHtml(ticket.source || "N/A")}</span>
          ${scoreHtml}
        </div>
      </div>
      <div class="ticket-title">${escapeHtml(ticket.title || "No title")}</div>
      <div class="ticket-component">${escapeHtml(ticket.component || "")}${ticket.date ? " &middot; " + escapeHtml(ticket.date) : ""}${hasPlaybook ? ' &middot; <span class="playbook-hint">Click for Playbook</span>' : ""}</div>
      ${showDocument && ticket.document ? `<div class="ticket-details">${escapeHtml(ticket.document)}</div>` : ""}
    `;

    card.addEventListener("click", () => {
      if (hasPlaybook) showPlaybook(ticket);
      if (showDocument && ticket.document) card.classList.toggle("expanded");
    });

    return card;
  }

  // ---- Query Form ----
  document.getElementById("queryForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const desc = textarea.value.trim();
    if (desc.length < 10) return;

    const topK = parseInt(document.getElementById("topK").value, 10);
    const btn = document.getElementById("queryBtn");
    btn.disabled = true;
    showLoading("Retrieving similar tickets and generating AI analysis...");

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_description: desc, top_k: topK }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      const data = await res.json();

      summaryContent.innerHTML = markdownToHtml(data.summary);
      ticketsList.innerHTML = "";
      (data.retrieved_tickets || []).forEach((t) => {
        ticketsList.appendChild(renderTicketCard(t, false));
      });
      queryResults.classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // ---- Search Form ----
  document.getElementById("searchForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = document.getElementById("searchQuery").value.trim();
    if (q.length < 5) return;

    const btn = document.getElementById("searchBtn");
    btn.disabled = true;
    showLoading("Searching knowledge base...");

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&top_k=10`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      const data = await res.json();

      searchTicketsList.innerHTML = "";
      (data.results || []).forEach((t) => {
        searchTicketsList.appendChild(renderTicketCard(t, true));
      });
      searchResults.classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // ---- Ingest Form ----
  document.getElementById("ingestForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const dataPath = document.getElementById("dataPath").value.trim() || null;
    const btn = document.getElementById("ingestBtn");
    btn.disabled = true;
    showLoading("Ingesting data and generating embeddings... This may take a minute.");

    try {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data_path: dataPath }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      const data = await res.json();

      if (data.status === "success") {
        ingestStatus.innerHTML = `
          <p class="ingest-success"><strong>Ingestion Successful</strong></p>
          <p>Documents ingested: <strong>${data.documents_ingested}</strong></p>
          <p>Collection: <strong>${escapeHtml(data.collection)}</strong></p>
          <p>Storage: <strong>${escapeHtml(data.persist_dir)}</strong></p>
        `;
      } else {
        ingestStatus.innerHTML = `<p class="ingest-error"><strong>Error:</strong> ${escapeHtml(data.message || "Unknown error")}</p>`;
      }
      ingestResults.classList.remove("hidden");
      checkHealth();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // ---- Sync Toggle ----
  const syncToggles = document.querySelectorAll(".sync-toggle");
  syncToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      syncToggles.forEach((t) => t.classList.remove("active"));
      toggle.classList.add("active");
      document.querySelectorAll(".sync-panel").forEach((p) => p.classList.remove("active"));
      const target = toggle.dataset.sync;
      document.getElementById(`sync${target.charAt(0).toUpperCase() + target.slice(1)}Panel`).classList.add("active");
    });
  });

  // ---- Sync JSON ----
  document.getElementById("syncJsonForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = document.getElementById("syncJsonInput").value.trim();
    if (!raw) return;

    const btn = document.getElementById("syncJsonBtn");
    btn.disabled = true;
    showLoading("Syncing JSON tickets into knowledge base...");

    try {
      let tickets;
      try { tickets = JSON.parse(raw); } catch { throw new Error("Invalid JSON format."); }
      if (!Array.isArray(tickets)) throw new Error("JSON must be an array.");

      const res = await fetch("/api/sync/json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickets }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      renderSyncResult(await res.json());
      loadSyncHistory();
      checkHealth();
    } catch (err) {
      alert("Sync Error: " + err.message);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // ---- Sync CSV ----
  document.getElementById("syncCsvForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = document.getElementById("syncCsvInput").value.trim();
    if (!raw) return;

    const btn = document.getElementById("syncCsvBtn");
    btn.disabled = true;
    showLoading("Syncing CSV tickets into knowledge base...");

    try {
      const res = await fetch("/api/sync/csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_content: raw }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      renderSyncResult(await res.json());
      loadSyncHistory();
      checkHealth();
    } catch (err) {
      alert("Sync Error: " + err.message);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  function renderSyncResult(data) {
    if (data.status === "success") {
      syncStatus.innerHTML = `
        <p class="ingest-success"><strong>Sync Successful</strong></p>
        <p>Tickets received: <strong>${data.tickets_received}</strong></p>
        <p>Tickets added: <strong>${data.tickets_added}</strong></p>
        <p>Duplicates skipped: <strong>${data.tickets_skipped_duplicate}</strong></p>
        <p>Total in knowledge base: <strong>${data.total_in_knowledge_base}</strong></p>
      `;
    } else {
      syncStatus.innerHTML = `<p class="ingest-error"><strong>Error:</strong> ${escapeHtml(data.message || "Unknown error")}</p>`;
    }
    syncResults.classList.remove("hidden");
  }

  async function loadSyncHistory() {
    try {
      const res = await fetch("/api/sync/history");
      const history = await res.json();

      if (!history || history.length === 0) {
        syncHistory.innerHTML = '<p class="empty-state">No sync activity yet.</p>';
        return;
      }
      syncHistory.innerHTML = history
        .slice()
        .reverse()
        .slice(0, 20)
        .map((entry) => `
          <div class="sync-history-item">
            <div class="sync-meta">
              <span class="sync-type">${escapeHtml(entry.source_type || "unknown")}</span>
              <span>+${entry.tickets_added || 0} added, ${entry.tickets_skipped || 0} skipped</span>
            </div>
            <span class="sync-time">${new Date(entry.timestamp).toLocaleString()}</span>
          </div>
        `)
        .join("");
    } catch { /* ignore */ }
  }

  // ---- Root Cause Analyser ----
  const rcaTextarea = document.getElementById("rcaSymptom");
  const rcaCharCount = document.getElementById("rcaCharCount");
  const rcaResults = document.getElementById("rcaResults");
  const rcaReport = document.getElementById("rcaReport");
  const rcaStatsRow = document.getElementById("rcaStatsRow");
  const rcaTicketsList = document.getElementById("rcaTicketsList");
  const rcaEmailTemplate = document.getElementById("rcaEmailTemplate");
  const copyEmailBtn = document.getElementById("copyEmailBtn");
  const copyEmailText = document.getElementById("copyEmailText");

  if (rcaTextarea && rcaCharCount) {
    rcaTextarea.addEventListener("input", () => {
      rcaCharCount.textContent = rcaTextarea.value.length;
    });
  }

  function renderRcaStats(stats) {
    if (!stats || !rcaStatsRow) return;
    const items = [
      { label: "Similar Tickets Found", value: stats.total_similar_tickets || 0, icon: "📋" },
    ];

    const topComps = Object.entries(stats.top_components || {}).slice(0, 3);
    if (topComps.length > 0) {
      items.push({ label: "Top Component", value: topComps[0][0], icon: "⚙️" });
    }

    const sevs = Object.entries(stats.severity_distribution || {});
    const p1Count = sevs.find(([k]) => k === "P1");
    const p2Count = sevs.find(([k]) => k === "P2");
    if (p1Count) {
      items.push({ label: "P1 Incidents", value: p1Count[1], icon: "🔴" });
    } else if (p2Count) {
      items.push({ label: "P2 Incidents", value: p2Count[1], icon: "🟠" });
    }

    const sources = Object.entries(stats.source_distribution || {});
    if (sources.length > 0) {
      items.push({ label: "Primary Source", value: sources.sort((a, b) => b[1] - a[1])[0][0], icon: "📡" });
    }

    rcaStatsRow.innerHTML = items.map((item) => `
      <div class="rca-stat-card">
        <span class="rca-stat-icon">${item.icon}</span>
        <div class="rca-stat-value">${escapeHtml(String(item.value))}</div>
        <div class="rca-stat-label">${escapeHtml(item.label)}</div>
      </div>
    `).join("");
  }

  document.getElementById("rcaForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const symptom = rcaTextarea.value.trim();
    if (symptom.length < 10) return;

    const topK = parseInt(document.getElementById("rcaTopK").value, 10);
    const btn = document.getElementById("rcaBtn");
    btn.disabled = true;
    showLoading("Running root cause analysis... Retrieving evidence and generating RCA report...");

    try {
      const res = await fetch("/api/rca", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symptom, top_k: topK }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      const data = await res.json();

      renderRcaStats(data.pattern_stats);
      rcaReport.innerHTML = markdownToHtml(data.rca_report);

      if (rcaEmailTemplate && data.email_template) {
        rcaEmailTemplate.textContent = data.email_template;
      }
      if (copyEmailText) copyEmailText.textContent = "Copy to Clipboard";

      rcaTicketsList.innerHTML = "";
      (data.evidence_tickets || []).forEach((t) => {
        rcaTicketsList.appendChild(renderTicketCard(t, false));
      });
      rcaResults.classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  if (copyEmailBtn) {
    copyEmailBtn.addEventListener("click", async () => {
      const text = rcaEmailTemplate ? rcaEmailTemplate.textContent : "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        copyEmailText.textContent = "Copied!";
        setTimeout(() => { copyEmailText.textContent = "Copy to Clipboard"; }, 2000);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(rcaEmailTemplate);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        copyEmailText.textContent = "Selected — press Ctrl+C";
        setTimeout(() => { copyEmailText.textContent = "Copy to Clipboard"; }, 3000);
      }
    });
  }

  // ---- Jira Ticket Generator ----
  const jiraTextarea = document.getElementById("jiraIssue");
  const jiraCharCount = document.getElementById("jiraCharCount");
  const jiraResults = document.getElementById("jiraResults");
  const jiraSeverityBanner = document.getElementById("jiraSeverityBanner");
  const jiraPreview = document.getElementById("jiraPreview");
  const jiraTicketText = document.getElementById("jiraTicketText");
  const copyJiraBtn = document.getElementById("copyJiraBtn");
  const copyJiraText = document.getElementById("copyJiraText");

  if (jiraTextarea && jiraCharCount) {
    jiraTextarea.addEventListener("input", () => {
      jiraCharCount.textContent = jiraTextarea.value.length;
    });
  }

  const SEV_CONFIG = {
    1: { label: "Critical", cls: "sev-critical", icon: "🔴", priority: "Blocker" },
    2: { label: "High", cls: "sev-high", icon: "🟠", priority: "Critical" },
    3: { label: "Medium", cls: "sev-medium", icon: "🟡", priority: "Major" },
    4: { label: "Low", cls: "sev-low", icon: "🟢", priority: "Minor" },
  };

  function renderJiraPreview(data) {
    const sev = data.severity || 3;
    const cfg = SEV_CONFIG[sev] || SEV_CONFIG[3];

    jiraSeverityBanner.className = `jira-severity-banner ${cfg.cls}`;
    jiraSeverityBanner.innerHTML = `
      <span class="jira-sev-icon">${cfg.icon}</span>
      <div class="jira-sev-info">
        <span class="jira-sev-level">Severity ${sev} — ${cfg.label}</span>
        <span class="jira-sev-priority">Jira Priority: ${cfg.priority}</span>
      </div>
      <div class="jira-sev-confidence">
        <span class="jira-confidence-label">AI Confidence</span>
        <span class="jira-confidence-value">${escapeHtml(data.confidence || "N/A")}</span>
      </div>
    `;

    const labels = (data.labels || []).map((l) => `<span class="jira-label">${escapeHtml(l)}</span>`).join(" ");
    const related = (data.related_tickets || []).map((r) =>
      `<div class="jira-related-item">
        <span class="ticket-id">${escapeHtml(r.ticket_id || "")}</span>
        <span>${escapeHtml(r.title || "")}</span>
        <span class="badge badge-severity ${severityClass(r.severity)}">${escapeHtml(r.severity || "")}</span>
      </div>`
    ).join("");

    jiraPreview.innerHTML = `
      <div class="jira-field"><span class="jira-field-label">Summary</span><span class="jira-field-value">${escapeHtml(data.title || "")}</span></div>
      <div class="jira-field"><span class="jira-field-label">Component</span><span class="jira-field-value">${escapeHtml(data.component || "")}</span></div>
      <div class="jira-field"><span class="jira-field-label">Labels</span><span class="jira-field-value">${labels || "—"}</span></div>
      <div class="jira-field"><span class="jira-field-label">Reasoning</span><span class="jira-field-value">${escapeHtml(data.reasoning || "")}</span></div>
      <div class="jira-field full"><span class="jira-field-label">Description</span><div class="jira-field-value jira-desc">${escapeHtml(data.description || "")}</div></div>
      <div class="jira-field full"><span class="jira-field-label">Acceptance Criteria</span><div class="jira-field-value">${escapeHtml(data.acceptance_criteria || "")}</div></div>
      ${related ? `<div class="jira-field full"><span class="jira-field-label">Related Tickets</span><div class="jira-related-list">${related}</div></div>` : ""}
    `;
  }

  document.getElementById("jiraForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const issue = jiraTextarea.value.trim();
    if (issue.length < 10) return;

    const rcaContext = document.getElementById("jiraRcaContext").value.trim() || null;
    const overrideSev = document.getElementById("jiraOverrideSev").value;
    const btn = document.getElementById("jiraBtn");
    btn.disabled = true;
    showLoading("Analysing issue severity and generating Jira ticket...");

    try {
      const body = { issue_description: issue };
      if (rcaContext) body.rca_report = rcaContext;
      if (overrideSev) body.override_severity = parseInt(overrideSev, 10);

      const res = await fetch("/api/jira-ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Server error");
      }
      const data = await res.json();

      renderJiraPreview(data);
      if (jiraTicketText && data.jira_text) {
        jiraTicketText.textContent = data.jira_text;
      }
      if (copyJiraText) copyJiraText.textContent = "Copy to Clipboard";
      jiraResults.classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  if (copyJiraBtn) {
    copyJiraBtn.addEventListener("click", async () => {
      const text = jiraTicketText ? jiraTicketText.textContent : "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        copyJiraText.textContent = "Copied!";
        setTimeout(() => { copyJiraText.textContent = "Copy to Clipboard"; }, 2000);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(jiraTicketText);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        copyJiraText.textContent = "Selected — press Ctrl+C";
        setTimeout(() => { copyJiraText.textContent = "Copy to Clipboard"; }, 3000);
      }
    });
  }

  // ---- Fine-Tune Form ----
  const finetuneForm = document.getElementById("finetuneForm");
  if (finetuneForm) {
    finetuneForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const dataPath = document.getElementById("ftDataPath").value.trim() || null;
      const epochs = parseInt(document.getElementById("ftEpochs").value, 10);
      const batchSize = parseInt(document.getElementById("ftBatchSize").value, 10);
      const btn = document.getElementById("finetuneBtn");
      btn.disabled = true;
      showLoading("Fine-tuning embedding model... This may take several minutes.");

      try {
        const res = await fetch("/api/finetune", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ data_path: dataPath, epochs, batch_size: batchSize }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Server error");
        }
        const data = await res.json();
        const status = document.getElementById("finetuneStatus");

        if (data.status === "success") {
          status.innerHTML = `
            <p class="ingest-success"><strong>Fine-Tuning Complete</strong></p>
            <p>Base model: <strong>${escapeHtml(data.base_model)}</strong></p>
            <p>Training pairs: <strong>${data.training_pairs}</strong></p>
            <p>Eval pairs: <strong>${data.eval_pairs}</strong></p>
            <p>Epochs: <strong>${data.epochs}</strong></p>
            <p>Output: <strong>${escapeHtml(data.output_dir)}</strong></p>
            <p style="margin-top:12px;color:var(--text-secondary);">${escapeHtml(data.message)}</p>
          `;
        } else {
          status.innerHTML = `<p class="ingest-error"><strong>Error:</strong> ${escapeHtml(data.message || "Unknown error")}</p>`;
        }
        document.getElementById("finetuneResults").classList.remove("hidden");
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        hideLoading();
        btn.disabled = false;
      }
    });
  }

  // ---- Health Check ----
  async function checkHealth() {
    try {
      const data = await (await fetch("/api/health")).json();
      if (data.database_initialized) {
        statusDot.className = "status-dot online";
        statusText.textContent = "DB Ready";
      } else {
        statusDot.className = "status-dot offline";
        statusText.textContent = "DB Not Initialized";
      }
    } catch {
      statusDot.className = "status-dot offline";
      statusText.textContent = "Server Offline";
    }
  }

  checkHealth();
  setInterval(checkHealth, 30000);
});
