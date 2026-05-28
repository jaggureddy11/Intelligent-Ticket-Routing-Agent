// =============================================================================
// GLOBAL APP STATE & CONFIG
// =============================================================================
const API_BASE = "/api";
let currentFilter = "all";
let categoryChart = null;
let workloadChart = null;

// Auth State
let currentUserToken = localStorage.getItem("token") || null;
let currentUserRole = localStorage.getItem("role") || null;
let currentUserName = localStorage.getItem("name") || null;
let currentUserExpertId = localStorage.getItem("expert_id") || null;

// DOM Elements - Auth & Layouts
const loginOverlay = document.getElementById("login-overlay");
const loginForm = document.getElementById("login-form");
const loginEmail = document.getElementById("login-email");
const loginPassword = document.getElementById("login-password");
const loginError = document.getElementById("login-error");

const appContent = document.getElementById("app-content");
const userDisplayName = document.getElementById("user-display-name");
const userDisplayRole = document.getElementById("user-display-role");
const logoutBtn = document.getElementById("logout-btn");

const panelAdminOnly = document.getElementById("panel-admin-only");
const panelExpertsList = document.getElementById("panel-experts-list");
const dashboardMain = document.getElementById("dashboard-main");
const metricsSection = document.getElementById("metrics-section");

// Clock
const timeDisplay = document.getElementById("live-time");
const hfStatusBadge = document.getElementById("hf-status-badge");
const hfStatusText = document.getElementById("hf-status-text");

// Metrics
const metricTotal = document.getElementById("metric-total-tickets");
const metricSla = document.getElementById("metric-sla-compliance");
const metricExperts = document.getElementById("metric-active-experts");
const metricBreaches = document.getElementById("metric-sla-breaches");

// Form
const ticketForm = document.getElementById("ticket-form");
const ticketTitleInput = document.getElementById("title");
const ticketDescInput = document.getElementById("description");
const submitBtn = document.getElementById("submit-ticket-btn");

// Lists
const ticketsList = document.getElementById("tickets-list");
const expertsList = document.getElementById("experts-list");

// Search & Advanced Filters
const feedSearchInput = document.getElementById("feed-search");
const searchClearBtn = document.getElementById("search-clear-btn");
const filterCategorySelect = document.getElementById("filter-category");
const filterPrioritySelect = document.getElementById("filter-priority");
const exportCsvBtn = document.getElementById("export-csv-btn");
const exportJsonBtn = document.getElementById("export-json-btn");

// Form Counters
const titleCounter = document.getElementById("title-counter");
const descCounter = document.getElementById("desc-counter");

// Modal
const traceModal = document.getElementById("trace-modal");
const closeModalBtn = document.getElementById("close-modal-btn");
const modalTitle = document.getElementById("modal-ticket-title");
const modalMeta = document.getElementById("modal-ticket-meta");
const modalDesc = document.getElementById("modal-ticket-desc");
const auditTimeline = document.getElementById("audit-timeline");

// Ping Modal Elements
const pingModal = document.getElementById("ping-modal");
const closePingModalBtn = document.getElementById("close-ping-modal-btn");
const pingForm = document.getElementById("ping-form");
const pingExpertIdInput = document.getElementById("ping-expert-id");
const pingExpertNameText = document.getElementById("ping-expert-name");
const pingMessageInput = document.getElementById("ping-message");

