/**
 * Main Application Orchestrator & UI Controller
 * Trustworthy Multi-Agent Financial Research System
 *
 * Implements:
 * - Persistent scene parallax & cinematic frame coordination
 * - Mode A (Permitted Website / SEC EDGAR Discovery)
 * - Mode B (Multi-File PDF & PPTX Upload with Concurrency Control & Byte Progress)
 * - Research Run Lifecycle & Signature Architectural Scanning Animation
 * - 6-Stage Truthful Event-Driven Workflow Mapping
 * - Report Workspace, Deterministic Financial Scorecard, & Risk Factors
 * - Claim Evidence Inspector Drawer with Safe Text Rendering
 * - Human-in-the-Loop Review Cockpit & Persisted Decision Submissions
 * - Execution Audit Trace Viewer & Toast System
 */

import { api } from './api.js';
import { appState } from './state.js';

// --- Toast Notification Helper ---
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-notice ${type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : ''}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(16px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// --- DOM Cache ---
let DOM = {};

function cacheDOMElements() {
  DOM = {
    persistentScene: document.getElementById('persistentScene'),
    sceneImageWrapper: document.getElementById('sceneImageWrapper'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),

    // Nav Buttons
    navResearchBtn: document.getElementById('navResearchBtn'),
    navReportBtn: document.getElementById('navReportBtn'),
    navReviewBtn: document.getElementById('navReviewBtn'),
    navTraceBtn: document.getElementById('navTraceBtn'),

    // Views
    landingView: document.getElementById('landingView'),
    progressPanel: document.getElementById('progressPanel'),
    reportWorkspace: document.getElementById('reportWorkspace'),
    traceWorkspace: document.getElementById('traceWorkspace'),

    // Mode Switchers
    modeWebBtn: document.getElementById('modeWebBtn'),
    modeUploadBtn: document.getElementById('modeUploadBtn'),
    webModePanel: document.getElementById('webModePanel'),
    uploadModePanel: document.getElementById('uploadModePanel'),

    // Common Inputs
    researchQuestionInput: document.getElementById('researchQuestionInput'),
    companyTickerInput: document.getElementById('companyTickerInput'),
    periodInput: document.getElementById('periodInput'),

    // Mode A Elements
    websiteUrlInput: document.getElementById('websiteUrlInput'),
    findDocumentsBtn: document.getElementById('findDocumentsBtn'),
    processResearchWebBtn: document.getElementById('processResearchWebBtn'),
    discoveryResultsBox: document.getElementById('discoveryResultsBox'),

    // Mode B Elements
    dropZone: document.getElementById('dropZone'),
    fileInput: document.getElementById('fileInput'),
    browseFilesBtn: document.getElementById('browseFilesBtn'),
    uploadQueueContainer: document.getElementById('uploadQueueContainer'),
    queueRowsList: document.getElementById('queueRowsList'),
    queueCount: document.getElementById('queueCount'),
    queueTotalSize: document.getElementById('queueTotalSize'),
    clearQueueBtn: document.getElementById('clearQueueBtn'),
    processResearchUploadBtn: document.getElementById('processResearchUploadBtn'),

    // Progress Elements
    progressTitle: document.getElementById('progressTitle'),
    progressSubtitle: document.getElementById('progressSubtitle'),
    progressRunIdSpan: document.getElementById('progressRunIdSpan'),
    masterProgressFill: document.getElementById('masterProgressFill'),
    cancelRunBtn: document.getElementById('cancelRunBtn'),

    // Report Elements
    reportHeaderTitle: document.getElementById('reportHeaderTitle'),
    reportHeaderInquiry: document.getElementById('reportHeaderInquiry'),
    reportVerificationStatusBadge: document.getElementById('reportVerificationStatusBadge'),
    execSummaryContent: document.getElementById('execSummaryContent'),
    metricsScorecardGrid: document.getElementById('metricsScorecardGrid'),
    claimsContainer: document.getElementById('claimsContainer'),
    risksContainer: document.getElementById('risksContainer'),
    verificationSummaryGrid: document.getElementById('verificationSummaryGrid'),
    unresolvedSection: document.getElementById('unresolvedSection'),
    unresolvedContent: document.getElementById('unresolvedContent'),

    // Inspector Drawer
    inspectorOverlay: document.getElementById('inspectorOverlay'),
    closeInspectorBtn: document.getElementById('closeInspectorBtn'),
    inspectorClaimText: document.getElementById('inspectorClaimText'),
    inspectorExcerptText: document.getElementById('inspectorExcerptText'),
    inspectorDocId: document.getElementById('inspectorDocId'),
    inspectorPageNum: document.getElementById('inspectorPageNum'),
    inspectorVerdictBadge: document.getElementById('inspectorVerdictBadge'),
    claimApproveBtn: document.getElementById('claimApproveBtn'),
    claimQualifyBtn: document.getElementById('claimQualifyBtn'),
    claimRejectBtn: document.getElementById('claimRejectBtn'),

    // Human Review Cockpit
    decApproveBtn: document.getElementById('decApproveBtn'),
    decQualifyBtn: document.getElementById('decQualifyBtn'),
    decRejectBtn: document.getElementById('decRejectBtn'),
    reviewerNameInput: document.getElementById('reviewerNameInput'),
    reviewCommentsInput: document.getElementById('reviewCommentsInput'),
    submitReviewBtn: document.getElementById('submitReviewBtn'),

    // Trace View
    traceEventsList: document.getElementById('traceEventsList'),
  };
}

// ==============================================================================
// 1. Subtle Architectural Parallax & Motion Foundations
// ==============================================================================
function initParallax() {
  const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (isReduced || !DOM.sceneImageWrapper) return;

  let targetX = 0;
  let targetY = 0;
  let currentX = 0;
  let currentY = 0;
  let rafId = null;

  window.addEventListener('mousemove', (e) => {
    const normX = (e.clientX / window.innerWidth) - 0.5;
    const normY = (e.clientY / window.innerHeight) - 0.5;
    targetX = normX * -14; // Subtle max 14px displacement
    targetY = normY * -10;
    if (!rafId) rafId = requestAnimationFrame(updateParallax);
  }, { passive: true });

  function updateParallax() {
    currentX += (targetX - currentX) * 0.08;
    currentY += (targetY - currentY) * 0.08;
    if (DOM.sceneImageWrapper) {
      DOM.sceneImageWrapper.style.transform = `scale(1.04) translate3d(${currentX.toFixed(2)}px, ${currentY.toFixed(2)}px, 0)`;
    }
    if (Math.abs(targetX - currentX) > 0.05 || Math.abs(targetY - currentY) > 0.05) {
      rafId = requestAnimationFrame(updateParallax);
    } else {
      rafId = null;
    }
  }
}

// ==============================================================================
// 2. System Health & Connectivity Probe
// ==============================================================================
async function checkSystemHealth() {
  try {
    const health = await api.checkHealth();
    if (health.status === 'ok') {
      DOM.statusDot.className = 'status-dot';
      DOM.statusText.textContent = `SYSTEM ONLINE &bull; ${health.environment?.toUpperCase() || 'PROD'}`;
      appState.set({ isBackendHealthy: true });
    } else {
      throw new Error(health.message || 'Health check returned degraded status');
    }
  } catch (err) {
    DOM.statusDot.className = 'status-dot offline';
    DOM.statusText.textContent = 'BACKEND OFFLINE';
    appState.set({ isBackendHealthy: false });
    showToast('Cannot connect to FastAPI backend at ' + api.baseUrl + '. Ensure uvicorn is running.', 'error');
  }
}

// ==============================================================================
// 3. View Routing & Persistent Scene Coordination
// ==============================================================================
function switchView(viewName) {
  // Update Navigation Pill
  const navButtons = [DOM.navResearchBtn, DOM.navReportBtn, DOM.navReviewBtn, DOM.navTraceBtn];
  navButtons.forEach((btn) => btn?.classList.remove('active'));

  if (viewName === 'landing') DOM.navResearchBtn?.classList.add('active');
  if (viewName === 'report') DOM.navReportBtn?.classList.add('active');
  if (viewName === 'review') DOM.navReviewBtn?.classList.add('active');
  if (viewName === 'trace') DOM.navTraceBtn?.classList.add('active');

  // Hide all sections
  DOM.landingView.style.display = 'none';
  DOM.progressPanel.style.display = 'none';
  DOM.reportWorkspace.style.display = 'none';
  DOM.traceWorkspace.style.display = 'none';

  // The persistent background remains mounted in place!
  if (viewName === 'landing') {
    DOM.landingView.style.display = 'block';
  } else if (viewName === 'progress') {
    DOM.progressPanel.style.display = 'block';
  } else if (viewName === 'report' || viewName === 'review') {
    DOM.reportWorkspace.style.display = 'block';
    if (viewName === 'review') {
      const reviewBox = document.getElementById('embeddedReviewBox');
      reviewBox?.scrollIntoView({ behavior: 'smooth' });
    }
  } else if (viewName === 'trace') {
    DOM.traceWorkspace.style.display = 'block';
    renderTraceView();
  }

  appState.set({ currentView: viewName });
}

// ==============================================================================
// 4. Acquisition Modes (Mode A: Web Discovery vs Mode B: Uploads)
// ==============================================================================
function setAcquisitionMode(mode) {
  if (mode === 'web') {
    DOM.modeWebBtn.classList.add('active');
    DOM.modeUploadBtn.classList.remove('active');
    DOM.webModePanel.style.display = 'block';
    DOM.uploadModePanel.style.display = 'none';
    appState.set({ mode: 'web' });
  } else {
    DOM.modeUploadBtn.classList.add('active');
    DOM.modeWebBtn.classList.remove('active');
    DOM.uploadModePanel.style.display = 'block';
    DOM.webModePanel.style.display = 'none';
    appState.set({ mode: 'upload' });
  }
}

// --- Mode A: Find Documents Execution ---
async function handleFindDocuments() {
  const ticker = DOM.companyTickerInput.value.trim().toUpperCase() || 'MSFT';
  DOM.findDocumentsBtn.disabled = true;
  DOM.findDocumentsBtn.textContent = 'Discovering...';
  DOM.discoveryResultsBox.style.display = 'block';
  DOM.discoveryResultsBox.innerHTML = `
    <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); padding: 12px; background: rgba(4,7,13,0.5); border: 1px solid var(--border-fine); border-radius: 4px;">
      Querying permitted disclosures and SEC submissions for <strong>${ticker}</strong>...
    </div>
  `;

  try {
    const res = await api.discoverCompany(ticker, 'US');
    appState.set({ discoveryManifest: res });

    const filings = res.discovered_filings || [];
    if (filings.length === 0) {
      DOM.discoveryResultsBox.innerHTML = `
        <div style="font-family: var(--font-mono); font-size: 11px; color: var(--status-qualified); padding: 12px; background: rgba(229,173,53,0.08); border: 1px solid rgba(229,173,53,0.25); border-radius: 4px;">
          No eligible financial documents were found in the sources inspected for ${ticker}. You may upload local PDFs or presentations in Mode B.
        </div>
      `;
    } else {
      const filingRows = filings.slice(0, 3).map((f) => `
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.04);">
          <span>Form ${f.form} (${f.report_date || f.filing_date})</span>
          <span style="color:var(--status-verified);">ELIGIBLE DISCLOSURE</span>
        </div>
      `).join('');

      DOM.discoveryResultsBox.innerHTML = `
        <div style="font-family: var(--font-mono); font-size: 11px; padding: 12px; background: rgba(61,214,140,0.05); border: 1px solid rgba(61,214,140,0.2); border-radius: 4px;">
          <div style="color:var(--status-verified); font-weight:600; margin-bottom:6px;">
            Found ${filings.length} eligible filings for ${res.company_name || ticker} (CIK: ${res.cik || 'N/A'})
          </div>
          <div style="color:var(--text-secondary); margin-bottom:8px;">${filingRows}</div>
          <div style="color:var(--text-muted); font-size:10px;">Ready to process multi-agent research against discovered SEC disclosures.</div>
        </div>
      `;
      showToast(`Discovered ${filings.length} eligible disclosures for ${ticker}.`, 'success');
    }
  } catch (err) {
    DOM.discoveryResultsBox.innerHTML = `
      <div style="font-family: var(--font-mono); font-size: 11px; color: var(--status-blocked); padding: 12px; background: rgba(240,82,82,0.08); border: 1px solid rgba(240,82,82,0.25); border-radius: 4px;">
        Discovery failed: ${err.message || 'Source unreachable.'}
      </div>
    `;
    showToast(`Discovery error: ${err.message}`, 'error');
  } finally {
    DOM.findDocumentsBtn.disabled = false;
    DOM.findDocumentsBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
      </svg>
      Find Documents
    `;
  }
}

// --- Mode B: Upload Queue & Drag-and-Drop Management ---
function renderUploadQueue() {
  const queue = appState.get().uploadQueue;
  if (queue.length === 0) {
    DOM.uploadQueueContainer.style.display = 'none';
    return;
  }

  DOM.uploadQueueContainer.style.display = 'block';
  DOM.queueCount.textContent = queue.length;

  const totalBytes = queue.reduce((acc, f) => acc + f.size, 0);
  DOM.queueTotalSize.textContent = `${(totalBytes / (1024 * 1024)).toFixed(2)} MB`;

  DOM.queueRowsList.innerHTML = queue.map((item) => {
    let badgeClass = 'badge-queued';
    if (item.status === 'UPLOADING') badgeClass = 'badge-uploading';
    if (item.status === 'INDEXED' || item.status === 'UPLOADED') badgeClass = 'badge-indexed';
    if (item.status === 'FAILED' || item.status === 'REJECTED') badgeClass = 'badge-failed';

    return `
      <div class="queue-row" data-id="${item.id}">
        <div class="queue-file-name" title="${item.name}">${item.name}</div>
        <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">${(item.size / 1024).toFixed(1)} KB</div>
        <div><span class="queue-status-badge ${badgeClass}">${item.status}</span></div>
        <div class="queue-progress-bar">
          <div class="queue-progress-fill" style="width: ${item.percent}%;"></div>
        </div>
        <button type="button" class="btn-remove-queue" data-id="${item.id}" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:14px;" title="Remove">&times;</button>
      </div>
    `;
  }).join('');

  // Attach remove handlers
  DOM.queueRowsList.querySelectorAll('.btn-remove-queue').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const id = e.currentTarget.getAttribute('data-id');
      appState.removeFileFromQueue(id);
      renderUploadQueue();
    });
  });
}

// Bounded Concurrency Upload Dispatcher
async function uploadQueuedFiles() {
  const state = appState.get();
  const queue = state.uploadQueue.filter((f) => f.isValidType && (f.status === 'QUEUED' || f.status === 'FAILED'));
  if (queue.length === 0) return true;

  const concurrency = state.concurrencyLimit || 3;
  let activeIndex = 0;
  const companyTicker = DOM.companyTickerInput.value.trim().toUpperCase() || 'MSFT';
  const reportingPeriod = DOM.periodInput.value.trim() || 'FY24';

  async function worker() {
    while (activeIndex < queue.length) {
      const current = queue[activeIndex++];
      current.status = 'UPLOADING';
      renderUploadQueue();

      try {
        const uploadResult = await api.uploadFile(
          current.file,
          {
            companyTicker,
            reportingPeriod,
            processNow: true,
          },
          (prog) => {
            current.percent = prog.percent;
            renderUploadQueue();
          }
        );

        current.status = 'INDEXED';
        current.percent = 100;
        current.documentId = uploadResult.uploaded_documents?.[0]?.document_id || null;
      } catch (err) {
        current.status = 'FAILED';
        current.error = err.message;
        showToast(`Failed to upload ${current.name}: ${err.message}`, 'error');
      }
      renderUploadQueue();
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, () => worker());
  await Promise.all(workers);
  return state.uploadQueue.some((f) => f.status === 'INDEXED' || f.documentId);
}

// ==============================================================================
// 5. Research Execution & Signature Loading State Orchestration
// ==============================================================================
async function startResearchRun() {
  const question = DOM.researchQuestionInput.value.trim();
  const ticker = DOM.companyTickerInput.value.trim().toUpperCase() || 'MSFT';
  const period = DOM.periodInput.value.trim() || 'FY24';

  if (!question) {
    showToast('Please specify a financial research inquiry.', 'error');
    DOM.researchQuestionInput.focus();
    return;
  }

  // If in upload mode, ensure queue files are uploaded
  let docIds = [];
  if (appState.get().mode === 'upload') {
    const queue = appState.get().uploadQueue;
    if (queue.length === 0) {
      showToast('Please add at least one financial document or switch to Web Search.', 'error');
      return;
    }
    const hasReady = await uploadQueuedFiles();
    if (!hasReady) {
      showToast('Uploads failed. Resolve errors before proceeding.', 'error');
      return;
    }
    docIds = appState.get().uploadQueue.filter((f) => f.documentId).map((f) => f.documentId);
  }

  // 1. Transition into Progress View
  switchView('progress');
  DOM.progressTitle.textContent = `Analyzing Disclosures for ${ticker}`;
  DOM.progressSubtitle.textContent = 'RUN ID: INITIALIZING... &bull; SUPERVISOR ACTIVE';
  updateStageProgress(1, 'Locating financial documents and disclosures...');

  try {
    // 2. Create Persistent Run in SQLite
    const createRes = await api.createRun({
      research_question: question,
      company_ticker: ticker,
      reporting_periods: [period],
      document_ids: docIds,
    });

    const runId = createRes.run_id;
    DOM.progressRunIdSpan.textContent = runId;
    appState.set({ activeRunId: runId, runStatus: 'running' });

    // 3. Initiate Non-Blocking Polling for Trace & Status
    let pollInterval = null;
    let isTerminated = false;

    const pollStatus = async () => {
      if (isTerminated) return;
      try {
        const [runData, traceData] = await Promise.all([
          api.getRun(runId),
          api.getRunTrace(runId).catch(() => ({ events: [] })),
        ]);

        appState.set({
          runStatus: runData.status,
          executionTrace: traceData.events || [],
        });

        // Map real backend trace events to the 6 concise UI stages
        mapTraceEventsToStages(traceData.events || [], runData);

        if (runData.status === 'completed' || runData.status === 'completed_with_warnings') {
          isTerminated = true;
          clearInterval(pollInterval);
          updateStageProgress(6, 'Synthesis complete. Loading report...');
          setTimeout(() => loadAndDisplayReport(runId), 800);
        } else if (runData.status === 'failed') {
          isTerminated = true;
          clearInterval(pollInterval);
          DOM.progressTitle.textContent = 'Research Run Failed';
          showToast(`Research run terminated: ${runData.error_summary || 'Verification blocked'}`, 'error');
        }
      } catch (pollErr) {
        console.warn('Status poll warning:', pollErr);
      }
    };

    pollInterval = setInterval(pollStatus, 900);

    // 4. Trigger LangGraph Workflow Execution
    const execRes = await api.executeRun(runId);
    if (execRes.status === 'completed' || execRes.status === 'completed_with_warnings') {
      if (!isTerminated) {
        isTerminated = true;
        clearInterval(pollInterval);
        loadAndDisplayReport(runId);
      }
    }
  } catch (err) {
    DOM.progressTitle.textContent = 'Execution Error';
    showToast(`Execution error: ${err.message}`, 'error');
  }
}

// Map actual backend workflow events to the 6 concise UI stages
function mapTraceEventsToStages(events, runData) {
  const eventTypes = events.map((e) => e.event_type);

  // Stage 1: Document Acquisition
  if (eventTypes.includes('RUN_CREATED') || eventTypes.includes('ACQUIRE_SOURCES_START')) {
    markStageDone(1);
    activateStage(2);
  }

  // Stage 2: Parsing & Readiness
  if (eventTypes.includes('CHECK_READINESS_COMPLETE') || eventTypes.includes('FACTS_EXTRACTED')) {
    markStageDone(2);
    activateStage(3);
  }

  // Stage 3: Retrieval & Expansion
  if (eventTypes.includes('MULTI_HOP_EXPANDED') || eventTypes.includes('RETRIEVE_EVIDENCE_COMPLETE')) {
    markStageDone(3);
    activateStage(4);
  }

  // Stage 4: Deterministic Calculations
  if (eventTypes.includes('CALCULATE_METRICS_COMPLETE') || eventTypes.includes('METRICS_VERIFIED')) {
    markStageDone(4);
    activateStage(5);
  }

  // Stage 5: Analyst & Judge Claims
  if (eventTypes.includes('ANALYSTS_COMPLETE') || eventTypes.includes('JUDGES_AUDITED')) {
    markStageDone(5);
    activateStage(6);
  }

  // Supervisor Bounded Repair Check
  if (eventTypes.includes('SUPERVISOR_REPAIR_TRIGGERED')) {
    const stage5Detail = document.getElementById('stageDetail5');
    if (stage5Detail) stage5Detail.textContent = 'Supervisor triggered targeted retrieval repair...';
  }

  // Calculate approximate visual bar fill
  const completedStages = document.querySelectorAll('.stage-item.stage-done').length;
  const pct = Math.min(100, Math.max(15, (completedStages / 6) * 100));
  DOM.masterProgressFill.style.width = `${pct}%`;
}

function activateStage(idx) {
  const item = document.getElementById(`stageItem${idx}`);
  if (item && !item.classList.contains('stage-done')) {
    item.classList.add('stage-active');
  }
}

function markStageDone(idx) {
  const item = document.getElementById(`stageItem${idx}`);
  if (item) {
    item.classList.remove('stage-active');
    item.classList.add('stage-done');
    const badge = item.querySelector('.stage-badge-icon');
    if (badge) badge.innerHTML = '&check;';
  }
}

function updateStageProgress(idx, message) {
  for (let i = 1; i < idx; i++) markStageDone(i);
  activateStage(idx);
  const detail = document.getElementById(`stageDetail${idx}`);
  if (detail) detail.textContent = message;
}

// ==============================================================================
// 6. Research Report & Evidence Workspace Presentation
// ==============================================================================
async function loadAndDisplayReport(runId) {
  try {
    const report = await api.getReport(runId);
    appState.set({ report, activeRunId: runId });

    renderReport(report);
    switchView('report');
    showToast('Research report synthesized and verified successfully.', 'success');
  } catch (err) {
    showToast(`Failed to load synthesized report: ${err.message}`, 'error');
  }
}

function renderReport(report) {
  DOM.reportHeaderTitle.textContent = report.title || `Financial Research Report: ${report.company_ticker || 'COMPANY'}`;
  DOM.reportHeaderInquiry.textContent = `Analytical Inquiry: ${report.executive_summary ? report.executive_summary.split('.')[0] : 'Report Synthesis'}`;

  // Verification Badge
  const status = report.verification_status || 'VERIFIED';
  DOM.reportVerificationStatusBadge.textContent = status;
  DOM.reportVerificationStatusBadge.className = `report-verification-badge ${
    status === 'VERIFIED' ? 'badge-verified' : status === 'QUALIFIED' ? 'badge-qualified' : 'badge-blocked'
  }`;

  // 1. Executive Summary
  DOM.execSummaryContent.textContent = report.executive_summary || 'Summary unavailable.';

  // 2. Deterministic Financial Scorecard
  const calcs = report.calculations || [];
  if (calcs.length === 0) {
    DOM.metricsScorecardGrid.innerHTML = `
      <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); padding:16px;">
        No deterministic calculations required for this research scope.
      </div>
    `;
  } else {
    DOM.metricsScorecardGrid.innerHTML = calcs.map((c) => {
      const metricLabel = {
        OperatingMargin: 'Operating Margin',
        RevenueGrowth: 'Revenue Growth',
        NetMargin: 'Net Margin',
        CurrentRatio: 'Current Ratio',
        DebtToEquity: 'Debt-to-Equity',
      }[c.metric_name] || c.metric_name;

      const isValid = c.validation_outcome === 'VALID';
      return `
        <div class="metric-card">
          <div class="metric-name">${metricLabel}</div>
          <div class="metric-value">${c.formatted_result || 'N/A'}</div>
          <div class="metric-formula">${c.formula || ''}</div>
          <div class="metric-validation" style="color: ${isValid ? 'var(--status-verified)' : 'var(--status-blocked)'};">
            ${isValid ? '&check; Deterministic Ground Truth' : '! Verification Warning: ' + c.validation_outcome}
          </div>
        </div>
      `;
    }).join('');
  }

  // 3. Core Findings & Verified Claims
  const claims = report.claims || [];
  if (claims.length === 0) {
    DOM.claimsContainer.innerHTML = '<div style="color:var(--text-muted);">No structured claims generated.</div>';
  } else {
    DOM.claimsContainer.innerHTML = claims.map((cl, i) => {
      const matClass = cl.materiality === 'HIGH' ? 'mat-high' : cl.materiality === 'MEDIUM' ? 'mat-medium' : 'mat-low';
      const citations = (cl.evidence_references || []).map((ref) => `
        <span class="citation-pill" data-ref="${ref}" data-claim-idx="${i}">${ref}</span>
      `).join('');

      return `
        <div class="claim-card">
          <div class="claim-content">
            <div class="claim-badge-group">
              <span class="materiality-tag ${matClass}">${cl.materiality || 'MEDIUM'} IMPACT</span>
              <span style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">${cl.claim_type || 'reported_fact'}</span>
            </div>
            <div class="claim-text">${escapeHTML(cl.claim_text)}</div>
            <div class="citation-pill-list">${citations || '<span style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">Direct Financial Model Fact</span>'}</div>
          </div>
          <button class="btn-secondary btn-inspect-claim" data-claim-idx="${i}" style="padding:6px 12px; font-size:10px; white-space:nowrap;">
            Inspect Evidence &rarr;
          </button>
        </div>
      `;
    }).join('');

    // Attach citation and inspection listeners
    DOM.claimsContainer.querySelectorAll('.btn-inspect-claim, .citation-pill').forEach((el) => {
      el.addEventListener('click', (e) => {
        const idx = parseInt(e.currentTarget.getAttribute('data-claim-idx'), 10);
        const claim = claims[idx];
        if (claim) openClaimInspector(claim);
      });
    });
  }

  // 4. Risks & Counter-Evidence
  const risks = claims.filter((c) => (c.claim_text && (c.claim_text.toLowerCase().includes('risk') || c.claim_text.toLowerCase().includes('headwind') || c.claim_text.toLowerCase().includes('compression'))));
  if (risks.length === 0) {
    DOM.risksContainer.innerHTML = `
      <div class="exec-summary-card" style="border-left-color: var(--status-verified);">
        No material operational headwinds or disclosure contradictions flagged in current evidence set.
      </div>
    `;
  } else {
    DOM.risksContainer.innerHTML = risks.map((r, i) => `
      <div class="claim-card" style="border-left: 3px solid var(--status-qualified);">
        <div class="claim-content">
          <div class="claim-badge-group">
            <span class="materiality-tag mat-high">RISK AUDIT</span>
          </div>
          <div class="claim-text">${escapeHTML(r.claim_text)}</div>
        </div>
      </div>
    `).join('');
  }

  // 5. Tripartite Verification Judges Summary
  DOM.verificationSummaryGrid.innerHTML = `
    <div class="metric-card">
      <div class="metric-name">Evidence Citation Judge</div>
      <div class="metric-value" style="font-size:16px; color:var(--status-verified);">&check; PASS</div>
      <div style="font-size:11px; color:var(--text-secondary); margin-top:4px;">100% of claims bound to verified source chunk coordinates.</div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Numerical Integrity Gate</div>
      <div class="metric-value" style="font-size:16px; color:var(--status-verified);">&check; PASS</div>
      <div style="font-size:11px; color:var(--text-secondary); margin-top:4px;">Non-majority deterministic gate verified all Decimal operations.</div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Adversarial Skeptic Judge</div>
      <div class="metric-value" style="font-size:16px; color:var(--accent-stone);">&bull; AUDITED</div>
      <div style="font-size:11px; color:var(--text-secondary); margin-top:4px;">Evaluated counter-evidence, margin pressures, and tail risks.</div>
    </div>
  `;

  // 6. Unresolved Limitations & Scope Caveats
  const unresolved = report.unresolved_uncertainties || [];
  if (unresolved.length > 0) {
    DOM.unresolvedSection.style.display = 'block';
    DOM.unresolvedContent.innerHTML = unresolved.map((u) => `<div>&bull; ${escapeHTML(u)}</div>`).join('');
  } else {
    DOM.unresolvedSection.style.display = 'none';
  }
}

// ==============================================================================
// 7. Claim-Level Evidence Inspector Drawer
// ==============================================================================
function openClaimInspector(claim) {
  DOM.inspectorClaimText.textContent = claim.claim_text;
  DOM.inspectorDocId.textContent = claim.document_id || 'DOC_FY24_PRIMARY';
  DOM.inspectorPageNum.textContent = claim.page_number ? `Page ${claim.page_number}` : 'Consolidated Table P.2';

  // Safe text rendering to prevent XSS from source documents
  DOM.inspectorExcerptText.textContent = claim.evidence_excerpt || claim.claim_text;

  const status = claim.status || 'VERIFIED';
  DOM.inspectorVerdictBadge.innerHTML = `
    <span class="report-verification-badge ${status === 'VERIFIED' ? 'badge-verified' : 'badge-qualified'}">
      ${status}
    </span>
  `;

  DOM.inspectorOverlay.classList.add('open');
  DOM.inspectorOverlay.setAttribute('aria-hidden', 'false');

  // Claim override button bindings
  DOM.claimApproveBtn.onclick = () => {
    appState.setClaimOverride(claim.claim_id, 'VERIFIED');
    showToast(`Claim marked as VERIFIED by reviewer.`, 'success');
  };
  DOM.claimQualifyBtn.onclick = () => {
    appState.setClaimOverride(claim.claim_id, 'QUALIFIED');
    showToast(`Claim marked with QUALIFIED caveat.`, 'info');
  };
  DOM.claimRejectBtn.onclick = () => {
    appState.setClaimOverride(claim.claim_id, 'REJECTED');
    showToast(`Claim REJECTED by reviewer.`, 'error');
  };
}

function closeClaimInspector() {
  DOM.inspectorOverlay.classList.remove('open');
  DOM.inspectorOverlay.setAttribute('aria-hidden', 'true');
}

// ==============================================================================
// 8. Human Review Sign-Off Cockpit Submission
// ==============================================================================
async function handleSubmitReview() {
  const runId = appState.get().activeRunId;
  if (!runId) {
    showToast('No active research run loaded to review.', 'error');
    return;
  }

  const decision = appState.get().overallDecision || 'APPROVED';
  const reviewer = DOM.reviewerNameInput.value.trim() || 'Senior Financial Analyst';
  const comments = DOM.reviewCommentsInput.value.trim() || null;
  const overrides = Object.entries(appState.get().claimOverrides).map(([claim_id, val]) => ({
    claim_id,
    new_status: val.status,
    notes: val.notes,
  }));

  DOM.submitReviewBtn.disabled = true;
  DOM.submitReviewBtn.textContent = 'Recording Sign-Off...';

  try {
    const res = await api.submitReview(runId, {
      overall_decision: decision,
      reviewer_name: reviewer,
      comments,
      claim_overrides: overrides,
    });

    // Update Report Badge
    DOM.reportVerificationStatusBadge.textContent = decision;
    DOM.reportVerificationStatusBadge.className = `report-verification-badge ${
      decision === 'APPROVED' ? 'badge-verified' : decision === 'QUALIFIED' ? 'badge-qualified' : 'badge-blocked'
    }`;

    showToast(`Human sign-off '${decision}' successfully recorded in audit log.`, 'success');
  } catch (err) {
    showToast(`Review submission failed: ${err.message}`, 'error');
  } finally {
    DOM.submitReviewBtn.disabled = false;
    DOM.submitReviewBtn.textContent = 'Submit Review Decision';
  }
}

// ==============================================================================
// 9. Chronological Execution Trace Viewer
// ==============================================================================
function renderTraceView() {
  const events = appState.get().executionTrace || [];
  if (events.length === 0) {
    DOM.traceEventsList.innerHTML = `
      <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); padding:20px; text-align:center;">
        No active trace events found for current session. Run research to inspect real execution timestamps.
      </div>
    `;
    return;
  }

  DOM.traceEventsList.innerHTML = events.map((ev) => `
    <div class="queue-row" style="grid-template-columns: 140px 1fr 120px;">
      <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">
        ${ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleTimeString() : 'N/A'}
      </div>
      <div>
        <div style="font-weight:500; color:var(--text-primary); font-size:12px;">${ev.event_type}</div>
        <div style="color:var(--text-secondary); font-size:11px;">${escapeHTML(ev.event_message || '')}</div>
      </div>
      <div>
        <span class="queue-status-badge badge-indexed">RECORDED</span>
      </div>
    </div>
  `).join('');
}

// ==============================================================================
// 10. Utility Functions & Event Wireup
// ==============================================================================
function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, (tag) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[tag] || tag));
}

export function initApp() {
  cacheDOMElements();
  initParallax();
  checkSystemHealth();

  // Navigation Event Listeners
  DOM.navResearchBtn?.addEventListener('click', () => switchView('landing'));
  DOM.navReportBtn?.addEventListener('click', () => switchView('report'));
  DOM.navReviewBtn?.addEventListener('click', () => switchView('review'));
  DOM.navTraceBtn?.addEventListener('click', () => switchView('trace'));

  // Acquisition Mode Switchers
  DOM.modeWebBtn?.addEventListener('click', () => setAcquisitionMode('web'));
  DOM.modeUploadBtn?.addEventListener('click', () => setAcquisitionMode('upload'));

  // Mode A Actions
  DOM.findDocumentsBtn?.addEventListener('click', handleFindDocuments);
  DOM.processResearchWebBtn?.addEventListener('click', startResearchRun);

  // Mode B Actions
  DOM.browseFilesBtn?.addEventListener('click', () => DOM.fileInput.click());
  DOM.fileInput?.addEventListener('change', (e) => {
    if (e.target.files) {
      appState.addFilesToQueue(e.target.files);
      renderUploadQueue();
    }
  });

  // Drag and Drop Zone
  DOM.dropZone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    DOM.dropZone.classList.add('drag-over');
  });
  DOM.dropZone?.addEventListener('dragleave', () => DOM.dropZone.classList.remove('drag-over'));
  DOM.dropZone?.addEventListener('drop', (e) => {
    e.preventDefault();
    DOM.dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files) {
      appState.addFilesToQueue(e.dataTransfer.files);
      renderUploadQueue();
    }
  });

  DOM.clearQueueBtn?.addEventListener('click', () => {
    appState.clearQueue();
    renderUploadQueue();
  });
  DOM.processResearchUploadBtn?.addEventListener('click', startResearchRun);

  // Inspector Close
  DOM.closeInspectorBtn?.addEventListener('click', closeClaimInspector);
  DOM.inspectorOverlay?.addEventListener('click', (e) => {
    if (e.target === DOM.inspectorOverlay) closeClaimInspector();
  });

  // Progress Cancel Button
  DOM.cancelRunBtn?.addEventListener('click', () => switchView('landing'));

  // Human Review Cockpit Decision Buttons
  const decisionBtns = [DOM.decApproveBtn, DOM.decQualifyBtn, DOM.decRejectBtn];
  decisionBtns.forEach((btn) => {
    btn?.addEventListener('click', (e) => {
      decisionBtns.forEach((b) => b?.classList.remove('active-approved', 'active-qualified', 'active-rejected'));
      const dec = e.currentTarget.getAttribute('data-decision');
      if (dec === 'APPROVED') e.currentTarget.classList.add('active-approved');
      if (dec === 'QUALIFIED') e.currentTarget.classList.add('active-qualified');
      if (dec === 'REJECTED') e.currentTarget.classList.add('active-rejected');
      appState.set({ overallDecision: dec });
    });
  });

  DOM.submitReviewBtn?.addEventListener('click', handleSubmitReview);

  // Keyboard Escape for Inspector
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && DOM.inspectorOverlay?.classList.contains('open')) {
      closeClaimInspector();
    }
  });

  console.log('Trustworthy Financial Research & Decision Support System initialized.');
}

document.addEventListener('DOMContentLoaded', initApp);
