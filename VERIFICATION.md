# Live verification - 13 November 2026

Executed locally with the actual configured credentials. Keys are not included in this report.

## Passed

- Gemini authenticated and generated structured answers using `gemini-3.1-flash-lite`.
- Tavily search authenticated and returned document-discovery results. Its snippets are not used as research evidence.
- BSE announcement retrieval and Yahoo EOD retrieval succeeded for all 15 seeded portfolio companies in a full monitoring cycle.
- First monitoring cycle established announcement checkpoints without flooding historical alerts.
- TCS research fetched an annual report and earnings-call transcript and returned five cited claims. HTTP end-to-end run: 2.84 seconds using cached PDFs; repeated answer: 0.11 seconds.
- Outside-portfolio ticker ASIANPAINT returned six cited claims from an earnings-call transcript. Reported partial coverage because its annual report exceeded the 25 MB download limit. HTTP end-to-end run: 5.50 seconds; repeated answer: 0.03 seconds.
- Local HTTP health, portfolio, Swagger documentation, TCS announcements and TCS price endpoints returned 200.
- 11 offline tests passed: cache expiry, event identity/time normalization, routine notice priority, alert deduplication, citation ID validation, model-failure behavior, API validation, non-public URL rejection, ticker validation, initial monitoring baseline and failed-download caching.
- Credential scan passed for backend/test source, README, dependency lock and environment example. `.env` and `data/` are ignored.

## Findings and limits

- Gemini's model listing advertised `gemini-2.5-flash`, but generation returned 404 with a message that it is unavailable to new users. The configured default was changed to a model verified by an actual generation call.
- A listing/authentication check is not sufficient evidence that a model can generate.
- The first TCS PDF extraction found a missing optional font parser; `fonttools` was installed and pinned.
- Annual reports larger than 25 MB are intentionally skipped. Download failures cache for 15 minutes. Partial responses disclose missing document types instead of claiming full coverage.
- The NSE fallback code has not been exercised against a live BSE outage. OCR, multi-user isolation, external notifications were not part of the initial backend increment. Network integration is verified below.
- Citation IDs and page links were mechanically checked; this is not a comprehensive financial-accuracy evaluation.
- One Starlette test-client deprecation warning remains; the tests passed.

Re-run live HTTP verification (may use API quota): `python -m backend.smoke` while the API is running. Summaries are written to ignored `data/live-verification.json`.

## Frontend increment

- Browser verified at the available narrow viewport: responsive navigation, seven-day briefing with 36 events, event details and original filing link.
- Event-to-research navigation populated TATASTEEL and the selected acquisition filing context.
- Submitted TCS research through the UI and expanded a claim citation to its original excerpt and PDF page link.
- Settings loaded the 15-company watchlist and saved backend alert preferences. Settings mutations were previously API-tested; this browser pass inspected the loaded form without changing preferences.
- Briefing now supports immediate cached snapshots with visible freshness status; explicit refresh requests fresh exchange data.
- Existing 11 automated backend tests still passed after frontend serving and briefing changes.
- Desktop-wide and physical-phone layouts were not separately browser-tested in this increment.

## Network and briefing increment - 14 November 2026

- 23 offline tests passed, including contact validation/CRUD, introduction cycles, expertise and major matching, affiliation overlap disclaimers, import review without auto-save, blocked public-profile fallback, filing grouping, quarterly comparison validation, briefing-only alert suppression, and actual event PDF inclusion in research. Both frontend scripts passed Node syntax checks.
- Browser verified expanded contact creation and search by Chemical Engineering major, explained ticker matching, and loaded interruption modes. Temporary QA contact was removed; three explicitly synthetic demo contacts remain.
- Live Gemini profile-text extraction returned occupation, employment dates, BTech major, expertise and location into an unsaved review draft.
- Live Tata Steel results filing analysis read a 24-page PDF, selecting 18 pages. Page 15 provided comparable consolidated Revenue, PBT and PAT for September 2026, June 2026 and September 2025. Revenue QoQ/YoY: 7.64%/11.50%; PBT: 42.15%/29.19%; PAT: 55.10%/16.23%. These values were checked against the extracted table. EBITDA was not verified and was not derived.
- An oversized Infosys filing returned an explicit download-limit failure; its original source remains available. Profile URLs behind LinkedIn access restrictions cannot be automatically imported; pasted professional text is the fallback.
- Citation substring validation does not prove that every interpretation is correct. Financial-table column assignment and narrative implications remain first-cut analysis, with source links and limitations exposed.

## Import, minimal UI and ticker search - 15 November 2026

- Sundar Pichai sample URL (including trailing comma) returned a review draft via exact-profile indexed content: Google roles, Wharton MBA, Stanford MS Materials Science and Engineering, and IIT Kharagpur BTech. Unknown major/dates remain blank. No contact was saved during verification.
- Removed marketing headings/promotional panels, reduced heading sizes, and adopted a white/green compact interface. Browser checked Research layout and suggestion selection.
- Live NSE equity directory returned 13 company-name matches for Tata, including TCS and TATASTEEL. Browser selection populated TATASTEEL.
- 26 tests passed, covering exact-profile rejection of same-name alternatives and company search ranking/cache/failure behavior; frontend JavaScript syntax checks passed.

## Routed research, background Push and monitors - 15 November 2026