// =============================================================================
// INITIALIZATION & EVENT LISTENERS
// =============================================================================
document.addEventListener("DOMContentLoaded", () => {
  // Start UTC Live Clock
  updateLiveClock();
  setInterval(updateLiveClock, 1000);

  // Authentication State Sweep
  checkAuth();

  // Login handler
  loginForm.addEventListener("submit", handleLogin);

  // Logout handler
  logoutBtn.addEventListener("click", handleLogout);

  // Form Submit Handler (Ticket Submission)
  ticketForm.addEventListener("submit", handleTicketSubmission);

  // Polling for real-time SLA breaches & notifications every 15 seconds (only when logged in)
  setInterval(() => {
    if (currentUserToken) {
      refreshDashboardSilent();
    }
  }, 15000);

  // Filter pills click handlers
  document.querySelectorAll(".filter-pill").forEach(pill => {
    pill.addEventListener("click", (e) => {
      document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      e.target.classList.add("active");
      currentFilter = e.target.getAttribute("data-filter");
      fetchTickets();
    });
  });

  // Search input listeners (with 250ms debouncing)
  let searchTimeout = null;
  feedSearchInput.addEventListener("input", () => {
    if (feedSearchInput.value.length > 0) {
      searchClearBtn.classList.add("visible");
    } else {
      searchClearBtn.classList.remove("visible");
    }
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      fetchTickets();
    }, 250);
  });

  searchClearBtn.addEventListener("click", () => {
    feedSearchInput.value = "";
    searchClearBtn.classList.remove("visible");
    fetchTickets();
  });

  // Dropdown filter changes
  filterCategorySelect.addEventListener("change", () => fetchTickets());
  filterPrioritySelect.addEventListener("change", () => fetchTickets());

  // Export buttons
  exportCsvBtn.addEventListener("click", () => exportCurrentFeed("csv"));
  exportJsonBtn.addEventListener("click", () => exportCurrentFeed("json"));

  // Form characters live counters
  ticketTitleInput.addEventListener("input", () => {
    const len = ticketTitleInput.value.length;
    titleCounter.innerText = `${len} / 255`;
    if (len >= 240) {
      titleCounter.className = "char-counter danger";
    } else if (len >= 200) {
      titleCounter.className = "char-counter warning";
    } else {
      titleCounter.className = "char-counter";
    }
  });

  ticketDescInput.addEventListener("input", () => {
    const len = ticketDescInput.value.length;
    descCounter.innerText = `${len} characters`;
    if (len >= 1000) {
      descCounter.className = "char-counter danger";
    } else if (len >= 800) {
      descCounter.className = "char-counter warning";
    } else {
      descCounter.className = "char-counter";
    }
  });

  // Live SLA Countdown ticking every 1 second
  setInterval(tickSlaCountdowns, 1000);

  // Modal Close handler
  closeModalBtn.addEventListener("click", () => {
    traceModal.classList.remove("visible");
  });

  // Close modal when clicking outside of contents
  window.addEventListener("click", (e) => {
    if (e.target === traceModal) {
      traceModal.classList.remove("visible");
    }
  });

  // Ping Modal Handlers
  closePingModalBtn.addEventListener("click", () => {
    pingModal.classList.remove("visible");
  });

  window.addEventListener("click", (e) => {
    if (e.target === pingModal) {
      pingModal.classList.remove("visible");
    }
  });

  pingForm.addEventListener("submit", handlePingSubmission);
});

// =============================================================================
// AUTHENTICATION & LOGIN FLOWS
// =============================================================================

function checkAuth() {
  if (currentUserToken) {
    // Hide login, show portal
    loginOverlay.classList.add("hidden");
    appContent.classList.remove("hidden");
    
    // Set user labels
    userDisplayName.innerText = currentUserName;
    userDisplayRole.innerText = currentUserRole;
    
    // Configure role-based layout
    if (currentUserRole === "Expert") {
      panelAdminOnly.classList.add("hidden");
      panelExpertsList.classList.add("hidden");
      metricsSection.classList.add("hidden");
      dashboardMain.classList.add("expert-layout");
    } else {
      panelAdminOnly.classList.remove("hidden");
      panelExpertsList.classList.remove("hidden");
      metricsSection.classList.remove("hidden");
      dashboardMain.classList.remove("expert-layout");
      document.getElementById("notifications-area").classList.add("hidden");
    }
    
    // Fetch dashboard records
    fetchAppStatus();
    refreshDashboard();
  } else {
    // Show login overlay, hide dashboard portal
    loginOverlay.classList.remove("hidden");
    appContent.classList.add("hidden");
  }
}

async function handleLogin(e) {
  e.preventDefault();
  loginError.classList.remove("visible");

  const email = loginEmail.value.trim();
  const password = loginPassword.value;

  try {
    const res = await fetch(`${API_BASE}/auth/login-json`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      throw new Error("Invalid credentials");
    }

    const data = await res.json();
    
    // Save state in browser local storage
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("role", data.role);
    localStorage.setItem("name", data.name);
    if (data.expert_id) {
      localStorage.setItem("expert_id", data.expert_id);
    }
    
    // Update local variables
    currentUserToken = data.access_token;
    currentUserRole = data.role;
    currentUserName = data.name;
    currentUserExpertId = data.expert_id;
    
    loginForm.reset();
    
    // Sweep state
    checkAuth();
  } catch (err) {
    loginError.innerText = "Invalid corporate email or password.";
    loginError.classList.add("visible");
  }
}

function handleLogout() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("name");
  localStorage.removeItem("expert_id");
  
  currentUserToken = null;
  currentUserRole = null;
  currentUserName = null;
  currentUserExpertId = null;
  
  if (categoryChart) {
    categoryChart.destroy();
    categoryChart = null;
  }
  if (workloadChart) {
    workloadChart.destroy();
    workloadChart = null;
  }
  
  checkAuth();
}

function getAuthHeaders() {
  return {
    "Authorization": `Bearer ${currentUserToken}`
  };
}

async function authorizedFetch(url, options = {}) {
  options.headers = {
    ...getAuthHeaders(),
    ...options.headers
  };
  const res = await fetch(url, options);
  if (res.status === 401) {
    handleLogout();
    throw new Error("Unauthorized access token - logging out.");
  }
  return res;
}

