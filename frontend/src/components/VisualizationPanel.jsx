import React from "react";
import ChartRenderer from "./ChartRenderer.jsx";

export default function VisualizationPanel({ visualization, onDataPointClick }) {
  const { title, notes, query_interpretation, type } = visualization;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Chart Header */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-teal-50 text-teal-700 border border-teal-100">
            {type.replace(/_/g, " ")}
          </span>
        </div>
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      </div>

      {/* Chart Body */}
      <div className="p-4">
        <ChartRenderer
          visualization={visualization}
          onDataPointClick={onDataPointClick}
        />
      </div>

      {/* Notes */}
      {notes && (
        <div className="px-4 pb-4">
          <div className="bg-primary-50 border border-primary-100 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <svg
                className="w-4 h-4 text-primary-500 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
                />
              </svg>
              <p className="text-sm text-primary-800">{notes}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
