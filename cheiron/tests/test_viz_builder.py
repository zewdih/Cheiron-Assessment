"""Tests for the visualization spec builder."""

import pytest
from cheiron.services.viz_builder import VizBuilder
from cheiron.models.query_plan import (
    QueryPlan,
    QueryType,
    VisualizationType,
    GroupByField,
    DateField,
    AggregationMethod,
    APIParams,
)


def _make_plan(**kwargs) -> QueryPlan:
    defaults = {
        "query_type": QueryType.DISTRIBUTION,
        "suggested_viz": VisualizationType.BAR_CHART,
        "primary_entity": "TestDrug",
        "group_by": [GroupByField.PHASE],
        "aggregation": AggregationMethod.COUNT,
        "api_params": APIParams(query_intr="TestDrug"),
        "fields_needed": ["NCTId", "BriefTitle", "Phase"],
        "reasoning": "test",
    }
    defaults.update(kwargs)
    return QueryPlan(**defaults)


@pytest.fixture
def builder():
    return VizBuilder()


class TestStandardVisualization:
    def test_bar_chart_structure(self, builder):
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [
                {"phase": "PHASE3", "trial_count": 10, "_nct_ids": ["NCT001"]},
                {"phase": "PHASE1", "trial_count": 5, "_nct_ids": ["NCT002"]},
            ],
            "total_studies": 15,
        }
        citations = {
            "PHASE3": [{"nct_id": "NCT001", "url": "https://clinicaltrials.gov/study/NCT001", "excerpt": "Test"}],
            "PHASE1": [{"nct_id": "NCT002", "url": "https://clinicaltrials.gov/study/NCT002", "excerpt": "Test"}],
        }
        plan = _make_plan()
        spec = builder.build(aggregated, plan, citations, title="Test Title", notes="Test notes")

        assert spec.type == "bar_chart"
        assert spec.title == "Test Title"
        assert spec.encoding.x.field == "phase"
        assert spec.encoding.y.field == "trial_count"
        assert spec.encoding.y.type == "quantitative"
        assert len(spec.data) == 2
        assert spec.data[0].values["phase"] == "PHASE3"
        assert spec.data[0].values["trial_count"] == 10
        assert "_nct_ids" not in spec.data[0].values  # stripped

    def test_citations_attached_to_data_points(self, builder):
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [
                {"phase": "PHASE3", "trial_count": 1, "_nct_ids": ["NCT001"]},
            ],
            "total_studies": 1,
        }
        citations = {
            "PHASE3": [{"nct_id": "NCT001", "url": "https://clinicaltrials.gov/study/NCT001", "excerpt": "My excerpt"}],
        }
        plan = _make_plan()
        spec = builder.build(aggregated, plan, citations)

        assert len(spec.data[0].citations) == 1
        assert spec.data[0].citations[0].nct_id == "NCT001"
        assert spec.data[0].citations[0].excerpt == "My excerpt"

    def test_internal_fields_stripped(self, builder):
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [
                {"phase": "PHASE3", "trial_count": 5, "_nct_ids": ["a", "b"]},
            ],
            "total_studies": 5,
        }
        plan = _make_plan()
        spec = builder.build(aggregated, plan, {})

        for dp in spec.data:
            assert "_nct_ids" not in dp.values


class TestTimeSeries:
    def test_temporal_encoding(self, builder):
        aggregated = {
            "query_type": "time_trend",
            "x_field": "year",
            "y_field": "trial_count",
            "data_points": [
                {"year": 2020, "trial_count": 10, "_nct_ids": []},
            ],
            "total_studies": 10,
        }
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            suggested_viz=VisualizationType.TIME_SERIES,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        spec = builder.build(aggregated, plan, {})

        assert spec.type == "time_series"
        assert spec.encoding.x.type == "temporal"


class TestNetworkVisualization:
    def test_network_structure(self, builder):
        aggregated = {
            "query_type": "relationship_network",
            "nodes": [
                {"id": "DrugA", "type": "intervention"},
                {"id": "Cancer", "type": "condition"},
            ],
            "edges": [
                {"source": "DrugA", "target": "Cancer", "weight": 5, "_nct_ids": ["NCT001"]},
            ],
            "total_studies": 5,
        }
        citations = {
            "DrugA->Cancer": [{"nct_id": "NCT001", "url": "https://clinicaltrials.gov/study/NCT001", "excerpt": "Test"}],
        }
        plan = _make_plan(
            query_type=QueryType.RELATIONSHIP_NETWORK,
            suggested_viz=VisualizationType.NETWORK_GRAPH,
            group_by=[GroupByField.INTERVENTION, GroupByField.CONDITION],
        )
        spec = builder.build(aggregated, plan, citations)

        assert spec.type == "network_graph"
        assert spec.network_data is not None
        assert len(spec.network_data["nodes"]) == 2
        assert len(spec.network_data["edges"]) == 1
        assert spec.network_data["edges"][0]["weight"] == 5