// =============================================================================
// CORE FUNCTIONS
// =============================================================================

function updateLiveClock() {
  const now = new Date();
  timeDisplay.innerHTML = `<i class="fa-regular fa-clock"></i> ${now.toUTCString().replace("GMT", "UTC")}`;
}

async function fetchAppStatus() {
  try {
    const res = await authorizedFetch(`${API_BASE}/status`);
    if (res.ok) {
      const data = await res.json();
      if (data.hf_enabled) {
        hfStatusBadge.className = "status-badge connected";
        hfStatusText.innerText = "Hugging Face API: Active";
      } else {
        hfStatusBadge.className = "status-badge fallback";
        hfStatusText.innerText = "Hugging Face API: Fallback Mode";
      }
    }
  } catch (err) {
    hfStatusBadge.className = "status-badge fallback";
    hfStatusText.innerText = "Hugging Face API: Local Fallback";
  }
}

async function refreshDashboard() {
  if (currentUserRole === "Admin") {
    await Promise.all([
      fetchAnalytics(),
      fetchExperts(),
      fetchTickets()
    ]);
  } else {
    await Promise.all([
      fetchExperts(), // Fetch qualified category list metadata
      fetchTickets(),
      fetchNotifications()
    ]);
  }
}

async function refreshDashboardSilent() {
  if (currentUserRole === "Admin") {
    fetchAnalytics();
    fetchExperts();
  } else {
    fetchExperts();
    fetchNotifications();
  }
  fetchTickets(true);
}

// Fetch and render metrics & Doughnut chart
async function fetchAnalytics() {
  if (currentUserRole !== "Admin") return;
  try {
    const res = await authorizedFetch(`${API_BASE}/analytics`);
    if (!res.ok) throw new Error("Analytics error");
    
    const data = await res.json();
    
    // Update metric numbers
    metricTotal.innerText = data.total_tickets;
    metricSla.innerText = `${data.sla_compliance_rate}%`;
    
    if (data.sla_compliance_rate >= 90) {
      metricSla.parentElement.previousElementSibling.className = "metric-icon green";
    } else if (data.sla_compliance_rate >= 75) {
      metricSla.parentElement.previousElementSibling.className = "metric-icon yellow";
    } else {
      metricSla.parentElement.previousElementSibling.className = "metric-icon red";
    }
    
    // Update Charts
    renderCategoryChart(data.by_category);
    renderWorkloadChart(data.by_expert);
    
  } catch (err) {
    console.error("Failed to load analytics: ", err);
  }
}

// Render Doughnut Chart with Category distribution
function renderCategoryChart(categoryData) {
  const chartCanvas = document.getElementById("categoryChart");
  if (!chartCanvas) return;
  const ctx = chartCanvas.getContext("2d");
  
  const labels = Object.keys(categoryData);
  const dataValues = Object.values(categoryData);

  if (labels.length === 0) {
    labels.push("No Tickets");
    dataValues.push(1);
  }

  const chartColors = {
    "Network": "#ef4444",   // Red/Coral
    "Software": "#f97316",  // Orange
    "Hardware": "#0ea5e9",  // Blue
    "Cloud": "#8b5cf6",     // Purple
    "General": "#6b7280",   // Gray
    "No Tickets": "#374151" // Dark Gray
  };
  
  const colors = labels.map(label => chartColors[label] || "#3b82f6");

  if (categoryChart) {
    categoryChart.data.labels = labels;
    categoryChart.data.datasets[0].data = dataValues;
    categoryChart.data.datasets[0].backgroundColor = colors;
    categoryChart.update();
    return;
  }

  categoryChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: dataValues,
        backgroundColor: colors,
        borderWidth: 1,
        borderColor: "rgba(255, 255, 255, 0.08)"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#9ca3af",
            boxWidth: 12,
            font: { family: "Outfit", size: 11 }
          }
        }
      },
      cutout: "70%"
    }
  });
}

// Render Bar Chart with Expert Workload balancing
function renderWorkloadChart(expertData) {
  const chartCanvas = document.getElementById("workloadChart");
  if (!chartCanvas) return;
  const ctx = chartCanvas.getContext("2d");
  
  const labels = Object.keys(expertData);
  const dataValues = Object.values(expertData);

  if (labels.length === 0) {
    labels.push("No Active Loads");
    dataValues.push(0);
  }

  if (workloadChart) {
    workloadChart.data.labels = labels;
    workloadChart.data.datasets[0].data = dataValues;
    workloadChart.update();
    return;
  }

  workloadChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Active Tickets",
        data: dataValues,
        backgroundColor: "rgba(139, 92, 246, 0.45)",
        borderColor: "rgba(139, 92, 246, 1)",
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#9ca3af",
            font: { family: "Outfit", size: 9 }
          }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: {
            color: "#9ca3af",
            font: { family: "Outfit", size: 10 },
            stepSize: 1
          }
        }
      }
    }
  });
}

