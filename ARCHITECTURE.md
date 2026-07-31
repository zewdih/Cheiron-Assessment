# Cheiron System Architecture — Deep Dive

This document covers everything you need to know for an on-site discussion: architecture decisions, trade-offs, what you'd improve, and questions an interviewer might ask.

---

## 1. System Overview

Cheiron is a **backend service** that takes a natural-language question about clinical trials and returns a structured JSON visualization specification. It is NOT a chatbot — it produces data-driven, citation-backed visualization specs that a frontend could render.

### The Pipeline (6 stages)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Request                                 │
│  { "query": "How has Pembrolizumab trial count changed over time?" }│
└────────────────────────────┬────────────────────────────────────────┘
                             │
                   ┌─────────▼──────────┐
                   │   INPUT VALIDATION  │  Pydantic: type checks, sanitization,
                   │   (Deterministic)   │  control char stripping, length limits
                   └─────────┬──────────┘
                             │
                   ┌─────────▼──────────┐
                   │  PHASE 1: LLM      │  gpt-4.1 with structured outputs
                   │  Query Analyzer     │  IN: question text only
                   │                     │  OUT: QueryPlan (enums, API params)
                   │  ⚠ NO DATA ACCESS   │  Cannot see or generate trial data
                   └─────────┬──────────┘
                             │ QueryPlan
                   ┌─────────▼──────────┐
                   │  CT API CLIENT      │  httpx → clinicaltrials.gov/api/v2
                   │  (Deterministic)    │  Pagination, retry, field selection
                   │                     │  Returns raw JSON from the API
                   └─────────┬──────────┘
                             │ Raw studies[]
                   ┌─────────▼──────────┐
                   │  DATA PROCESSOR     │  Python Counter + defaultdict
                   │  (Deterministic)    │  Counting, grouping, network building
                   │                     │  Embeds _nct_ids for citation linkage
                   │  ⚠ NO LLM          │
                   └─────────┬──────────┘
                             │ Aggregated data + _nct_ids
                   ┌─────────▼──────────┐
                   │  CITATION EXTRACTOR │  Dict lookups: _nct_ids → excerpts
                   │  (Deterministic)    │  Builds nct_id + URL + excerpt
                   │  ⚠ NO LLM          │
                   └─────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼────┐   ┌────▼────────┐     │
    │ VIZ BUILDER  │   │ PHASE 2:    │     │
    │(Deterministic)│   │ LLM Narrate │     │
    │ Assembles     │   │ gpt-4.1-mini│     │
    │ encoding,     │   │ IN: counts  │     │
    │ data points,  │   │ OUT: title  │     │
    │ citations     │   │ + notes     │     │
    └───────┬──────┘   └──────┬──────┘     │
            │                 │             │
            └────────┬────────┘             │
                     │                      │
           ┌─────────▼──────────┐           │
           │  RESPONSE ASSEMBLY  │           │
           │  QueryResponse      │◄──────────┘
           │  (Pydantic validated)│
           └─────────────────────┘
