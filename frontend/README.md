# Engineering RAG Assistant — Frontend

A polished React + TypeScript interface for the Engineering Document & Log Assistant backend.
Feels like a lightweight internal SaaS tool: clean card layout, animated transitions, live status indicators, and full source-attribution on every answer.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite 5 |
| Styling | Tailwind CSS v3 |
| Routing | React Router v6 |
| Data fetching | TanStack Query v5 |
| Icons | Lucide React |

No heavy UI library — the entire design system is hand-rolled in ~7 small primitive components so every pixel is intentional.

---

## Setup

### Prerequisites
- Node.js 18+
- The FastAPI backend running on `http://127.0.0.1:8000`

### Mac / Linux
```bash
cd frontend
cp .env.example .env      # backend URL is already set correctly for local dev
npm install
npm run dev               # → http://localhost:3000
```

### Windows PowerShell
```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open **http://localhost:3000** — the app auto-reloads on file changes.

### Production build
```bash
npm run build   # outputs to frontend/dist/
npm run preview # serve the production build locally
```

---

## Pages & API Mapping

| Page | Route | Backend Endpoints |
|---|---|---|
| Dashboard | `/` | `GET /health`, `GET /documents` |
| Upload | `/upload` | `POST /ingest` |
| Document Library | `/documents` | `GET /documents`, `DELETE /documents/{id}` |
| Semantic Search | `/search` | `POST /search` |
| Ask a Question | `/ask` | `POST /ask` |

The sidebar calls `GET /health` every 30 seconds in the background and shows a live backend/LLM status indicator — no user action needed.

---

## Configuration

Copy `.env.example` to `.env` and adjust if your backend runs on a different host:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

All `VITE_` variables are inlined at build time by Vite and exposed via `import.meta.env`.

---

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # Typed fetch wrapper — all API calls live here
│   ├── types/
│   │   └── index.ts           # Response types + visual config (colors, formatters)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Layout.tsx     # Sidebar + scrollable main area
│   │   │   └── Sidebar.tsx    # Nav, branding, live health indicator
│   │   └── ui/                # Reusable primitives
│   │       ├── Badge.tsx      # File-type and status badges
│   │       ├── Button.tsx     # Primary / secondary / danger / ghost variants
│   │       ├── Card.tsx       # White card with optional accent border
│   │       ├── ConfirmDialog.tsx  # Modal delete confirmation
│   │       ├── EmptyState.tsx     # Illustrated empty / zero-data states
│   │       ├── ScoreBar.tsx       # Colour-coded similarity score bar
│   │       └── Spinner.tsx        # Inline loading spinner
│   └── pages/
│       ├── DashboardPage.tsx  # Stats, quick actions, workflow, recent docs
│       ├── UploadPage.tsx     # Drag-and-drop file ingestion
│       ├── DocumentsPage.tsx  # Filterable document grid with delete
│       ├── SearchPage.tsx     # Semantic chunk retrieval with score display
│       └── AskPage.tsx        # Full RAG QA with source attribution
├── .env.example
├── index.html
├── package.json
├── tailwind.config.js
└── vite.config.ts
```

---

## Design Decisions

**Dark sidebar, light content** — the contrast immediately communicates sidebar = navigation, main area = work surface. Matches the visual language of tools like Linear and Vercel.

**Score colour coding** — similarity scores use a 4-tier colour scale (emerald / blue / amber / slate) consistently across both the Search and Ask pages. The same thresholds drive the bar fill colour and the numeric label, so the visual and literal information always agree.

**TanStack Query for all server state** — loading, error, and stale states are handled uniformly without any manual `useState` flag juggling. `queryClient.invalidateQueries` after mutations keeps the Documents count and Dashboard stats in sync automatically.

**LLM-optional design is surfaced in the UI** — the sidebar footer shows either "LLM enabled" (blue) or "Retrieval mode" (amber), and the Ask page answer card changes its accent colour and label to match. A user with no API key gets a clear, honest fallback experience instead of a confusing empty state.

**No proxy, direct CORS** — the backend enables `allow_origins=["*"]`, so the frontend calls it directly. The `VITE_API_BASE_URL` variable makes it trivial to point the same build at staging or production.

---

## What "Backend offline" means

When the sidebar shows **Backend offline** it means the frontend cannot reach `VITE_API_BASE_URL`. To fix it:

1. Make sure the FastAPI server is running: `uvicorn app.main:app --reload --port 8000` (from the project root)
2. Check that `VITE_API_BASE_URL` in `frontend/.env` matches the actual backend address
3. Reload the browser — the health check retries automatically every 30 s