// Fetch and render experts
async function fetchExperts() {
  try {
    const res = await authorizedFetch(`${API_BASE}/experts`);
    if (!res.ok) throw new Error("Experts fetch error");
    
    const experts = await res.json();
    
    // Count active online experts
    const activeCount = experts.filter(e => e.is_active).length;
    if (currentUserRole === "Admin") {
      metricExperts.innerText = activeCount;
    }
    
    // Render list (Admin only panel)
    if (currentUserRole === "Admin") {
      expertsList.innerHTML = "";
      if (experts.length === 0) {
        expertsList.innerHTML = `<div class="empty-state"><p>No registered experts.</p></div>`;
        return;
      }

      experts.forEach(expert => {
        const workloadClass = expert.active_workload >= 4 ? "high" : (expert.active_workload >= 2 ? "medium" : "low");
        
        const row = document.createElement("div");
        row.className = "expert-row";
        row.innerHTML = `
          <div class="expert-row-left">
            <div class="status-dot ${expert.is_active ? 'active' : 'inactive'}" 
                 title="Click to toggle active/inactive status" 
                 onclick="toggleExpertStatus(${expert.id})">
            </div>
            <div class="expert-details">
              <h4>${expert.name}</h4>
              <p>${expert.category} • <span class="expert-skills" title="${expert.skills}">${expert.skills}</span></p>
            </div>
          </div>
          <div class="expert-row-right">
            <button class="ping-expert-btn" onclick="openPingModal(${expert.id}, '${escapeHTML(expert.name)}')">
              <i class="fa-solid fa-paper-plane"></i> Ping
            </button>
            <div class="workload-count ${workloadClass}">${expert.active_workload}</div>
            <div class="workload-label">Active Load</div>
          </div>
        `;
        expertsList.appendChild(row);
      });
    }
  } catch (err) {
    console.error("Failed to load experts: ", err);
  }
}

// Toggle active/inactive status of an expert (Admin Only)
async function toggleExpertStatus(expertId) {
  if (currentUserRole !== "Admin") return;
  try {
    const res = await authorizedFetch(`${API_BASE}/experts/${expertId}/toggle`, {
      method: "PUT"
    });
    if (res.ok) {
      refreshDashboard();
    }
  } catch (err) {
    console.error("Error toggling expert status: ", err);
  }
}