```

---

## 2. The "Data Firewall" Pattern — Why It Matters

### The Problem
LLMs hallucinate. In a medical data context, a hallucinated trial count or fabricated NCT ID could mislead researchers. Prompt-level instructions ("don't hallucinate") are insufficient — they reduce but don't eliminate the risk.

### The Solution
**Structural separation.** The LLM is architecturally excluded from the data pipeline:

| Stage | Has LLM? | What flows through |
|-------|----------|-------------------|
| Query Analysis | Yes (Phase 1) | User's question text → enum fields, API params |
| API Fetching | No | HTTP request → raw JSON |
| Aggregation | No | Raw studies → Counter results |
| Citations | No | NCT ID lookups → excerpts |
| Viz Assembly | No | Aggregated data → Pydantic model |
| Narration | Yes (Phase 2) | Aggregated counts → title + notes text |

**Key insight:** The LLM produces *instructions* (Phase 1) and *text descriptions* (Phase 2). It never produces *data*. Data flows exclusively through deterministic Python code.

**Phase 2 narration** generates rich, data-grounded notes (3-5 sentences) that include exact counts, percentages, trend analysis, and plain-language explanations of clinical trial terminology. For example, instead of just "Phase 3 has the most trials," it says: "Of 500 diabetes trials, Phase 3 leads with 210 studies (42%), representing large-scale trials typically conducted before seeking regulatory approval." Every claim traces to a number in the aggregated data — the LLM is forbidden from adding medical opinions or speculating about causation.

### How to explain this to an interviewer
"I designed the system so that hallucination of clinical data is architecturally impossible, not just prompt-discouraged. The LLM tells us what to query and how to describe the results, but every number in the output comes from Python's Counter class operating on raw API responses. I can prove this with a test that independently recounts the data and asserts exact equality."

---

## 3. Data Cleaning — How We Handle Unknowns and Raw API Values

Before data reaches the frontend, the backend applies deterministic cleaning in `data_processor.py`:

**1. Label Normalization** — Raw API values like `"PHASE3"`, `"EARLY_PHASE1"` are mapped to human-readable labels (`"Phase 3"`, `"Early Phase 1"`) via the `PHASE_LABELS` dictionary. `"NA"` and `"NOT_APPLICABLE"` are merged into a single `"Not Applicable"` category.

**2. Unknown/Missing Data Filtering** — The `NOISE_VALUES` set (`"Unknown"`, `"UNKNOWN"`, `""`) is filtered out during aggregation across all chart types (bar, comparison, geographic, network). If a study doesn't list an intervention name or country, it's excluded from the count rather than showing as an "Unknown" bar. This is deliberate: "Unknown: 342" on a chart is noise, not insight. The `total_studies_analyzed` count still reflects all fetched studies, so no data is silently lost.

**3. Logical Ordering** — Phases are sorted in clinical progression order (Early Phase 1 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Not Applicable) rather than alphabetically or by count. Other categories (sponsors, countries) remain sorted by count descending.

**4. Internal Field Stripping** — The `_nct_ids` lists used to link data points to citations are stripped in `viz_builder.py` (removes any key starting with `_`). The frontend never sees internal tracking data.

All four steps are deterministic Python code — no LLM involvement. This ensures the frontend always receives clean, consistently formatted, presentation-ready data.

### Interviewer question: "Why filter out unknowns instead of showing them?"
Answer: "In a visualization context, an 'Unknown' bar doesn't help the researcher make decisions. It's missing data, not a meaningful category. We still count those studies in `total_studies_analyzed` so the researcher knows the full sample size. If they need to see unknowns, that's a configuration option we could add — but the default should be clean, actionable data."

---

## 4. Anti-Hallucination Strategy (5 Layers)

### Layer 1: Structural Separation (Architecture)
- LLM excluded from data pipeline entirely
- Data path: API → Python → Pydantic → JSON (no LLM in the loop)

### Layer 2: Constrained LLM Outputs (Model)
- OpenAI `strict: True` structured outputs use constrained decoding
- The model literally cannot produce tokens that violate the JSON schema
- Phase 1 output: enum fields (QueryType, VisualizationType, GroupByField) + strings
- Phase 2 output: title (max 100 chars) + notes (max 500 chars)

### Layer 3: Post-LLM Validation (Code)
- After Phase 1: verify at least one API param is populated, NCTId in fields_needed
- After API fetch: HTTP status check, JSON parse
- After aggregation: total_studies matches len(studies)
- After assembly: full Pydantic QueryResponse validation

### Layer 4: Citation Anchoring (Design)
- Every data point carries citations with real NCT IDs, direct URLs, and text excerpts
- Excerpts are built deterministically from actual API response fields
- A reviewer can verify any claim by clicking the URL

### Layer 5: Automated Verification (Testing)
- `TestAntiHallucination.test_counts_match_input_exactly`: feeds known data, asserts exact counts
- `TestAntiHallucination.test_all_nct_ids_traceable`: every output NCT ID exists in input
- These tests prove the pipeline is faithful to its input

### Interviewer question: "What if the LLM hallucinates in the query plan?"
Answer: "If Phase 1 produces a nonsensical query plan — say, a drug name the user didn't mention — the worst case is that the ClinicalTrials.gov API returns irrelevant results or zero results. The data itself is still real (it came from the API). The post-validation step catches the most obvious issues (empty search params, missing required fields). And the user's question is included in the response metadata, so a reviewer can see if the interpretation was wrong."

---

## 4. Model Selection Rationale

### Why gpt-4.1 for Phase 1?
- **Optimized for agentic tool use and structured outputs** — exactly what query planning requires
- **Reliable at following complex system prompts** — the prompt has safety rules, mapping rules, few-shot examples
- **Good latency** for live demos (vs. gpt-5.x which would be slower)
- **Shows engineering judgment** — not just "pick the biggest model"

### Why gpt-4.1-mini for Phase 2?
- Phase 2 is simple: take counts, write a title and 1-2 sentences
- Cheaper model, lower latency, no quality loss for this narrow task
- Phase 2 failure is non-fatal: we fall back to a generated title

### Why not gpt-5.x?
- The task doesn't require frontier reasoning — it's parsing intent and mapping to API params
- Higher latency would hurt the demo experience
- More expensive with no meaningful quality gain for this use case

### Interviewer question: "What if the model is slow or rate-limited?"
Answer: "Phase 2 is already non-critical — if it fails, we use a fallback title. For Phase 1, we could implement a simpler rule-based fallback for common query patterns (e.g., regex detection of 'over time' → time_trend). But for the scope of this assignment, the single LLM call with structured output is the right balance of capability and simplicity."

---

## 5. Tech Stack Justification

| Choice | Why | Alternative Considered |
|--------|-----|----------------------|
| **Python** | Rich data processing ecosystem, native OpenAI SDK, match-case for clean dispatch | Node.js — weaker at data manipulation |
| **FastAPI** | Auto-generated OpenAPI docs (great for demo), Pydantic integration, async support | Flask — no async, no auto-docs |
| **Pydantic v2** | Type safety at every boundary, JSON schema generation for OpenAI structured outputs | dataclasses — no validation |
| **httpx** | Async HTTP client, connection pooling, works with tenacity | requests — no async |
| **tenacity** | Retry with exponential backoff, clean decorator API | Manual retry loops |
| **OpenAI structured outputs** | Schema-guaranteed JSON, constrained decoding | Function calling — more complex for single-output |

### Interviewer question: "Why not use LangChain or LlamaIndex?"
Answer: "For this specific use case, they add abstraction without value. The pipeline is linear (question → plan → fetch → process → output). LangChain's chain/agent abstractions would obscure the Data Firewall pattern, which is the core architectural feature. The anti-hallucination guarantees depend on knowing exactly where the LLM is and isn't in the data path. A framework would make that harder to reason about and demonstrate."

---

## 6. Trade-offs & What I'd Improve

### Trade-off 1: Deterministic Aggregation vs. LLM Flexibility
**What we chose:** Fixed aggregation types (count by group, time bucketing, network edges)
**What we gave up:** The LLM can't do ad-hoc analysis ("what's the average enrollment for Phase 3 trials in Europe?")
**Why:** Reliability > flexibility for medical data. Every aggregation is testable and verifiable.
**Improvement:** Add more aggregation types (enrollment stats, duration analysis) to the deterministic pipeline.

### Trade-off 2: Top-N Truncation vs. Completeness
**What we chose:** Top 20 categories, top 50 network edges, max 5 citations per point
**What we gave up:** Long-tail data, complete citation coverage
**Why:** Visualization readability. A bar chart with 200 bars is unreadable. A network with 5000 edges is noise.
**Improvement:** Make limits configurable. Add a "show all" option that returns paginated raw data.

### Trade-off 3: Single Query vs. Multi-Turn
**What we chose:** Stateless single-query API
**What we gave up:** "Drill down into Phase 3" follow-up queries
**Why:** Scope management. Multi-turn adds session state, context management, and ambiguity resolution.
**Improvement:** Add a session_id parameter and query history for contextual follow-ups.

### Trade-off 4: No Caching vs. Latency
**What we chose:** Fresh API calls every time
**What we gave up:** Fast repeated queries
**Why:** Clinical trials data updates (new studies posted, status changes). Stale cache = stale data.
**Improvement:** Redis cache with 1-hour TTL. Cache key = hash of API params. Invalidation on known update schedules.

### Trade-off 5: Separate API Calls for Comparisons
**What we chose:** One API call per entity in comparison queries
**What we gave up:** Performance (2+ API calls vs 1)
**Why:** Clean separation. A combined search for "Pembrolizumab OR Nivolumab" returns trials mentioning either, but we can't cleanly attribute each trial to one entity. Separate calls give exact per-entity counts.
**Improvement:** Could parallelize the API calls with asyncio.gather() for faster comparisons.

---

## 7. Security Considerations

### Input Validation
- Pydantic validators strip control characters, normalize whitespace
- Max length on all string fields (query: 1000 chars)
- Regex validation on trial_phase
- Year range bounds (1990-2030) with cross-field validation

### Prompt Injection Defense
- User question is in the `user` message, never in `system`
- Structured output with `strict: True` means even a "jailbroken" response must conform to the QueryPlan schema
- Phase 2 receives aggregated counts, not raw user input — no injection vector

### API Key Management
- OpenAI key in .env file, loaded via pydantic-settings
- .env excluded from version control
- Key never appears in logs or API responses
- Error messages for key failures are generic ("Service configuration error")

### Rate Limiting
- In-memory rate limiter (configurable RPM per client IP)
- Protects both the service and the upstream APIs from abuse

### Interviewer question: "What about SQL injection or XSS?"
Answer: "There's no SQL database, so SQL injection doesn't apply. XSS is a frontend concern — our API returns JSON, not HTML. The primary attack surface is prompt injection, which we mitigate with structured outputs (the LLM can't produce freeform executable content) and input sanitization."

---

## 8. Query Type Coverage

| Query Type | Example | Viz Type | How It Works |
|-----------|---------|----------|--------------|
| Time Trend | "Pembrolizumab trials per year since 2015" | time_series | Group by start_date year, count |
| Distribution | "Diabetes trials by phase" | bar_chart | Group by phase, count, sort desc |
| Comparison | "Pembrolizumab vs Nivolumab by phase" | grouped_bar_chart | Separate API calls per entity, same grouping |
| Geographic | "Countries with most recruiting cancer trials" | bar_chart | Group by country from locations |
| Network | "Drug-condition network for breast cancer" | network_graph | Co-occurrence edges between two dimensions |

### How to extend to new query types
1. Add enum value to `QueryType` and `VisualizationType`
2. Add processing method to `DataProcessor` (deterministic)
3. Update system prompt with mapping rule and few-shot example
4. Add tests

The architecture is designed for this — each query type is a `match` case in the processor. No one-off hacks.

---

## 9. Citation System (Deep Traceability)

### How it works
1. During aggregation, the DataProcessor tracks which NCT IDs contribute to each data point via `_nct_ids` lists
2. The CitationExtractor takes these lists and looks up the original study in a dict
3. For each NCT ID, it builds an excerpt from actual API fields: title, status, phase, start date, sponsor
4. Citations are capped at 5 per data point to control response size
5. Each citation includes a direct URL: `https://clinicaltrials.gov/study/{nct_id}`

