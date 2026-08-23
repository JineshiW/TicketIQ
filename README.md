# TicketIQ — React Client

Modular React + TypeScript + Vite front-end for the TicketIQ FastAPI backend
(Qdrant + Sentence-Transformers + Ollama + LangGraph). Runs entirely on
localhost — no cloud, no deployment tooling, no external services.

## Requirements

- Node.js 18+
- The FastAPI backend running locally:
  `uvicorn main:app --reload --port 8000`

## Run

```bash
npm install
npm run dev      # http://localhost:5173
```

Vite proxies every `/api/*` call to `http://127.0.0.1:8000`, so you do not
need CORS middleware in FastAPI. To point at a different backend, copy
`.env.example` to `.env` and set `VITE_API_BASE_URL`.

## Scripts

| Command           | Description                     |
| ----------------- | ------------------------------- |
| `npm run dev`     | Dev server with API proxy       |
| `npm run build`   | Type-check + production bundle  |
| `npm run preview` | Serve the built bundle locally  |

## Architecture

```
src/
  api/                 One module per backend area (thin fetch wrapper)
    client.ts          fetch + error normalisation (ApiError)
    tickets.ts         POST /tickets, /tickets/batch, /tickets/similar, /tickets/similar/batch
    clusters.ts        GET /clusters, GET /clusters/reviews, POST /clusters/reviews/{sig}/decide
    agent.ts           POST /agent/check-patterns, POST /agent/resume/{thread_id}
  components/          Reusable presentational primitives (Card, Badge, StatCard, States, Layout)
    charts/            Dependency-free SVG charts (scatter, donut, bar)
  features/
    submit/            Ticket submission + similarity search (hook + components)
    patterns/          Clustering, human review, agentic check (hook + components)
  hooks/useAsync.ts    useAsyncAction / useAsyncResource
  lib/                 Pure helpers: formatting, cluster statistics
  pages/               Route-level composition only
  styles/global.css    Design tokens + component classes (single source of styling truth)
  types.ts             Mirrors the FastAPI Pydantic models 1:1
```

Rules the codebase follows:

- Components never call `fetch` directly — always through `src/api`.
- Feature hooks own state and orchestration; components stay presentational.
- No hardcoded colours in components; everything reads CSS variables.

## Endpoint coverage

| Backend endpoint                          | Where it is used                       |
| ----------------------------------------- | -------------------------------------- |
| `POST /tickets`                            | Submit page → "Store ticket"           |
| `POST /tickets/batch`                      | Submit page → multiple drafts stored   |
| `POST /tickets/similar`                    | Submit page → "Check Similarity"       |
| `POST /tickets/similar/batch`              | Submit page → multiple drafts checked  |
| `GET /clusters`                            | Patterns page → visualisation + charts |
| `GET /clusters/reviews`                    | Patterns page → stats + review table   |
| `POST /clusters/reviews/{signature}/decide`| Review table → Approve / Reject        |
| `POST /agent/check-patterns`               | Patterns page → agentic check          |
| `POST /agent/resume/{thread_id}`           | Patterns page → human decision resume  |

Note: `decide` and `resume` send `decision` as a **query parameter**, matching
the FastAPI signatures exactly.
