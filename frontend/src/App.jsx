import React, { useState, useCallback } from "react";
import QueryPanel from "./components/QueryPanel.jsx";
import VisualizationPanel from "./components/VisualizationPanel.jsx";
import CitationsPanel from "./components/CitationsPanel.jsx";
import MetadataFooter from "./components/MetadataFooter.jsx";

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCitations, setSelectedCitations] = useState(null);

  const handleSubmit = useCallback(async (payload) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedCitations(null);

    try {
      const res = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const message =
          body?.detail ||
          (Array.isArray(body?.detail)
            ? body.detail.map((d) => d.msg).join("; ")
            : `Request failed with status ${res.status}`);
        throw new Error(typeof message === "string" ? message : JSON.stringify(message));
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDataPointClick = useCallback((dataPoint) => {
    if (dataPoint && dataPoint.citations && dataPoint.citations.length > 0) {
      setSelectedCitations(dataPoint);
    }
  }, []);

  const closeCitations = useCallback(() => {
    setSelectedCitations(null);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-teal-500 to-primary-600 flex items-center justify-center text-white font-bold text-lg flex-shrink-0">
            C
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 leading-tight">
              Cheiron
            </h1>
            <p className="text-xs text-slate-500 leading-tight">
              Clinical Trials Visualization Agent
            </p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
          {/* Left Column: Query Panel */}
          <div className="lg:sticky lg:top-6 lg:self-start">
            <QueryPanel onSubmit={handleSubmit} loading={loading} />
          </div>

          {/* Right Column: Visualization + Citations */}
          <div className="flex flex-col gap-6 min-w-0">
            {/* Error State */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <svg
                    className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                  <div>
                    <h3 className="text-sm font-semibold text-red-800">
                      Error
                    </h3>
                    <p className="text-sm text-red-700 mt-1">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 flex flex-col items-center justify-center gap-4">
                <div className="w-10 h-10 border-3 border-slate-200 border-t-teal-500 rounded-full animate-spin" />
                <div className="text-center">
                  <p className="text-sm font-medium text-slate-700">
                    Retrieving and analyzing clinical trials data...
                  </p>
                  <p className="text-xs text-slate-400 mt-2 max-w-xs">
                    We query ClinicalTrials.gov directly and verify every data point against its source to ensure accuracy. This typically takes 5-8 seconds.
                  </p>
                </div>
              </div>
            )}

            {/* Empty State */}
            {!loading && !result && !error && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 flex flex-col items-center justify-center gap-4 text-center">
                <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v-5.5m3 5.5V8.75"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-700">
                    Ready to visualize
                  </h3>
                  <p className="text-sm text-slate-500 mt-1 max-w-sm">
                    Enter a natural language query about clinical trials to
                    generate an interactive visualization.
                  </p>
                </div>
              </div>
            )}

            {/* Visualization */}
            {result && !loading && (
              <>
                <VisualizationPanel
                  visualization={result.visualization}
                  onDataPointClick={handleDataPointClick}
                />

                {/* Citations Panel */}
                {selectedCitations && (
                  <CitationsPanel
                    dataPoint={selectedCitations}
                    onClose={closeCitations}
                  />
                )}

                {/* Metadata Footer */}
                <MetadataFooter
                  meta={result.meta}
                  queryInterpretation={
                    result.visualization.query_interpretation
                  }
                />
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white mt-auto">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-3 text-center text-xs text-slate-400">
          Cheiron Clinical Trials Visualization Agent &middot; Data sourced from
          ClinicalTrials.gov
        </div>
      </footer>
    </div>
  );
}