### Why this matters
"If someone sees '42 Phase 3 trials' in the visualization, they can click the citations and see exactly which 5 of those 42 trials are listed, with direct links to ClinicalTrials.gov. Nothing is fabricated."

### Design decision: Why only 5 citations per point?
A data point with 500 trials would have 500 citations — that's a 100KB JSON response per data point. 5 is a representative sample. The `total_studies_analyzed` field tells you the full count.

---

## 10. Error Handling Philosophy

**Principle: Degrade gracefully, never fabricate.**

| What fails | What happens | Why |
|-----------|-------------|-----|
| Phase 1 LLM | 500 error, "Failed to interpret your question" | Can't proceed without a query plan |
| ClinicalTrials.gov API | 502 error, "Service unavailable" | Can't visualize data we don't have |
| Zero results | 200 with empty data[] and explanatory note | Valid response — "no data" is an answer |
| Phase 2 LLM | 200 with fallback title | Data is already computed; narration is cosmetic |
| Pydantic validation | 422 with field-level errors | Fast feedback on malformed input |

The key insight: **Phase 2 LLM failure is deliberately non-fatal.** The data and citations are already computed by deterministic code. We just lose a pretty title and interpretive notes. This demonstrates that the LLM is not load-bearing for the data.

---

## 11. Testing Strategy

