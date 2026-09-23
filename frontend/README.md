# Science Bank frontend

React 19 + Vite + TypeScript + Tailwind v4. See the repository README for setup.

- `API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev` — dev server proxying `/api` to a backend
- `npm run gen:api` — regenerate `src/api/schema.d.ts` from `openapi.json`
  (refresh that file first with `backend/.venv/bin/python backend/scripts/dump_openapi.py`)
- `npm run lint` / `npm run build`

Stimulus bodies, charts (hand-written SVG) and print views live in `src/components/Stimulus.tsx`,
`src/components/Chart.tsx` and `src/pages/Print.tsx`.