// Fetch and render ticket live stream
async function fetchTickets(silent = false) {
  try {
    const params = new URLSearchParams();
    if (currentFilter !== "all") {
      params.append("status", currentFilter);
    }
    
    // Read search, category, and priority filters from DOM
    const searchVal = feedSearchInput.value.trim();
    const catVal = filterCategorySelect.value;
    const priVal = filterPrioritySelect.value;
    
    if (searchVal) params.append("q", searchVal);
    if (catVal) params.append("category", catVal);
    if (priVal) params.append("priority", priVal);
    
    let url = `${API_BASE}/tickets`;
    const queryString = params.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
    
    const res = await authorizedFetch(url);
    if (!res.ok) throw new Error("Tickets fetch error");
    
    const tickets = await res.json();
    
    // Store in global activeTicketsStore for exports
    activeTicketsStore = tickets;
    
    // Count breaches for metrics card (Admin only)
    if (currentUserRole === "Admin") {
      const breaches = tickets.filter(t => t.is_sla_breached).length;
      metricBreaches.innerText = breaches;
      if (breaches > 0) {
        metricBreaches.parentElement.previousElementSibling.className = "metric-icon yellow";
      } else {
        metricBreaches.parentElement.previousElementSibling.className = "metric-icon green";
      }
    }

    if (tickets.length === 0) {
      ticketsList.innerHTML = `
        <div class="empty-state">
          <i class="fa-solid fa-folder-open"></i>
          <p>No matching tickets found.</p>
        </div>
      `;
      return;
    }

    ticketsList.innerHTML = "";
    tickets.forEach(ticket => {
      const card = document.createElement("div");
      card.className = `ticket-card pri-${ticket.priority}`;
      card.addEventListener("click", () => openTraceModal(ticket.id));
      
      const createdDate = new Date(ticket.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      
      card.innerHTML = `
        <div class="ticket-card-top">
          <h3>${escapeHTML(ticket.title)}</h3>
          <span class="badge status-${ticket.status.replace(" ", "-")}">
            ${ticket.status}
          </span>
        </div>
        <p class="ticket-desc">${escapeHTML(ticket.description)}</p>
        <div class="ticket-card-bottom">
          <div class="ticket-meta-left">
            <span class="meta-item"><i class="fa-solid fa-hashtag"></i> #${ticket.id}</span>
            <span class="meta-item"><i class="fa-solid fa-clock"></i> ${createdDate}</span>
            <span class="meta-item"><i class="fa-solid fa-folder"></i> ${ticket.category || 'Unclassified'}</span>
            <span class="meta-item badge-priority ${ticket.priority}"><i class="fa-solid fa-circle-exclamation"></i> ${ticket.priority || 'Unassigned'}</span>
            <span class="meta-item"><i class="fa-solid fa-user-circle"></i> ${ticket.assignee || 'Unassigned'}</span>
            ${getSlaBadgeHTML(ticket)}
          </div>
          <button class="trace-trigger-btn" onclick="event.stopPropagation(); openTraceModal(${ticket.id})">
            <i class="fa-solid fa-terminal"></i>
            Trace
          </button>
        </div>
      `;
      ticketsList.appendChild(card);
    });
  } catch (err) {
    if (!silent) {
      ticketsList.innerHTML = `<div class="empty-state"><p>Error connecting to ticket stream.</p></div>`;
    }
    console.error("Failed to load tickets: ", err);
  }
}

// Submit a ticket (Admin Only)
async function handleTicketSubmission(e) {
  e.preventDefault();
  if (currentUserRole !== "Admin") return;

  // Reset errors
  document.getElementById("title-error").classList.remove("visible");
  document.getElementById("desc-error").classList.remove("visible");

  const title = ticketTitleInput.value.trim();
  const description = ticketDescInput.value.trim();

  let isValid = true;
  if (title.length < 3) {
    document.getElementById("title-error").classList.add("visible");
    isValid = false;
  }
  if (description.length < 10) {
    document.getElementById("desc-error").classList.add("visible");
    isValid = false;
  }

  if (!isValid) return;

  // Set Loading state
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>Processing Agent Rules...</span> <i class="fa-solid fa-spinner fa-spin"></i>`;

  try {
    const res = await authorizedFetch(`${API_BASE}/tickets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ title, description })
    });

    if (!res.ok) throw new Error("Ticket submission failed");

    const newTicket = await res.json();
    
    // Clear form
    ticketForm.reset();
    
    // Refresh lists and stats
    await refreshDashboard();
    
    // Auto trace new ticket
    openTraceModal(newTicket.id);

  } catch (err) {
    alert("Pipeline Error: Failed to analyze and route the ticket.");
    console.error(err);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>Submit to Agent Pipeline</span> <i class="fa-solid fa-paper-plane"></i>`;
  }
}

// Open trace details modal
async function openTraceModal(ticketId) {
  try {
    const res = await authorizedFetch(`${API_BASE}/tickets/${ticketId}`);
    if (!res.ok) throw new Error("Failed to fetch details");

    const ticket = await res.json();

    modalTitle.innerText = ticket.title;
    
    const formattedDate = new Date(ticket.created_at).toLocaleString();
    modalMeta.innerText = `Ticket #${ticket.id} | Status: ${ticket.status} | Created: ${formattedDate} | SLA Deadline: ${ticket.sla_deadline ? new Date(ticket.sla_deadline).toLocaleString() : 'N/A'}`;
    modalDesc.innerText = ticket.description;

    // Inject Action Dropdown in Modal for state change
    let statusBlock = document.getElementById("modal-status-block");
    if (!statusBlock) {
      statusBlock = document.createElement("div");
      statusBlock.id = "modal-status-block";
      statusBlock.className = "status-selector-block";
      modalDesc.parentElement.insertAdjacentElement("afterend", statusBlock);
    }
    
    if (currentUserRole === "Expert" && ticket.status !== "Resolved") {
      statusBlock.style.display = "block";
      statusBlock.innerHTML = `
        <h4>Status Action</h4>
        <div class="status-action-row">
          <select id="modal-status-select" class="glass-select">
            <option value="Assigned" ${ticket.status === 'Assigned' ? 'selected' : ''}>Assigned</option>
            <option value="In Progress" ${ticket.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
            <option value="Resolved" ${ticket.status === 'Resolved' ? 'selected' : ''}>Resolved</option>
          </select>
          <button class="trace-trigger-btn" onclick="updateTicketStatusFromModal(${ticket.id})">
            Update Status
          </button>
        </div>
      `;
    } else {
      statusBlock.style.display = "none";
    }

    // Inject AI assistant resolution block
    const aiAssistBlock = document.getElementById("modal-ai-assist-block");
    if (aiAssistBlock) {
      if (ticket.status === "Resolved") {
        if (ticket.resolution_reply) {
          aiAssistBlock.style.display = "block";
          aiAssistBlock.innerHTML = `
            <div class="resolution-reply-block">
              <h4>Resolved Solution Reply</h4>
              <div class="resolution-reply-text">${escapeHTML(ticket.resolution_reply)}</div>
            </div>
          `;
        } else {
          aiAssistBlock.style.display = "none";
        }
      } else if (currentUserRole === "Expert") {
        aiAssistBlock.style.display = "block";
        // Show AI assistant analysis trigger panel for assigned expert
        aiAssistBlock.innerHTML = `
          <div class="ai-assist-header">
            <h4><i class="fa-solid fa-wand-magic-sparkles"></i> AI Assistance Resolution</h4>
            <span class="ai-source-badge">Pipeline Ready</span>
          </div>
          <div id="ai-assist-results" class="ai-solutions-box" style="display: none;">
            <!-- Suggestions & draft text will be loaded here -->
          </div>
          <div class="ai-actions-row" id="ai-assist-actions">
            <button class="ai-btn btn-outline" id="ai-analyze-trigger-btn" onclick="runAITicketAnalysis(${ticket.id})">
              <i class="fa-solid fa-robot"></i> Analyze Ticket with AI
            </button>
          </div>
        `;
      } else {
        aiAssistBlock.style.display = "none";
      }
    }

    // Render Timeline logs
    auditTimeline.innerHTML = "";
    if (ticket.action_logs.length === 0) {
      auditTimeline.innerHTML = `<p style="color: var(--text-dark); font-size: 0.85rem;">No action logs recorded.</p>`;
    } else {
      ticket.action_logs.forEach(log => {
        const item = document.createElement("div");
        item.className = `timeline-item agent-${log.agent}`;
        
        const logTime = new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second: '2-digit'});
        
        item.innerHTML = `
          <div class="timeline-dot"></div>
          <div class="timeline-content">
            <div class="timeline-meta">
              <span class="timeline-agent">${getAgentFriendlyName(log.agent)}</span>
              <span class="timeline-time">${logTime}</span>
            </div>
            <p class="timeline-text">> ${log.result}</p>
          </div>
        `;
        auditTimeline.appendChild(item);
      });
    }

    traceModal.classList.add("visible");
  } catch (err) {
    console.error("Failed to load audit trace modal: ", err);
  }
}