### What we test and why

| Test Suite | Count | What it proves |
|-----------|-------|---------------|
| test_data_processor | 7 | Aggregation counts are exact, all query types work, missing fields handled |
| test_citation_extractor | 6 | Citations link to correct NCT IDs, URLs are valid, excerpts contain real fields |
| test_viz_builder | 5 | Output schema is correct, internal fields stripped, all viz types structured properly |
| test_request_validation | 8 | Input sanitization works, invalid inputs rejected, edge cases caught |
| **TestAntiHallucination** | 2 | **Counts match input exactly. All NCT IDs traceable. No data fabrication.** |

### The anti-hallucination tests are the most important
```python
def test_counts_match_input_exactly(self):
    # Feed 20 known studies (7 Phase 1, 8 Phase 2, 5 Phase 3)
    # Assert output counts are exactly 7, 8, 5
    # Assert total is exactly 20
    # This PROVES the pipeline doesn't fabricate or lose data
```

### What's NOT tested (and why)
- LLM outputs: Non-deterministic. We test the schema validation and post-processing, not the LLM itself.
- Live ClinicalTrials.gov API: Would make tests flaky. We use saved fixtures instead.
- Performance/load: Out of scope for a take-home. Would add k6/locust in production.

---

## 12. Potential Interviewer Questions & Answers

**Q: "Why not just let the LLM call the API directly as a tool?"**
A: "That would give the LLM control over the data pipeline. It could choose not to call the API and generate plausible-looking fake data instead. By structurally separating the LLM from data fetching, we guarantee every data point comes from a real API call."

