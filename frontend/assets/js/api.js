/**
 * API Client & Network Boundary
 * Trustworthy Multi-Agent Financial Research System
 *
 * Implements type-safe fetch & XHR wrappers for all backend contracts:
 * - GET  /api/health
 * - POST /api/company/discover
 * - POST /api/documents/upload
 * - POST /api/documents/{document_id}/process
 * - POST /api/runs
 * - POST /api/runs/{run_id}/execute
 * - GET  /api/runs/{run_id}
 * - GET  /api/runs/{run_id}/trace
 * - GET  /api/reports/{run_id}
 * - POST /api/runs/{run_id}/review
 */

// Determine API base URL dynamically or from runtime config
function resolveApiBaseUrl() {
  if (typeof window !== 'undefined' && window.__APP_CONFIG__?.apiBaseUrl) {
    return window.__APP_CONFIG__.apiBaseUrl.replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined') {
    // If frontend is served directly by FastAPI (e.g. at /ui or /), use same origin
    if (window.location.port === '8000' || window.location.pathname.startsWith('/ui')) {
      return `${window.location.origin}/api`;
    }
  }
  return 'http://127.0.0.1:8000/api';
}

export const API_BASE_URL = resolveApiBaseUrl();

class ApiClient {
  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.timeoutMs = 60000;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs || this.timeoutMs);

    const headers = {
      Accept: 'application/json',
      ...options.headers,
    };

    if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = { message: text };
      }

      if (!response.ok) {
        const errorMsg = data?.error?.message || data?.detail || `HTTP ${response.status}: ${response.statusText}`;
        const err = new Error(errorMsg);
        err.status = response.status;
        err.data = data;
        err.code = data?.error?.code || 'API_ERROR';
        throw err;
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        const timeoutErr = new Error(`Request timed out after ${this.timeoutMs / 1000}s.`);
        timeoutErr.code = 'TIMEOUT';
        throw timeoutErr;
      }
      throw err;
    }
  }

  // --- Health Check ---
  async checkHealth() {
    return this.request('/health', { method: 'GET' });
  }

  // --- Acquisition Mode A: Company / Permitted Website Discovery ---
  async discoverCompany(companyNameOrTicker, options = {}) {
    const jurisdiction = typeof options === 'string' ? options : (options.jurisdiction || 'US');
    const period = typeof options === 'object' ? (options.period || null) : null;
    const websiteUrl = typeof options === 'object' ? (options.websiteUrl || null) : null;
    const filingTypes = typeof options === 'object' && options.filingTypes ? options.filingTypes : ['10-K', '10-Q'];

    return this.request('/company/discover', {
      method: 'POST',
      body: {
        ticker_or_cik: companyNameOrTicker,
        company_name_or_ticker: companyNameOrTicker,
        jurisdiction,
        period,
        website_url: websiteUrl,
        filing_types: filingTypes,
      },
    });
  }

  // --- Acquisition Mode B: Upload Document with Real Byte-Progress Tracking ---
  uploadFile(file, { companyTicker = 'UNKNOWN', reportingPeriod = 'FY24', processNow = false } = {}, onProgress = null) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${this.baseUrl}/documents/upload`;

      xhr.open('POST', url, true);
      xhr.setRequestHeader('Accept', 'application/json');

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress({
              loaded: event.loaded,
              total: event.total,
              percent,
            });
          }
        };
      }

      xhr.onload = () => {
        let respData;
        try {
          respData = JSON.parse(xhr.responseText);
        } catch (_) {
          respData = { message: xhr.responseText };
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(respData);
        } else {
          const err = new Error(respData?.error?.message || respData?.detail || `Upload failed with status ${xhr.status}`);
          err.status = xhr.status;
          err.data = respData;
          reject(err);
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error occurred during document upload.'));
      };

      xhr.ontimeout = () => {
        reject(new Error('Upload timed out.'));
      };

      const formData = new FormData();
      formData.append('files', file);
      if (companyTicker) formData.append('company_ticker', companyTicker);
      if (reportingPeriod) formData.append('reporting_period', reportingPeriod);
      formData.append('process_now', processNow ? 'true' : 'false');

      xhr.send(formData);
    });
  }

  // --- Trigger Document Ingestion & Parsing ---
  async processDocument(documentId) {
    return this.request(`/documents/${encodeURIComponent(documentId)}/process`, {
      method: 'POST',
    });
  }

  // --- Document Details ---
  async getDocument(documentId) {
    return this.request(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'GET',
    });
  }

  // --- Document Page Summaries & Assessment ---
  async getDocumentPages(documentId) {
    return this.request(`/documents/${encodeURIComponent(documentId)}/pages`, {
      method: 'GET',
    });
  }

  // --- Research Run Lifecycle ---
  async createRun(payload) {
    return this.request('/runs', {
      method: 'POST',
      body: payload,
    });
  }

  async executeRun(runId) {
    return this.request(`/runs/${encodeURIComponent(runId)}/execute`, {
      method: 'POST',
      timeoutMs: 120000, // LangGraph execution can take time
    });
  }

  async getRun(runId) {
    return this.request(`/runs/${encodeURIComponent(runId)}`, {
      method: 'GET',
    });
  }

  async getRunTrace(runId) {
    return this.request(`/runs/${encodeURIComponent(runId)}/trace`, {
      method: 'GET',
    });
  }

  // --- Research Report Retrieval & Export ---
  async getReport(runId) {
    return this.request(`/reports/${encodeURIComponent(runId)}`, {
      method: 'GET',
    });
  }

  getReportPdfUrl(runId) {
    let cleanId = runId;
    if (typeof cleanId === 'object' && cleanId !== null) {
      cleanId = cleanId.run_id || cleanId.activeRunId || cleanId.id || '';
    }
    return `${this.baseUrl}/reports/${encodeURIComponent(String(cleanId || '').trim())}/export/pdf`;
  }

  // --- Human Review Sign-Off Cockpit ---
  async submitReview(runId, payload) {
    return this.request(`/runs/${encodeURIComponent(runId)}/review`, {
      method: 'POST',
      body: payload,
    });
  }
}

export const api = new ApiClient();
