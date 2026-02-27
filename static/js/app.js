document.addEventListener("DOMContentLoaded", () => {
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");
  const loadingOverlay = document.getElementById("loadingOverlay");
  const loadingText = document.getElementById("loadingText");

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      navBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      tabPanels.forEach((p) => p.classList.remove("active"));
      document.getElementById(`tab-${tab}`).classList.add("active");
    });
  });

  const charCount = document.getElementById("charCount");
  const textarea = document.getElementById("problemDescription");
  textarea.addEventListener("input", () => {
    charCount.textContent = textarea.value.length;
  });

  function showLoading(text) {
    loadingText.textContent = text;
    loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    loadingOverlay.classList.add("hidden");
  }

  function severityClass(sev) {
    if (!sev) return "";
    const s = sev.toLowerCase();
    if (s === "p2") return "p2";
    if (s === "p3") return "p3";
    if (s === "p4") return "p4";
    return "";
  }

  function renderTicketCard(ticket, showDocument) {
    const card = document.createElement("div");
    card.className = "ticket-card";

    const scoreHtml = ticket.similarity_score != null
      ? `<span class="badge badge-score">${Math.round(ticket.similarity_score * 100)}% match</span>`
      : "";

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
      <div class="ticket-component">${escapeHtml(ticket.component || "")}${ticket.date ? " &middot; " + escapeHtml(ticket.date) : ""}</div>
      ${showDocument && ticket.document ? `<div class="ticket-details">${escapeHtml(ticket.document)}</div>` : ""}
    `;

    if (showDocument && ticket.document) {
      card.addEventListener("click", () => card.classList.toggle("expanded"));
    }

    return card;
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

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // Query form
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

      document.getElementById("summaryContent").innerHTML = markdownToHtml(data.summary);

      const ticketsList = document.getElementById("ticketsList");
      ticketsList.innerHTML = "";
      if (data.retrieved_tickets) {
        data.retrieved_tickets.forEach((t) => {
          ticketsList.appendChild(renderTicketCard(t, false));
        });
      }

      document.getElementById("queryResults").classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // Search form
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

      const list = document.getElementById("searchTicketsList");
      list.innerHTML = "";
      if (data.results) {
        data.results.forEach((t) => {
          list.appendChild(renderTicketCard(t, true));
        });
      }

      document.getElementById("searchResults").classList.remove("hidden");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // Ingest form
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
      const status = document.getElementById("ingestStatus");

      if (data.status === "success") {
        status.innerHTML = `
          <p class="ingest-success"><strong>Ingestion Successful</strong></p>
          <p>Documents ingested: <strong>${data.documents_ingested}</strong></p>
          <p>Collection: <strong>${escapeHtml(data.collection)}</strong></p>
          <p>Storage: <strong>${escapeHtml(data.persist_dir)}</strong></p>
        `;
      } else {
        status.innerHTML = `<p class="ingest-error"><strong>Error:</strong> ${escapeHtml(data.message || "Unknown error")}</p>`;
      }

      document.getElementById("ingestResults").classList.remove("hidden");
      checkHealth();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // --- Fine-tune form handler (DISABLED) ---
  // Uncomment when fine-tune tab and API endpoint are enabled.
  //
  // const finetuneForm = document.getElementById("finetuneForm");
  // if (finetuneForm) {
  //   finetuneForm.addEventListener("submit", async (e) => {
  //     e.preventDefault();
  //     const dataPath = document.getElementById("ftDataPath").value.trim() || null;
  //     const epochs = parseInt(document.getElementById("ftEpochs").value, 10);
  //     const batchSize = parseInt(document.getElementById("ftBatchSize").value, 10);
  //     const btn = document.getElementById("finetuneBtn");
  //     btn.disabled = true;
  //     showLoading("Fine-tuning embedding model... This may take several minutes.");
  //
  //     try {
  //       const res = await fetch("/api/finetune", {
  //         method: "POST",
  //         headers: { "Content-Type": "application/json" },
  //         body: JSON.stringify({ data_path: dataPath, epochs: epochs, batch_size: batchSize }),
  //       });
  //
  //       if (!res.ok) {
  //         const err = await res.json();
  //         throw new Error(err.detail || "Server error");
  //       }
  //
  //       const data = await res.json();
  //       const status = document.getElementById("finetuneStatus");
  //
  //       if (data.status === "success") {
  //         status.innerHTML = `
  //           <p class="ingest-success"><strong>Fine-Tuning Complete</strong></p>
  //           <p>Base model: <strong>${escapeHtml(data.base_model)}</strong></p>
  //           <p>Training pairs: <strong>${data.training_pairs}</strong></p>
  //           <p>Eval pairs: <strong>${data.eval_pairs}</strong></p>
  //           <p>Epochs: <strong>${data.epochs}</strong></p>
  //           <p>Output: <strong>${escapeHtml(data.output_dir)}</strong></p>
  //           <p style="margin-top:12px;color:var(--text-secondary);">${escapeHtml(data.message)}</p>
  //         `;
  //       } else {
  //         status.innerHTML = `<p class="ingest-error"><strong>Error:</strong> ${escapeHtml(data.message || "Unknown error")}</p>`;
  //       }
  //
  //       document.getElementById("finetuneResults").classList.remove("hidden");
  //     } catch (err) {
  //       alert(`Error: ${err.message}`);
  //     } finally {
  //       hideLoading();
  //       btn.disabled = false;
  //     }
  //   });
  // }

  // Health check
  async function checkHealth() {
    const indicator = document.getElementById("statusIndicator");
    const dot = indicator.querySelector(".status-dot");
    const text = indicator.querySelector(".status-text");

    try {
      const res = await fetch("/api/health");
      const data = await res.json();

      if (data.database_initialized) {
        dot.className = "status-dot online";
        text.textContent = "DB Ready";
      } else {
        dot.className = "status-dot offline";
        text.textContent = "DB Not Initialized";
      }
    } catch {
      dot.className = "status-dot offline";
      text.textContent = "Server Offline";
    }
  }

  checkHealth();
  setInterval(checkHealth, 30000);
});
