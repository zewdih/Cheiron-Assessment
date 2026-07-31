import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import NetworkGraph from "./NetworkGraph.jsx";

const COLORS = [
  "#0d9488",
  "#2563eb",
  "#7c3aed",
  "#db2777",
  "#ea580c",
  "#65a30d",
  "#0891b2",
  "#6366f1",
  "#e11d48",
  "#ca8a04",
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-sm max-w-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-slate-500">{entry.name}:</span>
          <span className="font-medium text-slate-800">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function ChartRenderer({ visualization, onDataPointClick }) {
  const { type, encoding, data, network_data } = visualization;

  const xField = encoding.x?.field;
  const yField = encoding.y?.field;
  const colorField = encoding.color?.field;
  const xTitle = encoding.x?.title || xField;
  const yTitle = encoding.y?.title || yField;

  // Transform data points for Recharts
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.map((dp) => ({
      ...dp.values,
      _citations: dp.citations,
    }));
  }, [data]);

  // Find groups for grouped bar chart
  const groups = useMemo(() => {
    if (type !== "grouped_bar_chart" || !colorField) return [];
    const groupSet = new Set();
    chartData.forEach((d) => {
      if (d[colorField]) groupSet.add(d[colorField]);
    });
    return Array.from(groupSet);
  }, [type, colorField, chartData]);

  // For grouped bar chart, pivot data so each x value has multiple group columns
  const groupedData = useMemo(() => {
    if (type !== "grouped_bar_chart" || groups.length === 0) return chartData;

    const pivoted = {};
    chartData.forEach((d) => {
      const xVal = d[xField];
      if (!pivoted[xVal]) {
        pivoted[xVal] = { [xField]: xVal, _allCitations: [] };
      }
      const groupVal = d[colorField];
      pivoted[xVal][groupVal] = d[yField];
      if (d._citations) {
        pivoted[xVal][`_citations_${groupVal}`] = d._citations;
        pivoted[xVal]._allCitations.push(...d._citations);
      }
    });
    return Object.values(pivoted);
  }, [type, groups, chartData, xField, yField, colorField]);

  const handleBarClick = (dataItem, index) => {
    if (!dataItem) return;
    const original = data[index];
    if (original) {
      onDataPointClick({
        values: original.values,
        citations: original.citations,
      });
    }
  };

  const handleGroupedBarClick = (dataItem, groupName) => {
    if (!dataItem) return;
    const citations = dataItem[`_citations_${groupName}`] || [];
    onDataPointClick({
      values: {
        [xField]: dataItem[xField],
        [colorField]: groupName,
        [yField]: dataItem[groupName],
      },
      citations,
    });
  };

  // Network graph
  if (type === "network_graph") {
    return (
      <NetworkGraph
        networkData={network_data}
        onEdgeClick={(edge) =>
          onDataPointClick({
            values: {
              source: edge.source,
              target: edge.target,
              weight: edge.weight,
            },
            citations: edge.citations || [],
          })
        }
      />
    );
  }

  // Time series
  if (type === "time_series") {
    return (
      <ResponsiveContainer width="100%" height={450}>
        <LineChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 40 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey={xField}
            tick={{ fill: "#64748b", fontSize: 11 }}
            interval={0}
          />
          <YAxis
            label={{ value: yTitle, angle: -90, position: "insideLeft", offset: 0, style: { fill: "#64748b", fontSize: 12 } }}
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey={yField}
            stroke={COLORS[0]}
            strokeWidth={2}
            dot={{ fill: COLORS[0], r: 4, cursor: "pointer" }}
            activeDot={{
              r: 6,
              cursor: "pointer",
              onClick: (e, payload) => {
                const idx = payload.index;
                if (data[idx]) {
                  onDataPointClick({
                    values: data[idx].values,
                    citations: data[idx].citations,
                  });
                }
              },
            }}
            name={yTitle}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // Bar chart / histogram
  if (type === "bar_chart" || type === "histogram") {
    const needsAngle = chartData.length > 5 || chartData.some((d) => String(d[xField] || "").length > 10);
    return (
      <ResponsiveContainer width="100%" height={450}>
        <BarChart
          data={chartData}
          margin={{ top: 10, right: 30, left: 20, bottom: needsAngle ? 80 : 40 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey={xField}
            tick={{ fill: "#64748b", fontSize: 11, angle: needsAngle ? -35 : 0, textAnchor: needsAngle ? "end" : "middle" }}
            interval={0}
            height={needsAngle ? 80 : 40}
          />
          <YAxis
            label={{ value: yTitle, angle: -90, position: "insideLeft", offset: 0, style: { fill: "#64748b", fontSize: 12 } }}
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar
            dataKey={yField}
            name={yTitle}
            radius={[4, 4, 0, 0]}
            cursor="pointer"
            onClick={(dataItem, index) => handleBarClick(dataItem, index)}
            label={{ position: "top", fill: "#475569", fontSize: 11 }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // Grouped bar chart
  if (type === "grouped_bar_chart") {
    const needsAngle = groupedData.length > 5 || groupedData.some((d) => String(d[xField] || "").length > 10);
    return (
      <ResponsiveContainer width="100%" height={450}>
        <BarChart
          data={groupedData}
          margin={{ top: 10, right: 30, left: 20, bottom: needsAngle ? 80 : 40 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey={xField}
            tick={{ fill: "#64748b", fontSize: 11, angle: needsAngle ? -35 : 0, textAnchor: needsAngle ? "end" : "middle" }}
            interval={0}
            height={needsAngle ? 80 : 40}
          />
          <YAxis
            label={{ value: yTitle, angle: -90, position: "insideLeft", offset: 0, style: { fill: "#64748b", fontSize: 12 } }}
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          {groups.map((group, i) => (
            <Bar
              key={group}
              dataKey={group}
              name={group}
              fill={COLORS[i % COLORS.length]}
              radius={[4, 4, 0, 0]}
              cursor="pointer"
              onClick={(dataItem) => handleGroupedBarClick(dataItem, group)}
              label={{ position: "top", fill: "#475569", fontSize: 10 }}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // Scatter plot
  if (type === "scatter_plot") {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey={xField}
            name={xTitle}
            label={{ value: xTitle, position: "insideBottom", offset: -5, style: { fill: "#64748b", fontSize: 12 } }}
            tick={{ fill: "#64748b", fontSize: 11 }}
            type="number"
          />
          <YAxis
            dataKey={yField}
            name={yTitle}
            label={{ value: yTitle, angle: -90, position: "insideLeft", offset: 10, style: { fill: "#64748b", fontSize: 12 } }}
            tick={{ fill: "#64748b", fontSize: 11 }}
            type="number"
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ strokeDasharray: "3 3" }}
          />
          <Scatter
            data={chartData}
            fill={COLORS[0]}
            cursor="pointer"
            onClick={(point) => {
              const idx = chartData.indexOf(point);
              if (idx >= 0 && data[idx]) {
                onDataPointClick({
                  values: data[idx].values,
                  citations: data[idx].citations,
                });
              }
            }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  // Fallback
  return (
    <div className="text-center py-12 text-slate-500">
      <p>Unsupported visualization type: {type}</p>
    </div>
  );
}
