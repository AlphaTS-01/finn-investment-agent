# FINN — investment research with network context

Mobile-first web application for on-demand company research, primary-document caching, portfolio announcements, EOD alerts and professional network context.

Read [the submission writeup](SUBMISSION.md) for product decisions, architecture, privacy and limitations.

## Run

Python 3.12 recommended. On Windows, use a Windows Python installation rather than MSYS Python.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Copy .env.example to .env ONLY on a fresh checkout, then supply your own keys.
.\start.ps1
```

Open http://127.0.0.1:8000/ for the responsive frontend, or http://127.0.0.1:8000/docs for interactive API requests. This is a single-investor local prototype, not an authenticated public deployment. Bind to localhost. Public hosting needs authentication, investor isolation, request budgets and background research jobs first.

## Frontend

Buildless HTML/CSS/JavaScript in `frontend/`, served by the same FastAPI process. No Node installation is required.

- Today: selectable time window, company filter, priority cards, collapsed routine filings, original filing dialog and contextual research navigation.
- Research: any NSE ticker, suggested questions, cited answers, expandable source excerpts, and explicit partial/error/loading states.
- Settings: persistent watchlist, price/volume thresholds, and Important / Briefing only / Custom alert modes. Preferences affect interruptions; all filings remain accessible.
- Network: persistent contacts with career history, education and major, expertise, sectors, introductions and last-contact dates. Search and contextual recommendations explain their recorded evidence. Optional synthetic demo contacts are visibly labeled.
- Responsive sidebar becomes bottom navigation on narrow screens. Google Fonts enhance typography; local serif/sans-serif fallbacks remain available.

The briefing uses existing cached snapshots immediately, explicitly marking old snapshots as stale. The Refresh brief button requests fresh exchange data. Initial uncached windows may take longer. Event-to-research navigation retrieves the actual selected filing as evidence and reports whether it was included.

## Try the pipeline

1. `GET /health` checks configuration without exposing credentials.
2. `GET /companies/TCS/announcements?days=7` retrieves a rolling seven-day exchange window.
3. `GET /companies/TCS/prices` returns completed EOD bars, daily change and volume relative to the preceding 20 sessions.
4. `GET /companies/TCS/documents` discovers annual reports and earnings-call transcripts on demand.
5. `POST /research` with `{"ticker":"TCS","question":"What did management say about demand and revenue growth?","max_documents":2}` downloads and parses evidence, then returns model claims with source IDs, URLs, pages and excerpts.
6. Repeat research to exercise the answer cache. Change the question to reuse the document cache.
7. Try an outside ticker such as `ASIANPAINT`. Research does not add it to the portfolio.
8. `PUT /portfolio/ASIANPAINT` adds a tracked company. `GET /briefing?days=7` includes portfolio announcements.

`PUT /settings/alerts` configures thresholds and categories. `POST /refresh` performs one monitoring cycle. `GET /alerts` returns deduplicated in-app alerts.

The API starts its background worker automatically. It polls sources every 15 minutes and processes a durable SQLite analysis queue even when the browser is closed. Keep the API running; use a single API process for this local prototype. Source polling and analysis run separately so a slow exchange request does not stop queued work.

`POST /monitors` saves a company/question monitor; GET lists monitors and worker status; DELETE removes one. The first company observation establishes a baseline. Subsequent unseen filing IDs trigger analysis even if their publication timestamps are older. Relevant monitor updates include exact supporting quotes; identical document hashes do not generate duplicate monitor alerts. Briefing-only mode keeps updates in Settings without creating alerts. No email or device notifications are sent.

Jobs retry up to three times, with five-minute backoff and ten-minute recovery leases. Source failures remain visible. A seven-day overlapping observation window cannot recover filings that arrive outside that window.

## Sources and caching

- BSE via `bse`; NSE via `nse` on BSE failure. Sources are unofficial clients over exchange endpoints. Window results cache for five minutes. Unavailable sources are distinguished from an empty window; a dated cache may be returned as stale.
- Yahoo Finance via `yfinance`: one-hour cache, unadjusted closes, completed sessions only. Corporate actions can cause apparent price moves; action-aware adjustment is not implemented yet.
- Screener public document links: six-hour discovery cache. Tavily is a fallback locator, restricted to exchange/company domains. Search snippets are never used as research evidence.
- Actual primary PDFs: downloaded with byte limits, extracted page-by-page with `pypdf`, and cached seven days by URL plus content hash. Scanned PDFs without text return an explicit OCR limitation.
- Gemini: receives research questions and selected primary-document excerpts; the explicit profile-import action also sends the supplied professional profile text for extraction. Saved network matching runs locally. Answers cache for 24 hours keyed by ticker, question, source hashes, model and pipeline version.
- Default model: `gemini-3.1-flash-lite`, verified with the configured account. Model availability is account-dependent; override `GEMINI_MODEL` if needed.
- Failed PDF downloads are cached for 15 minutes to avoid repeatedly fetching oversized/unavailable documents. `refresh=true` bypasses this.
- Data and PDFs live in `data/` (gitignored). Secrets stay in `.env` (gitignored). `.env.example` has no secrets.

## Coverage and limits

- Announcement priority uses transparent subject-based rules. Today groups same-day results-related filings while retaining original links, with three attention tiers and an all-filings view. Selected filing analysis adds quoted summaries, disclosed executive background and comparable quarterly Revenue/EBITDA/PBT/PAT when extractable. Exact quotes and numerical presence are checked, but table interpretation still needs review; missing figures are marked unverified. Only selected PDF pages are analyzed.
- Research uses explicit topic/period routing to select event filings, annual reports and transcripts. Recent event discovery covers 90 days; historical document selection uses available title/date metadata. Comparisons remain partial until period coverage is established. It cannot claim exhaustive four-quarter analysis.
- Retrieval uses term matching with a few synonyms, not embeddings. Claim quotes and numerical presence are checked, but that does not establish factual entailment or financial accuracy.
- Network matching uses recorded professional details and explicit introduction paths. Shared affiliations are possible overlaps, not proof that two people know each other. LinkedIn import tries the public page, then Tavily indexed content for the exact same profile URL. Indexed drafts are labeled potentially incomplete/outdated; same-name profiles are rejected. Pasted text and manual entry remain available. Imports produce editable drafts and never save automatically.
- No OCR, multi-user security, cross-exchange event grouping, automatic retention cleanup or distributed rate limiting yet.
- Exchange/source availability is not guaranteed. No paywalls or blocked endpoints are bypassed.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests isolate their SQLite databases and do not call paid APIs. Live verification is recorded separately in `VERIFICATION.md`.

## Upstream components

No third-party application repository was copied. We use published packages: [bse](https://github.com/BennyThadikaran/BseIndiaApi) and [nse](https://github.com/BennyThadikaran/NseIndiaApi) (GPL-3.0), [yfinance](https://github.com/ranaroussi/yfinance) (Apache-2.0), [pypdf](https://github.com/py-pdf/pypdf) (BSD-3-Clause), FastAPI, HTTPX, Beautiful Soup and python-dotenv. Review upstream license obligations before distributing the combined application. Software licenses do not grant rights to redistribute source financial data.

## Network API

`GET /network`, `POST /network/contacts`, `PUT /network/contacts/{id}`, and `DELETE /network/contacts/{id}` manage local contacts. `POST /network/prefill` drafts fields from a public LinkedIn URL or pasted profile text. `GET /network/matches` accepts ticker and query; `/network/contacts/{id}/overlaps` lists possible shared affiliations. `POST /network/demo` adds twelve labeled synthetic examples. `GET /events/{id}/analysis` reads the selected primary filing.

## Company search

Research and watchlist inputs suggest symbols and company names as you type. `/companies/search?q=tata` searches the official NSE equity CSV, cached for one day; a stale cache remains available during outages. Exact symbols rank first, then symbol/name prefixes, word prefixes, and substrings. This is name matching, not a corporate-group ownership database. Arrow keys and Enter select a suggestion; direct ticker entry remains available.

## Pipeline workflow

- Filing summaries run in the backend; opening Today no longer starts model calls for its top cards. Opening a specific filing can still request an analysis.
- Pull displays its retrieval scope and returns only claims with valid source quotes and matching numerical tokens. Financial extraction additionally requires exact table-header evidence containing the claimed period dates.
- Exact cached NSE company names match contact employment even when the ticker was omitted. Employment autocomplete lets the investor explicitly select the company/ticker before saving. This does not infer corporate group ownership.
- Revised/corrigendum filings are labeled Updated. A previous filing is linked only when normalized titles match unambiguously. Identical analyzed documents are grouped while preserving original links; general semantic change detection is not implemented.
- Research answers have Monitor this question. Manage/remove monitors and inspect their latest evidence under Settings.

## Push and Preferences

Today is the Push feed: threshold-triggered alerts, a windowed digest (24 hours by default), named contact hooks, and collapsed routine filings. Quarterly result cards expose source-checked metrics and QoQ/YoY; unavailable figures stay blank. Management cards use disclosed bios and possible shared affiliations, without inferring a personal connection.

Preferences owns the watchlist, selected announcement types, price/volume thresholds, persistent digest defaults, network deletion controls and source status. GET/PUT /settings/digest saves default_days (1, 7 or 30) and ungroup_filings. DELETE /network/contacts removes all locally saved contacts; the UI requires explicit confirmation. New threshold alerts retain the triggering rule snapshot; older alerts may lack it. Selected categories control announcement alerts; all filings remain in the digest regardless of alert selection.
