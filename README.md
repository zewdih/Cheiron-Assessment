# Cheiron — Clinical Trials Query-to-Visualization Agent

AI-enabled backend (with optional frontend) that converts natural-language questions about clinical trials into structured visualization specifications, backed by the ClinicalTrials.gov API.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend only)
- OpenAI API key (with access to gpt-4.1 and gpt-4.1-mini)

### Install & Configure

```bash
# Clone and enter directory
cd Cheiron

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Install frontend dependencies (optional)
cd frontend && npm install && cd ..
```

### Run the Backend

```bash
uvicorn cheiron.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Run the Frontend (Optional)

In a second terminal:
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser. The frontend proxies API requests to the backend.

### Run Tests

```bash
# All 55 tests (unit, integration, security, robustness)
python -m pytest cheiron/tests/ -v
```

### Run Example Queries

```bash
# With the backend running:
python -m cheiron.examples.run_examples

# Or test directly with curl:
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How are diabetes trials distributed across phases?", "condition": "diabetes"}' \
  | python3 -m json.tool
```

---

## Request/Response Schema

### Request (`POST /api/v1/query`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Natural language question (10-1000 chars) |
| `drug_name` | string | No | Specific drug/intervention name |
| `condition` | string | No | Disease or condition name |
| `trial_phase` | string | No | Phase filter (e.g., "Phase 3") |
| `sponsor` | string | No | Sponsor organization name |
| `country` | string | No | Country for location filtering |
| `start_year` | int | No | Start of year range (1990-2030) |
| `end_year` | int | No | End of year range (1990-2030) |

**Example:**
```json
{
  "query": "How has the number of trials for Pembrolizumab changed over time?",
  "drug_name": "Pembrolizumab"
}
```

### Response

```json
{
  "visualization": {
    "type": "time_series",
    "title": "Pembrolizumab Clinical Trials by Year (2010-2025)",
    "encoding": {
      "x": {"field": "year", "type": "temporal", "title": "Year"},
      "y": {"field": "trial_count", "type": "quantitative", "title": "Number of Trials"}
    },
    "data": [
      {
        "values": {"year": 2015, "trial_count": 67},
        "citations": [
          {
            "nct_id": "NCT02362594",
            "url": "https://clinicaltrials.gov/study/NCT02362594",
            "excerpt": "Pembrolizumab Combined With Chemotherapy | Status: COMPLETED | Phase: PHASE2 | Start: 2015-02 | Sponsor: Dana-Farber"
          }
        ]
      }
    ],
    "notes": "Trial activity grew steadily from 2014 to 2020, peaking at 203 new trials.",
    "query_interpretation": "Time trend for Pembrolizumab trials grouped by start year."
  },
  "meta": {
    "query": "How has the number of trials for Pembrolizumab changed over time?",
    "filters": {"drug_name": "Pembrolizumab"},
    "total_studies_analyzed": 2914,
    "source": "clinicaltrials.gov",
    "api_version": "v2",
    "timestamp": "2026-07-30T12:34:56Z"
  }
}
```

### Supported Visualization Types

| Type | When Used |
|------|-----------|
| `time_series` | Time trend queries (trials over years) |
| `bar_chart` | Distributions (trials by phase, status, sponsor) |
| `grouped_bar_chart` | Comparisons (Drug A vs Drug B by phase) |
| `network_graph` | Relationships (drug-condition co-occurrence) |
| `histogram` | Numeric distributions |
| `scatter_plot` | Two-variable relationships |

---

## Key Design Decisions & Trade-offs

### 1. The "Data Firewall" Pattern

**Decision:** The LLM operates in two constrained phases with a fully deterministic data pipeline in between. The LLM never sees, generates, or modifies clinical trial data.

**Why:** Medical data accuracy is non-negotiable. By structurally excluding the LLM from the data path, hallucination of data points is architecturally impossible — not just prompt-discouraged.

**Trade-off:** Less flexibility. The LLM can't do ad-hoc data analysis or generate insights beyond what the deterministic pipeline computes. We accept this trade-off because reliability > flexibility in medical contexts.

### 2. gpt-4.1 for Query Analysis, gpt-4.1-mini for Narration

**Decision:** Use two different models for the two LLM phases.

**Why:** Phase 1 (query analysis) requires reliable structured output and multi-step reasoning. Phase 2 (title/notes) is simple text generation from pre-computed data. Using a cheaper model for Phase 2 saves cost and latency without sacrificing quality.

**Trade-off:** Two model configurations to manage. Minimal complexity increase.

### 3. Structured Outputs with strict: True

**Decision:** Use OpenAI's constrained decoding (JSON schema with strict mode) for all LLM outputs.

**Why:** Guarantees the LLM output is valid JSON conforming to our Pydantic schema. The model literally cannot produce output that violates the schema — it's constrained at the token-generation level.

### 4. Citation-First Design

**Decision:** Every data point carries citations with NCT IDs, URLs, and text excerpts from the API response.

**Why:** Source traceability is critical for medical data. A user or reviewer can verify any number in the visualization by following the citation back to ClinicalTrials.gov.

### 5. No Auto-Correction of Drug Names

**Decision:** The system passes drug/condition names directly to the ClinicalTrials.gov API without attempting to correct misspellings or resolve synonyms.

**Why:** We chose not to auto-correct drug names because false corrections in a medical context are worse than returning no results. If a user types "pembrulizumab" (misspelled), returning 0 results with a clear message is safer than the LLM "correcting" it to a different drug entirely. Medical data integrity requires that the system queries exactly what the user asked for.

**Trade-off:** Misspelled queries return empty results. With more time, we'd integrate a medical terminology service (RxNorm, MeSH) for validated drug name resolution — not LLM-based guessing.

### 6. Rich Data-Grounded Narration

**Decision:** The Phase 2 LLM generates detailed, data-grounded notes (3-5 sentences) that include exact counts, percentages, trend descriptions, and plain-language explanations of categories (e.g., "Phase 3 trials are large-scale studies typically conducted before seeking regulatory approval").

**Why:** A chart alone isn't always self-explanatory. Researchers need context — but that context must be grounded in the data, not hallucinated. The narration prompt enforces this: every claim must trace to a number in the data summary, and the LLM is forbidden from making medical claims or speculating about causation.

**Trade-off:** Richer notes require a more capable LLM call, slightly increasing latency. We use gpt-4.1-mini to keep it fast, and failure falls back to a basic generated title.

### 7. Deterministic Aggregation via Python

**Decision:** All counting, grouping, and network-building is done with Python's `Counter` and `defaultdict`, not by the LLM.

**Why:** Deterministic code produces reproducible, verifiable results. The same input always produces the same output. An anti-hallucination test can independently recount and assert exact equality.

---

## Limitations & Future Improvements

### Limitations
- **No semantic understanding of medical terminology:** The system passes drug/condition names directly to the API. It doesn't understand that "Keytruda" is the brand name for Pembrolizumab.
- **Max 5000 studies per query:** Large-scale analyses (e.g., "all cancer trials") are truncated.
- **No caching:** Each query hits the ClinicalTrials.gov API fresh. Repeated queries re-fetch.
- **Single-query scope:** Can't do follow-up questions or multi-turn conversations.
- **Network graphs limited to top 50 edges:** Very dense networks are pruned for readability.

### With More Time
- **Drug name resolution:** Use a medical terminology service (RxNorm, MeSH) to resolve brand names, synonyms, and related compounds.
- **Response caching:** Cache ClinicalTrials.gov responses with TTL to reduce latency for repeated queries.
- **Streaming responses:** Stream partial results as the pipeline progresses.
- **Frontend enhancements:** Add export to PNG/PDF, dark mode toggle, shareable visualization URLs.
- **Multi-turn context:** Allow follow-up queries that refine the previous visualization.
- **More aggregation types:** Enrollment counts, study duration analysis, outcome-based filtering.

---

## Tools Used

- **Claude Code (Anthropic):** Used for architecture design, code generation, and iterative refinement
- **ClinicalTrials.gov API v2:** Live API testing to validate endpoint behavior, response structure, and query parameters
- **OpenAI gpt-4.1 / gpt-4.1-mini:** LLM backbone for query analysis and narration

### Validation Approach
- 55 tests covering data processing, citation extraction, visualization building, input validation, security (prompt injection, rate limiting), integration (real ClinicalTrials.gov API), and robustness (novel drugs, missing fields, edge cases)
- Anti-hallucination tests that independently verify aggregated counts match raw input data and all NCT IDs are traceable
- End-to-end integration tests against live ClinicalTrials.gov API with real queries
- All data transformation is deterministic and reproducible

### Deliberate Design vs. Generated Code
- **Architecture (Data Firewall pattern, anti-hallucination strategy, two-phase LLM design):** Deliberately designed based on the constraint that medical data must be grounded in source
- **System prompts:** Carefully crafted with few-shot examples, safety rules, and data visualization best practices
- **Pydantic schemas:** Designed to enforce contracts at every boundary
- **Service implementations:** Generated and then reviewed/refined for correctness, edge case handling, and code clarity
