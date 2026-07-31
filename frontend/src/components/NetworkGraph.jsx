import React, { useRef, useCallback, useEffect, useMemo } from "react";

const NODE_COLORS = {
  drug: "#0d9488",
  condition: "#2563eb",
  sponsor: "#7c3aed",
  intervention: "#0d9488",
  default: "#64748b",
};

export default function NetworkGraph({ networkData, onEdgeClick }) {
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const ForceGraph = useRef(null);
  const [mounted, setMounted] = React.useState(false);

  // Dynamically import react-force-graph-2d (it requires window/document)
  useEffect(() => {
    let cancelled = false;
    import("react-force-graph-2d").then((mod) => {
      if (!cancelled) {
        ForceGraph.current = mod.default;
        setMounted(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const graphData = useMemo(() => {
    if (!networkData) return { nodes: [], links: [] };

    const nodes = (networkData.nodes || []).map((n) => ({
      id: n.id,
      type: n.type,
      color: NODE_COLORS[n.type?.toLowerCase()] || NODE_COLORS.default,
    }));

    const links = (networkData.edges || []).map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
      citations: e.citations || [],
    }));

    return { nodes, links };
  }, [networkData]);

  const handleLinkClick = useCallback(
    (link) => {
      if (onEdgeClick) {
        onEdgeClick({
          source: typeof link.source === "object" ? link.source.id : link.source,
          target: typeof link.target === "object" ? link.target.id : link.target,
          weight: link.weight,
          citations: link.citations,
        });
      }
    },
    [onEdgeClick]
  );

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const label = node.id;
    const fontSize = Math.max(10 / globalScale, 3);
    const radius = Math.max(5, 3 + (node.val || 1));

    // Draw node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || "#64748b";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    // Draw label
    ctx.font = `${fontSize}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#334155";
    ctx.fillText(label, node.x, node.y + radius + 2);
  }, []);

  const linkCanvasObject = useCallback((link, ctx, globalScale) => {
    const start = link.source;
    const end = link.target;
    if (!start || !end || typeof start.x === "undefined") return;

    const lineWidth = Math.max(1, Math.min(link.weight || 1, 8)) / globalScale;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }, []);

  if (!networkData || (!networkData.nodes?.length && !networkData.edges?.length)) {
    return (
      <div className="text-center py-12 text-slate-500">
        <p>No network data available.</p>
      </div>
    );
  }

  if (!mounted || !ForceGraph.current) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-slate-200 border-t-teal-500 rounded-full animate-spin" />
      </div>
    );
  }

  const FG = ForceGraph.current;

  // Build a simple legend from node types
  const nodeTypes = [
    ...new Set(graphData.nodes.map((n) => n.type?.toLowerCase()).filter(Boolean)),
  ];

  return (
    <div>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-3">
        {nodeTypes.map((t) => (
          <div key={t} className="flex items-center gap-1.5 text-xs text-slate-600">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: NODE_COLORS[t] || NODE_COLORS.default }}
            />
            <span className="capitalize">{t}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-xs text-slate-400 ml-auto">
          Click an edge to see citations
        </div>
      </div>

      <div
        ref={containerRef}
        className="border border-slate-200 rounded-lg overflow-hidden bg-slate-50"
        style={{ height: 450 }}
      >
        <FG
          ref={graphRef}
          graphData={graphData}
          width={containerRef.current?.offsetWidth || 700}
          height={450}
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={(node, color, ctx) => {
            const radius = Math.max(5, 3 + (node.val || 1));
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          linkCanvasObject={linkCanvasObject}
          linkPointerAreaPaint={(link, color, ctx) => {
            const start = link.source;
            const end = link.target;
            if (!start || !end || typeof start.x === "undefined") return;
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(end.x, end.y);
            ctx.strokeStyle = color;
            ctx.lineWidth = 8;
            ctx.stroke();
          }}
          onLinkClick={handleLinkClick}
          cooldownTicks={100}
          enableZoomInteraction={true}
          enablePanInteraction={true}
        />
      </div>
    </div>
  );
}