// Update status directly from detail modal
async function updateTicketStatusFromModal(ticketId) {
  const select = document.getElementById("modal-status-select");
  if (!select) return;
  const newStatus = select.value;
  
  try {
    const res = await authorizedFetch(`${API_BASE}/tickets/${ticketId}/status`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ status: newStatus })
    });
    
    if (!res.ok) throw new Error("Failed to update status");
    
    // Close modal, refresh lists, reopen updated modal to show new logs
    traceModal.classList.remove("visible");
    await refreshDashboard();
    openTraceModal(ticketId);
  } catch (err) {
    alert("Authorization Error: You are not authorized to update this ticket.");
    console.error(err);
  }
}

// Expose status updater globally so inline onclick works
window.updateTicketStatusFromModal = updateTicketStatusFromModal;
window.openTraceModal = openTraceModal;

function getAgentFriendlyName(agentId) {
  const names = {
    "ClassificationAgent": "🤖 Classification Agent (LLM)",
    "PrioritizationAgent": "⚡ Prioritization Agent (Urgency Calculator)",
    "RoutingAgent": "🎯 Routing Agent (Expert Matching DB)",
    "SLAMonitorAgent": "⏱️ SLA Monitoring Agent",
    "System": "⚙️ System Action Log"
  };
  return names[agentId] || agentId;
}

function escapeHTML(str) {
  return str.replace(/[&<>'"]/g, 
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag)
  );
}

// Global memory store for tickets list to compute export and SLA counts
let activeTicketsStore = [];

function getSlaBadgeHTML(ticket) {
  if (ticket.status === "Resolved") {
    return `<span class="sla-badge sla-met"><i class="fa-solid fa-check-double"></i> SLA Met</span>`;
  }
  if (!ticket.sla_deadline) {
    return `<span class="sla-badge sla-safe"><i class="fa-solid fa-infinity"></i> No Deadline</span>`;
  }
  
  if (ticket.is_sla_breached) {
    return `<span class="sla-badge sla-breached"><i class="fa-solid fa-triangle-exclamation"></i> SLA Breached</span>`;
  }

  const deadline = new Date(ticket.sla_deadline);
  const now = new Date();
  const diffMs = deadline - now;

  if (diffMs <= 0) {
    return `<span class="sla-badge sla-breached"><i class="fa-solid fa-triangle-exclamation"></i> SLA Breached</span>`;
  }

  const totalSecs = Math.floor(diffMs / 1000);
  const hours = Math.floor(totalSecs / 3600);
  const mins = Math.floor((totalSecs % 3600) / 60);
  
  let label = "";
  if (hours > 0) {
    label = `${hours}h ${mins}m left`;
  } else {
    label = `${mins}m left`;
  }

  // Color coding
  let badgeClass = "sla-safe";
  if (hours < 1) {
    badgeClass = "sla-danger";
  } else if (hours < 4) {
    badgeClass = "sla-warning";
  }

  return `<span class="sla-badge ${badgeClass}" data-deadline="${ticket.sla_deadline}" data-ticket-id="${ticket.id}">
    <i class="fa-regular fa-hourglass-half"></i> <span class="countdown-text">${label}</span>
  </span>`;
}

