# How it works (for developers)

[← Overview](../../README.md)

This page is for people who change the code. Researchers who only run studies do not need it.

## Architecture

```
Qualtrics page (Qualtrics.js)
   │  POST {route: "next", payload: {session_id, interview_id, user_message, session, signature}}
   ▼
Cloudflare Worker (Python, src/entry.py → interviewer.service.dispatch)
   │  chat/completions over fetch
   ▼
OpenAI / Gemini / Claude (OpenAI-compatible endpoints)
```

- **Stateless.** The worker keeps nothing between requests. The whole session history travels with every request and comes back with an HMAC signature (`interviewer/state.py`). The signing key is `SESSION_SECRET`, or a digest of the active provider key if that is unset. A tampered or foreign session is rejected.
- **Storage.** The Qualtrics page writes the transcript and graphs into embedded data (main copy). Values above 15,000 bytes are split into `_1` … `_5`. If the `DB` binding exists, every turn is also upserted into the D1 table `sessions` (`interviewer/storage.py`). The table is created on first use.
- **Interviews** are TOML files in `src/interviews/`, loaded and validated once at worker start (`interviewer/config.py`). A broken file makes the start fail, so Cloudflare keeps the previous deployment. Files starting with `_` are skipped.
- **No pip packages.** The worker uses only the standard library plus the Workers runtime. The compatibility flag `disable_python_external_sdk` is required for that; see the comments in `wrangler.jsonc`. All three providers are called through their OpenAI-compatible chat endpoints with the built-in `fetch` (`interviewer/providers.py`). Gemini audio uses the native `generateContent` endpoint; OpenAI audio uses Whisper with a hand-built multipart body.
- **Settings.** `env_text` treats an unset, empty or `none` value as unset. That is why the Deploy form can pre-fill every secret with `none`.

## Modules

| File | Role |
|---|---|
| `src/entry.py` | Workers entrypoint. Converts the request, calls `dispatch`, converts the result. |
| `interviewer/service.py` | Routing, input limits, signature checks, `/export`. Runs under plain CPython. |
| `interviewer/logic.py` | One interview turn: moderate, record, then probe, transition (with optional DAG step) or closing question. |
| `interviewer/manager.py` | The session history list and its counters. |
| `interviewer/agent.py`, `auxiliary.py` | Prompt filling and the LLM agents (probe, transition, summary, moderator). |
| `interviewer/dag_agent.py`, `svg_generator.py` | Causal graph extraction and its SVG rendering. |
| `interviewer/providers.py` | HTTP client for the three providers, with retries on 429 and 5xx. |
| `interviewer/test_page.py` | The page at `/test/<interview_id>`. |
| `qualtrics/*/Qualtrics.{html,js}` | The chat embedded in Qualtrics. |
| `qualtrics/build_qsf.py` | Builds the importable `.qsf` files from the HTML and JS. |

## Routes

| Method and path | Purpose |
|---|---|
| `GET /` | `Running!` |
| `GET /healthcheck` | `ok` |
| `GET /interviews` | IDs of the loaded interviews |
| `GET /test/<interview_id>` | Browser test page |
| `GET /export?password=...` | CSV of all D1 turns. 404 unless `ADMIN_PASSWORD` and `DB` are set. |
| `POST /` | Qualtrics dispatcher: `{"route": "next" or "transcribe", "payload": {...}}` |
| `POST /next` | Next interviewer message |
| `POST /transcribe` | `{"audio": "<base64 webm>"}` → text |

## Local development

Requirements: Node.js 20 or later, Python 3.11 or later (for `tomllib` in the tests).

```bash
npm install
cp .dev.vars.example .dev.vars   # put one real API key in, keep the rest "none"
npm run dev                      # http://127.0.0.1:8791/test/STOCK_MARKET
npm test                         # unit tests under plain CPython
```

`wrangler dev` uses a local D1 database. Deploy from your machine with `npm run deploy` (after `npx wrangler login`).

## Changing the Qualtrics files

Edit `qualtrics/without_voice/Qualtrics.{html,js}` or `qualtrics/with_voice/…`, then rebuild the import files:

```bash
python3 qualtrics/build_qsf.py
```

Qualtrics is strict about the QSF format. These details were found by trial and are kept in `build_qsf.py`:

- Survey, block and owner IDs are a prefix plus 15 letters or digits (`SV_`, `BL_`, `UR_`).
- `SurveyEntry.SurveyOwnerID` and `CreatorID` must match `^URH?_[a-zA-Z0-9]{11,15}$`. `SurveyBrandID` must not be empty.
- The elements `PROJ`, `QC`, `RS` and `SCO` must exist. Blocks other than the default block use flow type `Standard`.

## Deploy to Cloudflare button

- The form pre-fills secret fields from `.dev.vars.example`. Its field descriptions come from `package.json` → `cloudflare.bindings`.
- The `LLM_PROVIDER` value the user types is written into `wrangler.jsonc` of the new repository.
- Cloudflare caches the form per URL. The `/tree/<ref>` part must name a branch; a commit SHA fails at clone time.

## Origin

The interview logic follows Chopra & Haaland (2023), *Conducting Qualitative Interviews with AI*, CESifo Working Paper No. 10666, originally a Flask app. The DAG agent and this Cloudflare port are additions.
