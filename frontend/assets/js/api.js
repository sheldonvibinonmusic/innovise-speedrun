/**
 * API Client & Network Boundary
 * Trustworthy Multi-Agent Financial Research System
 *
 * PHASE 0 STATUS: Scaffolding only.
 * In Phase 4, this module will provide type-safe fetch wrappers for all
 * endpoints specified in API_CONTRACT.md:
 * - GET  /api/health
 * - POST /api/runs
 * - GET  /api/runs/{run_id}
 * - POST /api/documents/upload
 * - POST /api/company/discover
 * - GET  /api/reports/{run_id}
 * - GET  /api/runs/{run_id}/trace
 * - POST /api/runs/{run_id}/review
 */

const API_BASE_URL = 'http://127.0.0.1:8000/api';

export const api = {
  baseUrl: API_BASE_URL,

  // TODO (Phase 4): Implement fetch helper with JSON deserialization and error boundary
  async request(endpoint, options = {}) {
    throw new Error('API client not implemented in Phase 0 scaffolding.');
  }
};
