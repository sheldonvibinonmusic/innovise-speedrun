# Frontend Architecture & Setup

## Overview

The user interface is a custom, professional financial research and analyst-review cockpit built using **vanilla HTML5, CSS3, and standard ES modules (JavaScript)**.

To adhere to the 6-hour rapid implementation constraints and maintain absolute architectural transparency:
- **No Heavy Frameworks**: No React, Vue, Angular, or Next.js build overhead.
- **No Streamlit**: Avoids monolithic Python UI limitations, allowing clean separation of concerns and independent backend execution.
- **No CDN Dependencies**: Zero external runtime script requirements; everything runs locally.

---

## Communication with FastAPI Backend

The frontend communicates with the FastAPI backend exclusively via standard `fetch()` API calls defined in `assets/js/api.js`.

- **API Base URL**: Configured in `assets/js/api.js` (default: `http://127.0.0.1:8000/api`).
- **Data Exchange**: All communication uses standard JSON or `multipart/form-data` (for PDF uploads).
- **Polling / Updates**: The frontend polls `GET /api/runs/{run_id}` to track asynchronous analysis stages and retrieve draft reports.

---

## Directory Organization

```
frontend/
├── index.html                  # Semantic single-page application shell
├── README.md                   # Frontend architecture and communication guide
└── assets/
    ├── css/
    │   ├── styles.css          # Core layouts, variables, reset, and typography
    │   └── components.css      # UI component styling (claim cards, evidence drawer)
    ├── js/
    │   ├── app.js              # Application entry point & router
    │   ├── api.js              # HTTP client and API endpoint abstractions
    │   ├── state.js            # Central reactive application state store
    │   ├── pages/
    │   │   ├── research.js     # Company discovery and research run trigger
    │   │   ├── documents.js    # Document upload and ingestion vault
    │   │   ├── reports.js      # Financial report viewer and scorecard
    │   │   └── review.js       # Human-in-the-loop audit and sign-off cockpit
    │   └── components/
    │       ├── workflow-status.js # Live LangGraph progress indicator
    │       ├── evidence-panel.js  # Side-by-side source PDF excerpt viewer
    │       ├── claim-card.js      # Claim verification card with gate badges
    │       ├── financial-charts.js# Lightweight SVG/CSS financial metric visuals
    │       └── review-controls.js # Approval, override, and comment controls
    └── images/
        └── .gitkeep
```

---

## Running the Frontend

Run a lightweight static server from the project root:
```bash
python -m http.server 3000 --directory frontend
```
The interface is accessible at `http://localhost:3000`.