**Q: "How would you handle a query the system can't understand?"**
A: "Post-validation catches plans with no search parameters and returns a 422 with suggestions. For edge cases that slip through, the ClinicalTrials.gov API returns zero results, and we return an empty visualization with an explanatory note. We never guess or fabricate data to fill the gap."

**Q: "How would you scale this?"**
A: "The stateless API design means horizontal scaling with a load balancer is straightforward. The main bottleneck is the LLM call (~1-2s). Adding Redis caching for repeated queries would reduce load. For heavy use, I'd add a queue (Celery/Redis) for async processing with webhook callbacks."

**Q: "What if ClinicalTrials.gov changes their API?"**
A: "The API client is a single isolated module (ct_client.py). All field extraction is in one place (data_processor.py's _extract_field method). API changes require updating these two files only — the rest of the pipeline is API-agnostic."

**Q: "Why Pydantic for everything?"**
A: "It serves three roles: (1) input validation — rejects bad requests before they hit the LLM, (2) LLM output constraint — the JSON schema is generated from Pydantic models and enforced by OpenAI's constrained decoding, (3) output contract — the response schema is auto-documented in the OpenAPI spec. One type system, three uses."

**Q: "How do you ensure the visualization is appropriate for the data?"**
A: "The query type → visualization type mapping is encoded in the system prompt with explicit rules and few-shot examples. The narration prompt includes data visualization best practices — flagging baseline differences in comparisons, noting gaps in time series, identifying when scales are misleading. The system doesn't just pick a chart type; it provides context for correct interpretation."

**Q: "Why is there a 5-8 second delay?"**
A: "I profiled the pipeline. 87% of the latency is the two LLM calls (query analysis ~2s, narration ~3s). The API fetch is ~0.8s. Data processing is under 1ms. The LLM calls are the bottleneck, but they're doing essential work — Phase 1 interprets the question, Phase 2 generates data-grounded insights. We could cut Phase 2 and save 3 seconds, but we'd lose the rich narration. Instead, we show a loading message that frames the wait: 'We query ClinicalTrials.gov directly and verify every data point against its source.' Users will trade time for trust when they know the data is real."

**Q: "How do I verify the chart numbers are correct without domain expertise?"**
A: "Three steps: (1) Click any bar — see 5 citation links. (2) Click a citation — it opens the real study on ClinicalTrials.gov. (3) Confirm the phase/condition/drug matches what our chart says. You don't need to understand Pembrolizumab to verify that a study labeled Phase 3 on ClinicalTrials.gov is counted in our Phase 3 bar. The citation is the receipt, the bar is the summary."

**Q: "Why are phases ordered Early Phase 1 through Phase 4 instead of by count?"**
A: "Clinical trial phases represent a progression — safety testing (Phase 1) → efficacy (Phase 2) → large-scale confirmation (Phase 3) → post-approval monitoring (Phase 4). Ordering by count would scatter this progression. A researcher reading the chart expects to see the clinical pipeline left to right. We sort phases logically in `data_processor.py` using a `PHASE_ORDER` list, while all other categories (sponsors, countries) remain sorted by count descending."

**Q: "How would you reduce the latency?"**
A: "Three approaches: (1) Run Phase 2 narration in parallel with viz building and stream it in after the chart renders — the chart appears in ~3s, notes fill in 2s later. (2) Cache ClinicalTrials.gov responses with Redis (1-hour TTL) — eliminates the 0.8s API call for repeated queries. (3) For common query patterns, use a rule-based classifier instead of the LLM for Phase 1 — regex can detect 'over time' → time_trend without an LLM call. But all three add complexity, and 5-8 seconds is acceptable for a research tool that guarantees data accuracy."

**Q: "Why don't you auto-correct misspelled drug names?"**
A: "We chose not to auto-correct drug names because false corrections in a medical context are worse than returning no results. If the LLM 'corrects' a misspelling to the wrong drug, you get plausible-looking data for the wrong compound — that's a silent failure. Returning 0 results with a clear message is honest and safe. With more time, we'd integrate a validated medical terminology service like RxNorm or MeSH for resolution — not LLM-based guessing."

**Q: "What would you do differently with more time?"**
A: "Three things: (1) Drug name resolution — integrate RxNorm/MeSH for validated synonym and brand-name mapping (not LLM guessing). (2) Response caching — Redis with 1-hour TTL to avoid redundant API calls. (3) Frontend enhancements — export to PNG/PDF, dark mode, shareable visualization URLs."