// Tick down active countdown badges every second in real time on client side
function tickSlaCountdowns() {
  document.querySelectorAll(".sla-badge[data-deadline]").forEach(badge => {
    const deadlineStr = badge.getAttribute("data-deadline");
    const deadline = new Date(deadlineStr);
    const now = new Date();
    const diffMs = deadline - now;

    const countdownSpan = badge.querySelector(".countdown-text");
    if (!countdownSpan) return;

    if (diffMs <= 0) {
      badge.className = "sla-badge sla-breached";
      badge.removeAttribute("data-deadline");
      badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> SLA Breached`;
      
      // Refresh stats if a breach happens in live feed
      fetchAnalytics();
      return;
    }

    const totalSecs = Math.floor(diffMs / 1000);
    const hours = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    
    let text = "";
    if (hours > 0) {
      text = `${hours}h ${mins}m ${secs}s left`;
    } else {
      text = `${mins}m ${secs}s left`;
    }
    
    countdownSpan.innerText = text;

    // Dynamically transition to danger styling when countdown goes below 1 hour
    if (hours < 1 && !badge.classList.contains("sla-danger")) {
      badge.className = "sla-badge sla-danger";
    } else if (hours < 4 && hours >= 1 && !badge.classList.contains("sla-warning") && !badge.classList.contains("sla-danger")) {
      badge.className = "sla-badge sla-warning";
    }
  });
}

// Export current feed data to CSV/JSON
function exportCurrentFeed(format) {
  if (activeTicketsStore.length === 0) {
    alert("No tickets available in the current feed to export.");
    return;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `it_support_flow_tickets_export_${timestamp}`;

  if (format === "json") {
    // Export JSON
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeTicketsStore, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${filename}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  } else if (format === "csv") {
    // Export CSV
    const headers = ["ID", "Title", "Description", "Status", "Category", "Priority", "Assignee", "Created At", "SLA Deadline", "Is Breached"];
    const rows = activeTicketsStore.map(ticket => [
      ticket.id,
      `"${ticket.title.replace(/"/g, '""')}"`,
      `"${ticket.description.replace(/"/g, '""')}"`,
      ticket.status,
      ticket.category || "Unclassified",
      ticket.priority || "Unassigned",
      ticket.assignee || "Unassigned",
      ticket.created_at,
      ticket.sla_deadline || "N/A",
      ticket.is_sla_breached ? "TRUE" : "FALSE"
    ]);

    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
      
    const encodedUri = encodeURI(csvContent);
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", encodedUri);
    downloadAnchor.setAttribute("download", `${filename}.csv`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }
}

async function runAITicketAnalysis(ticketId) {
  const resultsContainer = document.getElementById("ai-assist-results");
  const actionsRow = document.getElementById("ai-assist-actions");
  if (!resultsContainer || !actionsRow) return;

  // Show loading state
  resultsContainer.style.display = "block";
  resultsContainer.innerHTML = `
    <div class="ai-loader">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>IT Support Flow AI is analyzing the ticket issue...</span>
    </div>
  `;
  actionsRow.style.display = "none";

  try {
    const res = await authorizedFetch(`${API_BASE}/tickets/${ticketId}/analyze-ai`, {
      method: "POST"
    });

    if (!res.ok) throw new Error("AI analysis failed");

    const data = await res.json();

    // Render solutions list
    let solutionsHTML = "";
    if (data.solutions && data.solutions.length > 0) {
      solutionsHTML = `
        <div class="ai-solutions-box">
          <h5><i class="fa-solid fa-list-check"></i> Possible Solutions</h5>
          <ol class="ai-solutions-list">
            ${data.solutions.map(s => `<li>${escapeHTML(s)}</li>`).join("")}
          </ol>
        </div>
      `;
    }

    resultsContainer.innerHTML = `
      <div class="ai-assist-header">
        <h4><i class="fa-solid fa-wand-magic-sparkles"></i> AI Analysis Results</h4>
        <span class="ai-source-badge">${escapeHTML(data.source)}</span>
      </div>
      ${solutionsHTML}
      <div class="ai-draft-box">
        <h5><i class="fa-regular fa-paper-plane"></i> Drafted Response</h5>
        <textarea id="ai-draft-reply-text" class="ai-draft-textarea">${escapeHTML(data.draft_reply)}</textarea>
      </div>
    `;

    // Show action buttons
    actionsRow.style.display = "flex";
    actionsRow.innerHTML = `
      <button class="ai-btn btn-outline" onclick="runAITicketAnalysis(${ticketId})">
        <i class="fa-solid fa-rotate"></i> Re-Analyze
      </button>
      <button class="ai-btn" onclick="resolveTicketWithAI(${ticketId})">
        <i class="fa-solid fa-check"></i> Apply Solutions & Resolve
      </button>
    `;

  } catch (err) {
    resultsContainer.innerHTML = `
      <div class="ai-loader" style="color: var(--clr-red);">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>Failed to analyze ticket: ${escapeHTML(err.message)}</span>
      </div>
    `;
    actionsRow.style.display = "flex";
    actionsRow.innerHTML = `
      <button class="ai-btn" onclick="runAITicketAnalysis(${ticketId})">
        <i class="fa-solid fa-rotate"></i> Try Again
      </button>
    `;
  }
}