- 35 offline tests pass. New coverage checks question routing, two-document selection, late-arriving filing IDs, baseline suppression, durable job retries, monitor CRUD, exact-quote validation, duplicate attachment suppression, briefing-only behavior, exact employer matching, amendment links and repeated-document grouping.
- Live TCS research returned source-quoted claims through the stricter validator. Browser verification submitted research, saved a monitor, viewed it in Settings, and selected Tata Consultancy Services in an employment row; TCS was filled automatically. The temporary verification monitor was removed afterward.
- API startup launches a worker. A live queued filing-analysis job completed without browser enrichment. Source ingestion and queue processing are separate, so an exchange timeout does not stop cached filing work.
- Research remains keyword-based and uses available title/date metadata. Comparisons are explicitly partial pending independent period coverage. Historical filing discovery is limited to 90 days; Push observation overlaps seven days. Monitor alerts for real future filings have not been awaited; their full ingestion/quote/deduplication path is covered by isolated tests.
- Financial comparison extraction now requires an exact table header containing the claimed quarter dates. Semantic interpretation, unit assignment, and number-to-column interpretation still require source review.

## Mobile hierarchy and freshness repair - 15 November 2026

- Reviewed all four supplied phone screenshots. Replaced the stylesheet with a shared spacing/type system and consistent inline SVG navigation.
- Today now orders Alerts, Worth reviewing, Watchlist, then collapsed Routine filings. Filters share one row; status is compact; watchlist rows have status dots and labels, with five shown initially. Review totals and the visible review section share the same threshold and filters.
- Filing titles open the dialog; generic filler summaries and internal external-link arrows were removed. Contact cards retain one synthetic-demo label, separate role/company lines, and noninteractive expertise tags. Network filters have selected states and Show more; Research shortcuts have a Try label.
- Relative times open a dialog with the exact IST timestamp. Date appears only on Today, with an avatar linking to Settings.
- Fixed stale-window selection: briefing chooses the freshest covering snapshot, then reapplies the rolling cutoff. Live HTTP check returned 15 fresh feeds and zero filings in the current 24-hour window. Seven-day browser view showed 33 filings and 9 worth reviewing. Counts and portfolio reflect the user's current saved state.
- 37 automated tests passed, including fresh wider-window reuse and stale status preservation. JS syntax checks passed. Browser verified mobile layouts at 390x844 and 320x740, expertise filter selection, Show more/less, all 15 watchlist rows, exact timestamp dialog, and filing title navigation. Narrow Settings layout did not overflow horizontally. Viewport restored afterward.
- Phone preview saved to data/mobile-review/today-after.png. Actual physical-phone interaction was not repeated; verification used responsive browser viewports.

## Focused Push and Preferences - 15 November 2026

- Today contains triggered market/selected-announcement alerts, then the windowed digest and collapsed routine filings. Watchlist management/status and grouping defaults moved to Preferences. Monitor-question updates remain under Preferences, separate from threshold-triggered Today alerts.
- Digest defaults persist via GET/PUT /settings/digest, initially 24 hours and grouped filings. Browser changed the default to seven days and saved it, then restored 24 hours. Preference fields wait for saved values before accepting edits.
- New alerts store the actual observed price/volume, the rule snapshot, and human-readable trigger reasons. Announcement alerts respect selected categories in both legacy active modes. Older alerts without snapshots identify the missing historical threshold instead of assuming the current setting.
- Cards show the top named contact, recorded role/company and a matching reason. Results cards include Revenue/EBITDA/PBT/PAT with QoQ/YoY and source scope, or explicit unverified values. Management cards only show incoming-person bios from available filing analysis; exact disclosed affiliations can match contacts, with dates/relationships explicitly unverified.
- Preferences includes thresholds, categories, collapsed watchlist management, digest defaults, monitored questions, local network data disclosure/deletion, and per-company source status. Actual contacts were not deleted during verification; deletion tests use isolated temporary databases.
- 42 backend tests passed. Frontend syntax checks passed. Phone-size browser verified Today hooks, the four-row results table, Preferences persistence and no horizontal overflow at 390px. Both localhost:8000 and the existing phone server on port 8001 run the updated backend.
- Current seven-day results example lacks validated figures, so its card shows dashes rather than fabricated comparisons. Management bios/affiliations remain dependent on what the filing discloses; no external executive-biography enrichment is claimed.
- Preview files: data/mobile-review/push-after.png and preferences-after.png.
# Phone and research fixes — 15 November 2026

- Header date verified visible on Today, Research, Network and Preferences.
- Reproduced Add contact crash on LAN HTTP (`crypto.randomUUID` unavailable); removed secure-context dependency from dynamic form identifiers. Verified dialog and Add role over LAN, including 390px viewport.
- Seeded nine additional fictional profiles; Network shows 12 labelled synthetic contacts.
- Research distinguishes document retrieval, passage matching, citation validation and Gemini failures. Unverified answers retain source excerpts; malformed or wholly unverifiable model output gets one repair attempt. Empty answers are not cached.
- Live TCS business overview: three documents read, 14 passages, three verified claims, one model attempt, status ok.
- Regression suite: 44 passed. Covers empty Gemini candidates, repair retry, numeric formatting equivalence, rejection of changed signs, retained evidence and existing workflows.
- Screenshot: `data/mobile-review/contact-phone-fixed.png`.

