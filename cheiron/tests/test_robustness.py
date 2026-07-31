"""Robustness tests for unseen/novel queries.

These tests verify that the system gracefully handles query patterns it
was NOT explicitly designed or few-shot-prompted for. The deterministic
pipeline should produce valid output for any well-formed API response,
regardless of what question triggered it.
"""

import pytest
from cheiron.services.data_processor import DataProcessor
from cheiron.services.citation_extractor import CitationExtractor
from cheiron.services.viz_builder import VizBuilder
from cheiron.services.ct_client import CTClient
from cheiron.models.query_plan import (
    QueryPlan,
    QueryType,
    VisualizationType,
    GroupByField,
    DateField,
    AggregationMethod,
    APIParams,
)
from cheiron.models.response import QueryResponse


@pytest.fixture
def processor():
    return DataProcessor()


@pytest.fixture
def citation_extractor():
    return CitationExtractor()


@pytest.fixture
def viz_builder():
    return VizBuilder()


class TestNovelDrugQueries:
    """Test with drugs/conditions the system has never seen in examples."""

    @pytest.mark.asyncio
    async def test_rare_drug_semaglutide(self, processor, citation_extractor, viz_builder):
        """Semaglutide (GLP-1 agonist) - not in any examples."""
        plan = QueryPlan(
            query_type=QueryType.TIME_TREND,
            suggested_viz=VisualizationType.TIME_SERIES,
            primary_entity="Semaglutide",
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
            api_params=APIParams(query_intr="Semaglutide"),
            fields_needed=["NCTId", "BriefTitle", "StartDate", "Phase", "OverallStatus", "LeadSponsorName"],
            max_results=100,
            reasoning="Novel query test",
        )
        result = await self._run_pipeline(plan, processor, citation_extractor, viz_builder)
        assert result.visualization.type == "time_series"
        assert len(result.visualization.data) > 0

    @pytest.mark.asyncio
    async def test_rare_condition_lupus(self, processor, citation_extractor, viz_builder):
        """Lupus - not in any examples."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="lupus",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_cond="lupus"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "OverallStatus", "LeadSponsorName"],
            max_results=100,
            reasoning="Novel condition test",
        )
        result = await self._run_pipeline(plan, processor, citation_extractor, viz_builder)
        assert result.visualization.type == "bar_chart"
        assert len(result.visualization.data) > 0

    @pytest.mark.asyncio
    async def test_sponsor_grouping_novel(self, processor, citation_extractor, viz_builder):
        """Group by sponsor class - a grouping not heavily tested."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="COVID-19",
            group_by=[GroupByField.SPONSOR_CLASS],
            api_params=APIParams(query_cond="COVID-19"),
            fields_needed=["NCTId", "BriefTitle", "LeadSponsorClass", "OverallStatus", "LeadSponsorName"],
            max_results=200,
            reasoning="Novel grouping test",
        )
        result = await self._run_pipeline(plan, processor, citation_extractor, viz_builder)
        assert result.visualization.type == "bar_chart"
        # Should see INDUSTRY, OTHER, NIH, etc.
        categories = [dp.values.get("sponsor_class") for dp in result.visualization.data]
        assert len(categories) > 0

    async def _run_pipeline(self, plan, processor, citation_extractor, viz_builder):
        """Run the deterministic pipeline (no LLM) and return a valid QueryResponse."""
        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        assert len(raw_studies) > 0 if isinstance(raw_studies, list) else sum(len(v) for v in raw_studies.values()) > 0

        aggregated = processor.process(raw_studies, plan)
        citations = citation_extractor.extract(raw_studies, aggregated)
        viz = viz_builder.build(aggregated, plan, citations, title="Test", notes="Test")

        from cheiron.models.visualization import ResponseMeta
        from datetime import datetime, timezone

        response = QueryResponse(
            visualization=viz,
            meta=ResponseMeta(
                query="test",
                total_studies_analyzed=aggregated.get("total_studies", 0),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )
        # This validates the entire response schema
        QueryResponse.model_validate(response.model_dump())
        return response


class TestEdgeCases:
    """Test edge cases the system might encounter with real-world data."""

    @pytest.mark.asyncio
    async def test_very_narrow_query_few_results(self, processor, citation_extractor, viz_builder):
        """A very specific query that might return very few results."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="zanubrutinib",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_intr="zanubrutinib"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "OverallStatus", "LeadSponsorName"],
            max_results=50,
            reasoning="Narrow query test",
        )
        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        # Even with few results, the pipeline should work
        aggregated = processor.process(raw_studies, plan)
        citations = citation_extractor.extract(raw_studies, aggregated)

        # Data points should be verifiable — total_from_points >= total_studies
        # because multi-phase studies (e.g., PHASE1/PHASE2) count in each phase
        total_from_points = sum(dp["trial_count"] for dp in aggregated.get("data_points", []))
        assert total_from_points >= aggregated["total_studies"]
        assert len(aggregated.get("data_points", [])) > 0

    def test_study_with_missing_fields(self, processor):
        """Studies with missing optional fields should not crash the processor."""
        sparse_studies = [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT001", "briefTitle": "Sparse Study"},
                    # Missing: statusModule, designModule, sponsorCollaboratorsModule, etc.
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT002", "briefTitle": "Also Sparse"},
                    "statusModule": {},  # Empty but present
                    "designModule": {},
                }
            },
        ]
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="test",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_term="test"),
            fields_needed=["NCTId", "BriefTitle", "Phase"],
            reasoning="Missing fields test",
        )
        # Should not raise
        result = processor.process(sparse_studies, plan)
        assert result["total_studies"] == 2

    def test_study_with_multiple_conditions_and_interventions(self, processor):
        """Studies with multiple conditions and interventions should count correctly."""
        studies = [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT001", "briefTitle": "Multi"},
                    "conditionsModule": {
                        "conditions": ["Cancer", "Diabetes", "Heart Disease"]
                    },
                    "armsInterventionsModule": {
                        "interventions": [
                            {"name": "DrugA", "type": "DRUG"},
                            {"name": "DrugB", "type": "DRUG"},
                            {"name": "ProcedureC", "type": "PROCEDURE"},
                        ]
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "designModule": {"phases": ["PHASE2"]},
                }
            }
        ]
        # Test condition distribution — the study should count for each condition
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="multi",
            group_by=[GroupByField.CONDITION],
            api_params=APIParams(query_term="multi"),
            fields_needed=["NCTId", "BriefTitle", "Condition"],
            reasoning="Multi-value test",
        )
        result = processor.process(studies, plan)
        # Each condition gets counted
        conditions = {dp["condition"] for dp in result["data_points"]}
        assert "Cancer" in conditions
        assert "Diabetes" in conditions
        assert "Heart Disease" in conditions

    def test_empty_input(self, processor):
        """Empty study list should produce valid but empty output."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="nothing",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_term="nothing"),
            fields_needed=["NCTId", "BriefTitle"],
            reasoning="Empty test",
        )
        result = processor.process([], plan)
        assert result["total_studies"] == 0
        assert result["data_points"] == []