async function resolveTicketWithAI(ticketId) {
  const textarea = document.getElementById("ai-draft-reply-text");
  if (!textarea) return;
  const resolutionText = textarea.value.trim();

  if (!resolutionText) {
    alert("Please provide a solution or message to draft.");
    return;
  }

  try {
    const res = await authorizedFetch(`${API_BASE}/tickets/${ticketId}/status`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        status: "Resolved",
        resolution_reply: resolutionText
      })
    });

    if (!res.ok) throw new Error("Failed to resolve ticket");

    // Close modal, refresh dashboard and show updated resolved modal
    traceModal.classList.remove("visible");
    await refreshDashboard();
    openTraceModal(ticketId);

  } catch (err) {
    alert("Error resolving ticket: " + err.message);
    console.error(err);
  }
}

// Expose functions to window scope for inline onclick attributes
window.runAITicketAnalysis = runAITicketAnalysis;
window.resolveTicketWithAI = resolveTicketWithAI;

// =============================================================================
// ADMIN & EXPERT NOTIFICATIONS UTILITIES
// =============================================================================

function openPingModal(expertId, expertName) {
  pingExpertIdInput.value = expertId;
  pingExpertNameText.innerText = `Sending message to ${expertName}`;
  pingMessageInput.value = "";
  pingModal.classList.add("visible");
}

async function handlePingSubmission(e) {
  e.preventDefault();
  const expertId = pingExpertIdInput.value;
  const message = pingMessageInput.value.trim();
  if (!message) return;

  try {
    const res = await authorizedFetch(`${API_BASE}/notifications/ping/${expertId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ message })
    });

    if (!res.ok) {
      throw new Error("Failed to send ping");
    }

    pingModal.classList.remove("visible");
    alert("Notification ping successfully sent.");
  } catch (err) {
    alert("Error sending ping: " + err.message);
  }
}

async function fetchNotifications() {
  if (currentUserRole !== "Expert") return;
  const notificationsArea = document.getElementById("notifications-area");
  if (!notificationsArea) return;

  try {
    const res = await authorizedFetch(`${API_BASE}/notifications`);
    if (!res.ok) throw new Error("Failed to fetch notifications");

    const notifications = await res.json();
    const unread = notifications.filter(n => !n.is_read);

    if (unread.length === 0) {
      notificationsArea.innerHTML = "";
      notificationsArea.classList.add("hidden");
      return;
    }

    notificationsArea.classList.remove("hidden");
    notificationsArea.innerHTML = unread.map(n => `
      <div class="notification-alert" id="notification-${n.id}">
        <div class="notification-alert-content">
          <div class="notification-alert-header">
            <i class="fa-solid fa-bell"></i>
            <span>Message from ${escapeHTML(n.sender)} • ${new Date(n.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
          </div>
          <div class="notification-alert-message">${escapeHTML(n.message)}</div>
        </div>
        <button class="notification-dismiss-btn" title="Dismiss Alert" onclick="dismissNotification(${n.id})">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    `).join("");

  } catch (err) {
    console.error("Failed to load notifications:", err);
  }
}

async function dismissNotification(notificationId) {
  try {
    const res = await authorizedFetch(`${API_BASE}/notifications/${notificationId}/read`, {
      method: "PUT"
    });

    if (!res.ok) throw new Error("Failed to dismiss notification");
    fetchNotifications();
  } catch (err) {
    console.error("Failed to dismiss notification:", err);
  }
}

window.openPingModal = openPingModal;
window.handlePingSubmission = handlePingSubmission;
window.fetchNotifications = fetchNotifications;
window.dismissNotification = dismissNotification;

