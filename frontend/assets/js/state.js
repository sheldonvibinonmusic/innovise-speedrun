/**
 * Central State Store & Event Bus
 * Trustworthy Multi-Agent Financial Research System
 *
 * Manages explicit application state across:
 * - Active view & acquisition modes (Web Search vs Document Upload)
 * - File upload queue (with concurrent batching up to 300 files)
 * - Discovery manifests
 * - Active research run lifecycle and trace history
 * - Generated report and claim-level evidence inspector
 * - Human review decisions
 */

class AppState {
  constructor() {
    this.state = {
      // Navigation & Layout
      mode: 'web', // 'web' | 'upload'
      currentView: 'landing', // 'landing' | 'progress' | 'report' | 'review' | 'trace'

      // Mode A Discovery State
      discoveryInput: 'MSFT',
      discoveryJurisdiction: 'US',
      discoveryLoading: false,
      discoveryManifest: null,
      discoveryError: null,

      // Mode B Upload Queue
      uploadQueue: [], // Array of { id, file, name, size, type, status, percent, documentId, error }
      isUploading: false,
      concurrencyLimit: 3,

      // Research Run Execution
      researchQuestion: 'Analyze operating profitability, revenue trajectory, and key operational risks.',
      companyTicker: 'MSFT',
      reportingPeriod: 'FY24',
      activeRunId: null,
      runStatus: 'idle', // 'idle' | 'running' | 'completed' | 'completed_with_warnings' | 'failed'
      currentStage: 'idle',
      currentStageIndex: 0,
      runProgressPercent: 0,
      executionTrace: [],
      runError: null,

      // Report & Evidence Inspector
      report: null,
      selectedClaim: null,
      isInspectorOpen: false,

      // Human Review Cockpit
      reviewerName: '',
      overallDecision: 'APPROVED', // 'APPROVED' | 'QUALIFIED' | 'REJECTED'
      reviewComments: '',
      claimOverrides: {}, // { [claimId]: { status: 'VERIFIED'|'REJECTED'|'QUALIFIED', notes: string } }
      isReviewSubmitting: false,
      reviewOutcome: null,

      // System Health
      isBackendHealthy: true,
      lastHealthCheck: null,
    };

    this.listeners = new Set();
  }

  get(key) {
    if (key === 'currentRunId') {
      return this.state.activeRunId || this.state.report?.run_id || null;
    }
    if (key && typeof key === 'string') {
      return this.state[key];
    }
    return this.state;
  }

  set(partial) {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...partial };
    this.notify(this.state, prevState);
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify(state, prevState) {
    for (const listener of this.listeners) {
      try {
        listener(state, prevState);
      } catch (err) {
        console.error('State subscriber error:', err);
      }
    }
  }

  // Helper Methods
  setMode(mode) {
    this.set({ mode });
  }

  setView(currentView) {
    this.set({ currentView });
  }

  addFilesToQueue(fileList) {
    const currentQueue = [...this.state.uploadQueue];
    const maxFiles = 300;

    for (const file of Array.from(fileList)) {
      if (currentQueue.length >= maxFiles) break;

      // Duplicate check by name and size
      const exists = currentQueue.some((q) => q.name === file.name && q.size === file.size);
      if (exists) continue;

      const ext = file.name.split('.').pop().toLowerCase();
      const isPdf = file.type === 'application/pdf' || ext === 'pdf';
      const isPptx = ext === 'pptx' || file.type.includes('presentation');

      currentQueue.push({
        id: `file_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
        file,
        name: file.name,
        size: file.size,
        type: isPdf ? 'PDF' : isPptx ? 'PPTX' : 'UNKNOWN',
        isValidType: isPdf || isPptx,
        status: isPdf || isPptx ? 'QUEUED' : 'REJECTED',
        percent: 0,
        documentId: null,
        error: isPdf || isPptx ? null : 'Only PDF and PowerPoint (.pptx) files are supported.',
      });
    }

    this.set({ uploadQueue: currentQueue });
  }

  removeFileFromQueue(fileId) {
    const uploadQueue = this.state.uploadQueue.filter((f) => f.id !== fileId);
    this.set({ uploadQueue });
  }

  clearQueue() {
    this.set({ uploadQueue: [] });
  }

  openInspector(claim) {
    this.set({ selectedClaim: claim, isInspectorOpen: true });
  }

  closeInspector() {
    this.set({ selectedClaim: null, isInspectorOpen: false });
  }

  setClaimOverride(claimId, newStatus, notes = '') {
    const claimOverrides = {
      ...this.state.claimOverrides,
      [claimId]: { status: newStatus, notes },
    };
    this.set({ claimOverrides });
  }
}

export const appState = new AppState();
export const state = appState; // Backwards compatible alias
