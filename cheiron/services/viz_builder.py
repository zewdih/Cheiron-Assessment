from cheiron.models.query_plan import QueryPlan
from cheiron.models.visualization import (
    VisualizationSpec,
    Encoding,
    AxisEncoding,
    DataPoint,
    Citation,
)


class VizBuilder:
    """Deterministic assembly of the visualization specification.

    Combines aggregated data, citations, and narration into a frontend-friendly
    VisualizationSpec. No LLM is called here.
    """

    def build(
        self,
        aggregated: dict,
        plan: QueryPlan,
        citations: dict[str, list[dict]],
        title: str = "",
        notes: str = "",
    ) -> VisualizationSpec:
        viz_type = plan.suggested_viz.value
        query_type = aggregated["query_type"]

        if query_type == "relationship_network":
            return self._build_network(aggregated, citations, title, notes, plan)

        encoding = self._build_encoding(aggregated, plan)

        if query_type == "comparison":
            data_points = self._build_comparison_data(aggregated, citations)
        else:
            data_points = self._build_standard_data(aggregated, citations)

        return VisualizationSpec(
            type=viz_type,
            title=title,
            encoding=encoding,
            data=data_points,
            notes=notes,
            query_interpretation=plan.reasoning,
        )

    def _build_encoding(self, aggregated: dict, plan: QueryPlan) -> Encoding:
        x_field = aggregated.get("x_field", "category")
        y_field = aggregated.get("y_field", "trial_count")
        series_field = aggregated.get("series_field")

        x_type = "temporal" if x_field == "year" else "nominal"
        encoding = Encoding(
            x=AxisEncoding(field=x_field, type=x_type, title=self._field_title(x_field)),
            y=AxisEncoding(field=y_field, type="quantitative", title="Number of Trials"),
        )
        if series_field:
            encoding.color = AxisEncoding(
                field=series_field, type="nominal", title=self._field_title(series_field)
            )
        return encoding

    def _build_standard_data(
        self, aggregated: dict, citations: dict[str, list[dict]]
    ) -> list[DataPoint]:
        x_field = aggregated.get("x_field")
        data_points = []
        for dp in aggregated.get("data_points", []):
            clean = {k: v for k, v in dp.items() if not k.startswith("_")}
            key = str(dp.get(x_field, ""))
            cites = [Citation(**c) for c in citations.get(key, [])]
            data_points.append(DataPoint(values=clean, citations=cites))
        return data_points

    def _build_comparison_data(
        self, aggregated: dict, citations: dict[str, list[dict]]
    ) -> list[DataPoint]:
        data_points = []
        x_field = aggregated.get("x_field")
        for series_item in aggregated.get("series", []):
            entity = series_item["entity"]
            for dp in series_item["data_points"]:
                clean = {k: v for k, v in dp.items() if not k.startswith("_")}
                clean["entity"] = entity
                key = f"{entity}:{dp.get(x_field, '')}"
                cites = [Citation(**c) for c in citations.get(key, [])]
                data_points.append(DataPoint(values=clean, citations=cites))
        return data_points

    def _build_network(
        self,
        aggregated: dict,
        citations: dict[str, list[dict]],
        title: str,
        notes: str,
        plan: QueryPlan,
    ) -> VisualizationSpec:
        network_nodes = aggregated.get("nodes", [])
        network_edges = []
        for edge in aggregated.get("edges", []):
            key = f"{edge['source']}->{edge['target']}"
            cites = [Citation(**c) for c in citations.get(key, [])]
            network_edges.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "weight": edge["weight"],
                    "citations": [c.model_dump() for c in cites],
                }
            )

        return VisualizationSpec(
            type="network_graph",
            title=title,
            encoding=Encoding(nodes="id", edges="source,target"),
            network_data={"nodes": network_nodes, "edges": network_edges},
            notes=notes,
            query_interpretation=plan.reasoning,
        )

    def _field_title(self, field: str) -> str:
        return field.replace("_", " ").title()