/**
 * Central Client State Store
 * Trustworthy Multi-Agent Financial Research System
 *
 * PHASE 0 STATUS: Scaffolding only.
 * In Phase 4, this module will manage reactive state for:
 * - Active selected company & document list
 * - Current research run ID and live execution status
 * - Loaded report, claim registry, and evidence viewer state
 * - Human review decisions and override queue
 */

export const state = {
  activeTab: 'research',
  currentCompany: null,
  activeRunId: null,
  runStatus: null,
  documents: [],
  currentReport: null,
  selectedClaim: null,
  reviewDecisions: {}
};
