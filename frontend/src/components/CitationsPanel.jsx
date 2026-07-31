import React from "react";

export default function CitationsPanel({ dataPoint, onClose }) {
  if (!dataPoint) return null;

  const { values, citations } = dataPoint;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">
            Citations
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {citations.length} source{citations.length !== 1 ? "s" : ""} for
            selected data point
          </p>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-md hover:bg-slate-100 flex items-center justify-center transition-colors"
          aria-label="Close citations"
        >
          <svg
            className="w-4 h-4 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Selected Data Point Summary */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex flex-wrap gap-2">
          {Object.entries(values).map(([key, val]) => (
            <span
              key={key}
              className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 rounded text-xs"
            >
              <span className="text-slate-500">{key}:</span>
              <span className="font-medium text-slate-700">{String(val)}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Citations List */}
      <div className="p-4 space-y-3 max-h-80 overflow-y-auto">
        {citations.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">
            No citations available for this data point.
          </p>
        ) : (
          citations.map((citation, i) => (
            <div
              key={`${citation.nct_id}-${i}`}
              className="border border-slate-100 rounded-lg p-3 hover:border-slate-200 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <a
                  href={citation.url || `https://clinicaltrials.gov/study/${citation.nct_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-semibold text-teal-600 hover:text-teal-700 hover:underline flex items-center gap-1"
                >
                  {citation.nct_id}
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                    />
                  </svg>
                </a>
              </div>
              {citation.excerpt && (
                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                  {citation.excerpt}
                </p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
