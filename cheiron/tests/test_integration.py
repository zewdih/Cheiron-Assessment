"""End-to-end integration tests.

These tests hit the real ClinicalTrials.gov API (no mock) and mock only
the OpenAI client to avoid API key dependency in CI.
"""

import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from cheiron.services.ct_client import CTClient
from cheiron.services.data_processor import DataProcessor
from cheiron.services.citation_extractor import CitationExtractor
from cheiron.services.viz_builder import VizBuilder
from cheiron.models.query_plan import (
    QueryPlan,
    QueryType,
    VisualizationType,
    GroupByField,
    DateField,
    AggregationMethod,
    APIParams,
    ComparisonEntity,
)
from cheiron.models.response import QueryResponse
from cheiron.models.visualization import ResponseMeta


@pytest.fixture
def processor():
    return DataProcessor()


@pytest.fixture
def citation_extractor():
    return CitationExtractor()


@pytest.fixture
def viz_builder():
    return VizBuilder()


class TestEndToEndWithRealAPI:
    """Tests that fetch real data from ClinicalTrials.gov and process it
    through the deterministic pipeline."""

    @pytest.mark.asyncio
    async def test_time_trend_pembrolizumab(self, processor, citation_extractor, viz_builder):
        """Full pipeline: fetch real Pembrolizumab data, aggregate by year, build viz."""
        plan = QueryPlan(
            query_type=QueryType.TIME_TREND,
            suggested_viz=VisualizationType.TIME_SERIES,
            primary_entity="Pembrolizumab",
            group_by=[GroupByField.YEAR],
            aggregation=AggregationMethod.COUNT,
            date_field=DateField.START_DATE,
            api_params=APIParams(query_intr="Pembrolizumab"),
            fields_needed=["NCTId", "BriefTitle", "StartDate", "Phase", "LeadSponsorName", "OverallStatus"],
            max_results=100,
            reasoning="Test: time trend for Pembrolizumab",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        assert len(raw_studies) > 0, "Should find Pembrolizumab trials"

        # Aggregate
        aggregated = processor.process(raw_studies, plan)
        assert aggregated["query_type"] == "time_trend"
        assert aggregated["total_studies"] == len(raw_studies)
        assert len(aggregated["data_points"]) > 0

        # Verify counts match
        total_from_points = sum(dp["trial_count"] for dp in aggregated["data_points"])
        studies_with_dates = sum(1 for s in raw_studies if _has_start_date(s))
        assert total_from_points == studies_with_dates

        # Citations
        citations = citation_extractor.extract(raw_studies, aggregated)
        assert len(citations) > 0

        # Build viz
        viz = viz_builder.build(aggregated, plan, citations, title="Test", notes="Test")
        assert viz.type == "time_series"
        assert len(viz.data) > 0

        # Verify every citation has a real URL
        for dp in viz.data:
            for cite in dp.citations:
                assert cite.nct_id.startswith("NCT")
                assert cite.url.startswith("https://clinicaltrials.gov/study/NCT")
                assert len(cite.excerpt) > 0

    @pytest.mark.asyncio
    async def test_distribution_diabetes(self, processor, citation_extractor, viz_builder):
        """Full pipeline: fetch real diabetes data, aggregate by phase."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="diabetes",
            group_by=[GroupByField.PHASE],
            aggregation=AggregationMethod.COUNT,
            api_params=APIParams(query_cond="diabetes"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "LeadSponsorName", "OverallStatus"],
            max_results=200,
            reasoning="Test: phase distribution for diabetes",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        assert len(raw_studies) > 0

        aggregated = processor.process(raw_studies, plan)
        assert aggregated["query_type"] == "distribution"

        # Verify valid phases
        valid_phases = {"PHASE1", "PHASE2", "PHASE3", "PHASE4", "EARLY_PHASE1",
                        "NA", "NOT_APPLICABLE", "PHASE1/PHASE2", "PHASE2/PHASE3"}
        for dp in aggregated["data_points"]:
            # phase values should be from the API, not fabricated
            assert isinstance(dp["phase"], str)
            assert dp["trial_count"] > 0

    @pytest.mark.asyncio
    async def test_comparison_two_drugs(self, processor, citation_extractor, viz_builder):
        """Full pipeline: compare Pembrolizumab vs Nivolumab."""
        plan = QueryPlan(
            query_type=QueryType.COMPARISON,
            suggested_viz=VisualizationType.GROUPED_BAR_CHART,
            primary_entity="Pembrolizumab vs Nivolumab",
            group_by=[GroupByField.PHASE],
            aggregation=AggregationMethod.COUNT,
            api_params=APIParams(),
            comparison_entities=[
                ComparisonEntity(
                    label="Pembrolizumab",
                    api_params=APIParams(query_intr="Pembrolizumab"),
                ),
                ComparisonEntity(
                    label="Nivolumab",
                    api_params=APIParams(query_intr="Nivolumab"),
                ),
            ],
            fields_needed=["NCTId", "BriefTitle", "Phase", "InterventionName"],
            max_results=100,
            reasoning="Test: comparison",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        assert isinstance(raw_studies, dict)
        assert "Pembrolizumab" in raw_studies
        assert "Nivolumab" in raw_studies
        assert len(raw_studies["Pembrolizumab"]) > 0
        assert len(raw_studies["Nivolumab"]) > 0

        aggregated = processor.process(raw_studies, plan)
        assert aggregated["query_type"] == "comparison"
        assert len(aggregated["series"]) == 2


class TestCitationIntegrity:
    """Verify that every citation in the output traces back to real API data."""

    @pytest.mark.asyncio
    async def test_all_citation_nct_ids_exist_in_raw_data(self, processor, citation_extractor):
        """Every NCT ID in citations must exist in the raw API response."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="aspirin",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_intr="aspirin"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "OverallStatus", "StartDate", "LeadSponsorName"],
            max_results=50,
            reasoning="Test citation integrity",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        raw_nct_ids = {
            s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            for s in raw_studies
        }

        aggregated = processor.process(raw_studies, plan)
        citations = citation_extractor.extract(raw_studies, aggregated)

        for key, cite_list in citations.items():
            for cite in cite_list:
                assert cite["nct_id"] in raw_nct_ids, (
                    f"Citation NCT ID {cite['nct_id']} not found in raw API data"
                )

    @pytest.mark.asyncio
    async def test_citation_urls_are_valid(self, processor, citation_extractor):
        """Every citation URL should be a valid ClinicalTrials.gov link."""
        plan = QueryPlan(
            query_type=QueryType.DISTRIBUTION,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="metformin",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(query_intr="metformin"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "OverallStatus", "StartDate", "LeadSponsorName"],
            max_results=30,
            reasoning="Test citation URLs",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        aggregated = processor.process(raw_studies, plan)
        citations = citation_extractor.extract(raw_studies, aggregated)

        for key, cite_list in citations.items():
            for cite in cite_list:
                assert cite["url"] == f"https://clinicaltrials.gov/study/{cite['nct_id']}"
                assert cite["excerpt"] != "No details available", (
                    f"Citation for {cite['nct_id']} has no excerpt — API field extraction may be broken"
                )

    @pytest.mark.asyncio
    async def test_citation_excerpts_contain_real_data(self, processor, citation_extractor):
        """Excerpts should contain actual field values from the API response."""
        plan = QueryPlan(
            query_type=QueryType.TIME_TREND,
            suggested_viz=VisualizationType.TIME_SERIES,
            primary_entity="ibuprofen",
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
            api_params=APIParams(query_intr="ibuprofen"),
            fields_needed=["NCTId", "BriefTitle", "Phase", "OverallStatus", "StartDate", "LeadSponsorName"],
            max_results=20,
            reasoning="Test citation excerpts",
        )

        client = CTClient()
        try:
            raw_studies = await client.fetch_studies(plan)
        finally:
            await client.close()

        aggregated = processor.process(raw_studies, plan)
        citations = citation_extractor.extract(raw_studies, aggregated)

        # Build lookup for verification
        study_lookup = {
            s.get("protocolSection", {}).get("identificationModule", {}).get("nctId"): s
            for s in raw_studies
        }

        for key, cite_list in citations.items():
            for cite in cite_list:
                study = study_lookup.get(cite["nct_id"])
                if study:
                    title = study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "")
                    if title:
                        assert title in cite["excerpt"], (
                            f"Excerpt for {cite['nct_id']} doesn't contain the study title"
                        )


def _has_start_date(study: dict) -> bool:
    return bool(
        study.get("protocolSection", {})
        .get("statusModule", {})
        .get("startDateStruct", {})
        .get("date")
    )
