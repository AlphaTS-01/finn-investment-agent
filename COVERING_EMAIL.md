# Submission email draft

To: assessment@enam.com

Subject: IIT Kanpur â€“ Founding AI Engineer - 2027

Dear ENAM team,

Please find my submission for the FINN build challenge.

- Prototype: [add verified hosted URL]
- Public repository: https://github.com/AlphaTS-01/finn-investment-agent
- AI build history: [add redacted export or share link]

I built a mobile-first investment workflow around Today, Research, Network and Preferences. Today prioritises portfolio filings and configurable alerts. Research retrieves primary company documents on demand and presents cited answers with evidence gaps. Network context appears within those workflows, helping the investor identify who could explain a company or event. The demo uses twelve clearly labelled synthetic contacts.

The application uses a FastAPI backend, a lightweight web frontend, SQLite persistence and a background ingestion and analysis queue. It combines exchange filings, Yahoo EOD prices and primary annual reports and transcripts. Gemini 3.1 Flash-Lite handles extraction and grounded synthesis, while routing, thresholds and network matching use deterministic code. Document and answer caching reduce repeated API usage.

I focused on concise prioritisation, configurable attention thresholds and visible evidence. Answers require exact supporting quotes and numeric checks, with explicit partial and failure states. These checks do not replace financial interpretation or entailment evaluation. Historical comparisons, scanned-PDF OCR and reliable profile import remain limited by source coverage and extraction quality.

The current architecture is a single-investor prototype. Contacts are locally persisted until deleted, and explicit profile import sends profile content to Gemini. Production work would add investor authentication, tenant isolation, consent and retention controls, managed secrets and request budgets. The planned hosted setup is a single AWS EC2 instance with persistent storage and HTTPS. Deployment is pending and the prototype link above must be verified before submission.

The latest local test run passed 44 tests, with additional live pipeline and mobile-layout checks. SUBMISSION.md in the repository provides the architecture diagram, tradeoffs, privacy decisions, limitations and next steps.

Regards,
[Your full name]
[Contact details]
