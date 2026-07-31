import React, { useState } from "react";

const EXAMPLE_QUERIES = [
  {
    label: "Pembrolizumab over time",
    query: "How has the number of trials for Pembrolizumab changed over time?",
    filters: { drug_name: "Pembrolizumab" },
  },
  {
    label: "Diabetes phase distribution",
    query: "How are diabetes trials distributed across phases?",
    filters: { condition: "diabetes" },
  },
  {
    label: "Pembrolizumab vs Nivolumab",
    query:
      "Compare the phase distribution of trials for Pembrolizumab vs Nivolumab",
    filters: {},
  },
  {
    label: "Top countries for oncology",
    query: "Which countries have the most recruiting oncology trials?",
    filters: { condition: "cancer" },
  },
  {
    label: "Breast cancer drug network",
    query: "Show a network of drugs and conditions in breast cancer trials",
    filters: { condition: "breast cancer" },
  },
];

const PHASES = ["", "Phase 1", "Phase 2", "Phase 3", "Phase 4"];

export default function QueryPanel({ onSubmit, loading }) {
  const [query, setQuery] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [drugName, setDrugName] = useState("");
  const [condition, setCondition] = useState("");
  const [trialPhase, setTrialPhase] = useState("");
  const [sponsor, setSponsor] = useState("");
  const [country, setCountry] = useState("");
  const [startYear, setStartYear] = useState("");
  const [endYear, setEndYear] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 10) return;

    const payload = { query: query.trim() };
    if (drugName.trim()) payload.drug_name = drugName.trim();
    if (condition.trim()) payload.condition = condition.trim();
    if (trialPhase) payload.trial_phase = trialPhase;
    if (sponsor.trim()) payload.sponsor = sponsor.trim();
    if (country.trim()) payload.country = country.trim();
    if (startYear) payload.start_year = parseInt(startYear, 10);
    if (endYear) payload.end_year = parseInt(endYear, 10);

    onSubmit(payload);
  };

  const handleExampleClick = (example) => {
    setQuery(example.query);
    setDrugName(example.filters.drug_name || "");
    setCondition(example.filters.condition || "");
    setTrialPhase(example.filters.trial_phase || "");
    setSponsor(example.filters.sponsor || "");
    setCountry(example.filters.country || "");
    setStartYear(example.filters.start_year?.toString() || "");
    setEndYear(example.filters.end_year?.toString() || "");

    if (
      example.filters.drug_name ||
      example.filters.condition ||
      example.filters.trial_phase ||
      example.filters.sponsor ||
      example.filters.country ||
      example.filters.start_year ||
      example.filters.end_year
    ) {
      setFiltersOpen(true);
    }
  };

  const activeFilterCount = [
    drugName,
    condition,
    trialPhase,
    sponsor,
    country,
    startYear,
    endYear,
  ].filter(Boolean).length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-4 border-b border-slate-100">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
          Query
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="p-4 flex flex-col gap-4">
        {/* Main Query Input */}
        <div>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about clinical trials..."
            rows={3}
            maxLength={1000}
            className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500 resize-none transition-colors"
          />
          <div className="flex justify-between mt-1">
            <p className="text-xs text-slate-400">Min 10 characters</p>
            <p className="text-xs text-slate-400">{query.length}/1000</p>
          </div>
        </div>

        {/* Advanced Filters Toggle */}
        <button
          type="button"
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-800 transition-colors self-start"
        >
          <svg
            className={`w-4 h-4 transition-transform ${filtersOpen ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.25 4.5l7.5 7.5-7.5 7.5"
            />
          </svg>
          Advanced Filters
          {activeFilterCount > 0 && (
            <span className="bg-teal-100 text-teal-700 text-xs font-medium px-1.5 py-0.5 rounded-full">
              {activeFilterCount}
            </span>
          )}
        </button>

        {/* Filters Section */}
        {filtersOpen && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Drug Name
              </label>
              <input
                type="text"
                value={drugName}
                onChange={(e) => setDrugName(e.target.value)}
                placeholder="e.g. Pembrolizumab"
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Condition
              </label>
              <input
                type="text"
                value={condition}
                onChange={(e) => setCondition(e.target.value)}
                placeholder="e.g. diabetes"
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Trial Phase
              </label>
              <select
                value={trialPhase}
                onChange={(e) => setTrialPhase(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500 bg-white"
              >
                {PHASES.map((p) => (
                  <option key={p} value={p}>
                    {p || "Any phase"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Sponsor
              </label>
              <input
                type="text"
                value={sponsor}
                onChange={(e) => setSponsor(e.target.value)}
                placeholder="e.g. Pfizer"
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Country
              </label>
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="e.g. United States"
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Start Year
                </label>
                <input
                  type="number"
                  value={startYear}
                  onChange={(e) => setStartYear(e.target.value)}
                  placeholder="1990"
                  min={1990}
                  max={2030}
                  className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  End Year
                </label>
                <input
                  type="number"
                  value={endYear}
                  onChange={(e) => setEndYear(e.target.value)}
                  placeholder="2030"
                  min={1990}
                  max={2030}
                  className="w-full px-2.5 py-1.5 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || query.trim().length < 10}
          className="w-full py-2.5 px-4 bg-gradient-to-r from-teal-600 to-primary-600 text-white text-sm font-semibold rounded-lg hover:from-teal-700 hover:to-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                />
              </svg>
              Analyze
            </>
          )}
        </button>
      </form>

      {/* Example Queries */}
      <div className="p-4 border-t border-slate-100">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
          Example Queries
        </p>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_QUERIES.map((example, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleExampleClick(example)}
              disabled={loading}
              className="px-2.5 py-1 bg-slate-100 text-slate-600 text-xs rounded-full hover:bg-teal-50 hover:text-teal-700 transition-colors disabled:opacity-50"
            >
              {example.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
