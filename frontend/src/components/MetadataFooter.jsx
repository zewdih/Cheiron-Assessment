import React from "react";

export default function MetadataFooter({ meta, queryInterpretation }) {
  if (!meta) return null;

  const formatTimestamp = (ts) => {
    try {
      const date = new Date(ts);
      return date.toLocaleString();
    } catch {
      return ts;
    }
  };

  const activeFilters = Object.entries(meta.filters || {}).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-4">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Query Metadata
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-slate-400">Studies Analyzed</p>
            <p className="text-lg font-semibold text-slate-800">
              {meta.total_studies_analyzed?.toLocaleString() ?? "N/A"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Source</p>
            <p className="text-sm font-medium text-slate-700">
              {meta.source || "clinicaltrials.gov"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">API Version</p>
            <p className="text-sm font-medium text-slate-700">
              {meta.api_version || "v2"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Timestamp</p>
            <p className="text-sm font-medium text-slate-700">
              {formatTimestamp(meta.timestamp)}
            </p>
          </div>
        </div>

        {/* Active Filters */}
        {activeFilters.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-400 mb-1.5">Applied Filters</p>
            <div className="flex flex-wrap gap-1.5">
              {activeFilters.map(([key, val]) => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-xs rounded"
                >
                  <span className="text-slate-500">{key}:</span>
                  <span className="text-slate-700 font-medium">
                    {String(val)}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Original Query */}
        {meta.query && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-400 mb-1">Original Query</p>
            <p className="text-sm text-slate-600 italic">
              &ldquo;{meta.query}&rdquo;
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
