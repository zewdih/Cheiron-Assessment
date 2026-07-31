"""Edge case tests the developer might not have considered.

These test real-world scenarios that would come up in production or
during an on-site demo, covering query interpretation, data quality,
API quirks, and user behavior patterns.
"""

import pytest
from cheiron.services.data_processor import DataProcessor
from cheiron.services.citation_extractor import CitationExtractor
from cheiron.services.viz_builder import VizBuilder
from cheiron.models.query_plan import (
    QueryPlan, QueryType, VisualizationType, GroupByField,
    DateField, AggregationMethod, APIParams, ComparisonEntity,
)


def _make_study(nct_id, phase="PHASE3", status="COMPLETED", start_date="2020-05-01",
                sponsor="TestSponsor", sponsor_class="INDUSTRY",
                conditions=None, interventions=None, countries=None):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": f"Study {nct_id}"},
            "statusModule": {
                "overallStatus": status,
                "startDateStruct": {"date": start_date},
            },
            "designModule": {
                "phases": [phase] if phase else [],
                "studyType": "INTERVENTIONAL",
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor, "class": sponsor_class}
            },
            "conditionsModule": {"conditions": conditions or ["TestCondition"]},
            "armsInterventionsModule": {
                "interventions": interventions or [{"name": "TestDrug", "type": "DRUG"}]
            },
            "contactsLocationsModule": {
                "locations": [{"country": c} for c in (countries or ["United States"])]
            },
        }
    }


def _make_plan(**kwargs):
    defaults = {
        "query_type": QueryType.DISTRIBUTION,
        "suggested_viz": VisualizationType.BAR_CHART,
        "primary_entity": "test",
        "group_by": [GroupByField.PHASE],
        "aggregation": AggregationMethod.COUNT,
        "api_params": APIParams(query_intr="test"),
        "fields_needed": ["NCTId", "BriefTitle", "Phase"],
        "reasoning": "test",
    }
    defaults.update(kwargs)
    return QueryPlan(**defaults)


@pytest.fixture
def processor():
    return DataProcessor()


@pytest.fixture
def citation_extractor():
    return CitationExtractor()


@pytest.fixture
def viz_builder():
    return VizBuilder()


class TestUnknownFiltering:
    """Verify that Unknown/missing values are filtered from all chart types."""

    def test_unknown_interventions_filtered_from_distribution(self, processor):
        studies = [
            _make_study("NCT001", interventions=[{"name": "Unknown", "type": "DRUG"}]),
            _make_study("NCT002", interventions=[{"name": "Aspirin", "type": "DRUG"}]),
            _make_study("NCT003", interventions=[{"name": "Aspirin", "type": "DRUG"}]),
        ]
        plan = _make_plan(group_by=[GroupByField.INTERVENTION])
        result = processor.process(studies, plan)

        categories = [dp["intervention"] for dp in result["data_points"]]
        assert "Unknown" not in categories
        assert "Aspirin" in categories

    def test_unknown_countries_filtered_from_geographic(self, processor):
        studies = [
            _make_study("NCT001", countries=["Unknown"]),
            _make_study("NCT002", countries=["United States"]),
        ]
        plan = _make_plan(
            query_type=QueryType.GEOGRAPHIC,
            group_by=[GroupByField.COUNTRY],
        )
        result = processor.process(studies, plan)

        countries = [dp["country"] for dp in result["data_points"]]
        assert "Unknown" not in countries
        assert "United States" in countries

    def test_unknown_filtered_from_network_edges(self, processor):
        studies = [
            _make_study("NCT001",
                        conditions=["Cancer"],
                        interventions=[{"name": "Unknown", "type": "DRUG"}]),
            _make_study("NCT002",
                        conditions=["Cancer"],
                        interventions=[{"name": "Aspirin", "type": "DRUG"}]),
        ]
        plan = _make_plan(
            query_type=QueryType.RELATIONSHIP_NETWORK,
            suggested_viz=VisualizationType.NETWORK_GRAPH,
            group_by=[GroupByField.INTERVENTION, GroupByField.CONDITION],
        )
        result = processor.process(studies, plan)

        sources = [e["source"] for e in result["edges"]]
        assert "Unknown" not in sources

    def test_empty_string_filtered(self, processor):
        studies = [
            _make_study("NCT001", interventions=[{"name": "", "type": "DRUG"}]),
            _make_study("NCT002", interventions=[{"name": "Aspirin", "type": "DRUG"}]),
        ]
        plan = _make_plan(group_by=[GroupByField.INTERVENTION])
        result = processor.process(studies, plan)

        categories = [dp["intervention"] for dp in result["data_points"]]
        assert "" not in categories


class TestPhaseHandling:
    """Verify phase label cleaning and ordering."""

    def test_phases_have_clean_labels(self, processor):
        studies = [
            _make_study("NCT001", phase="PHASE1"),
            _make_study("NCT002", phase="PHASE2"),
            _make_study("NCT003", phase="PHASE3"),
            _make_study("NCT004", phase="EARLY_PHASE1"),
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        phases = [dp["phase"] for dp in result["data_points"]]
        assert "PHASE1" not in phases  # raw labels should not appear
        assert "Phase 1" in phases
        assert "Phase 2" in phases
        assert "Phase 3" in phases
        assert "Early Phase 1" in phases

    def test_phases_in_logical_order(self, processor):
        studies = [
            _make_study("NCT001", phase="PHASE3"),
            _make_study("NCT002", phase="PHASE1"),
            _make_study("NCT003", phase="EARLY_PHASE1"),
            _make_study("NCT004", phase="PHASE2"),
            _make_study("NCT005", phase="PHASE4"),
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        phases = [dp["phase"] for dp in result["data_points"]]
        assert phases == ["Early Phase 1", "Phase 1", "Phase 2", "Phase 3", "Phase 4"]

    def test_na_and_not_applicable_merged(self, processor):
        studies = [
            _make_study("NCT001", phase="NA"),
            _make_study("NCT002", phase="NOT_APPLICABLE"),
            _make_study("NCT003", phase=""),  # empty phase
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        phases = [dp["phase"] for dp in result["data_points"]]
        # NA and NOT_APPLICABLE should both map to "Not Applicable"
        assert phases.count("Not Applicable") == 1  # merged into one bar
        assert "NA" not in phases
        assert "NOT_APPLICABLE" not in phases

    def test_combo_phases_handled(self, processor):
        """Some trials span two phases (e.g., Phase 1/Phase 2)."""
        studies = [
            _make_study("NCT001", phase="PHASE1/PHASE2"),
            _make_study("NCT002", phase="PHASE2/PHASE3"),
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        phases = [dp["phase"] for dp in result["data_points"]]
        assert "Phase 1/2" in phases
        assert "Phase 2/3" in phases


class TestMultiValueFields:
    """Studies with multiple conditions, interventions, or countries."""

    def test_study_with_multiple_conditions_counted_in_each(self, processor):
        studies = [
            _make_study("NCT001", conditions=["Cancer", "Diabetes", "Heart Disease"]),
        ]
        plan = _make_plan(group_by=[GroupByField.CONDITION])
        result = processor.process(studies, plan)

        # The study should appear in all three condition counts
        conditions = {dp["condition"]: dp["trial_count"] for dp in result["data_points"]}
        assert conditions["Cancer"] == 1
        assert conditions["Diabetes"] == 1
        assert conditions["Heart Disease"] == 1

    def test_study_with_multiple_countries_counted_in_each(self, processor):
        studies = [
            _make_study("NCT001", countries=["United States", "Canada", "Germany"]),
        ]
        plan = _make_plan(
            query_type=QueryType.GEOGRAPHIC,
            group_by=[GroupByField.COUNTRY],
        )
        result = processor.process(studies, plan)

        countries = {dp["country"]: dp["trial_count"] for dp in result["data_points"]}
        assert countries["United States"] == 1
        assert countries["Canada"] == 1
        assert countries["Germany"] == 1

    def test_total_studies_reflects_input_not_expanded_counts(self, processor):
        """total_studies should be the number of studies, not the sum of multi-value expansions."""
        studies = [
            _make_study("NCT001", conditions=["Cancer", "Diabetes"]),
            _make_study("NCT002", conditions=["Cancer"]),
        ]
        plan = _make_plan(group_by=[GroupByField.CONDITION])
        result = processor.process(studies, plan)

        assert result["total_studies"] == 2  # 2 studies, not 3 condition-entries


class TestDateEdgeCases:
    """Date parsing edge cases from real API data."""

    def test_date_with_only_year_and_month(self, processor):
        """Some API dates are 'YYYY-MM' without a day."""
        studies = [
            _make_study("NCT001", start_date="2020-05"),
            _make_study("NCT002", start_date="2021-12"),
        ]
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        result = processor.process(studies, plan)

        years = [dp["year"] for dp in result["data_points"]]
        assert 2020 in years
        assert 2021 in years

    def test_date_with_full_format(self, processor):
        """Standard YYYY-MM-DD format."""
        studies = [
            _make_study("NCT001", start_date="2020-05-15"),
        ]
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        result = processor.process(studies, plan)
        assert result["data_points"][0]["year"] == 2020


class TestCitationEdgeCases:
    """Citation extraction edge cases."""

    def test_citation_for_study_with_minimal_fields(self, citation_extractor):
        """Studies with very few fields should still produce a citation."""
        raw_studies = [{
            "protocolSection": {
                "identificationModule": {"nctId": "NCT001", "briefTitle": "Minimal Study"},
            }
        }]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {"phase": "Phase 1", "trial_count": 1, "_nct_ids": ["NCT001"]},
            ],
        }
        citations = citation_extractor.extract(raw_studies, aggregated)
        assert len(citations["Phase 1"]) == 1
        assert citations["Phase 1"][0]["nct_id"] == "NCT001"
        assert "Minimal Study" in citations["Phase 1"][0]["excerpt"]

    def test_citation_url_always_valid(self, citation_extractor):
        """Every citation must have a properly formatted URL."""
        raw_studies = [_make_study(f"NCT{i:08d}") for i in range(10)]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {"phase": "Phase 3", "trial_count": 10,
                 "_nct_ids": [f"NCT{i:08d}" for i in range(10)]},
            ],
        }
        citations = citation_extractor.extract(raw_studies, aggregated)
        for cite in citations["Phase 3"]:
            assert cite["url"].startswith("https://clinicaltrials.gov/study/NCT")
            assert cite["nct_id"] in cite["url"]


class TestVizBuilderEdgeCases:
    """Visualization builder edge cases."""

    def test_single_data_point(self, viz_builder):
        """Chart with only one bar should still render."""
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [
                {"phase": "Phase 3", "trial_count": 42, "_nct_ids": ["NCT001"]},
            ],
            "total_studies": 42,
        }
        plan = _make_plan()
        spec = viz_builder.build(aggregated, plan, {}, title="Single Bar", notes="")
        assert len(spec.data) == 1
        assert spec.data[0].values["trial_count"] == 42

    def test_empty_data_produces_valid_spec(self, viz_builder):
        """Zero results should produce a valid (empty) visualization spec."""
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [],
            "total_studies": 0,
        }
        plan = _make_plan()
        spec = viz_builder.build(aggregated, plan, {}, title="No Data", notes="No results")
        assert len(spec.data) == 0
        assert spec.title == "No Data"

    def test_internal_fields_never_leak_to_output(self, viz_builder):
        """_nct_ids and other internal fields must never appear in the response."""
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "y_field": "trial_count",
            "data_points": [
                {"phase": "Phase 3", "trial_count": 10,
                 "_nct_ids": ["NCT001"], "_internal_debug": "secret"},
            ],
            "total_studies": 10,
        }
        plan = _make_plan()
        spec = viz_builder.build(aggregated, plan, {})

        for dp in spec.data:
            for key in dp.values:
                assert not key.startswith("_"), f"Internal field '{key}' leaked to output"


class TestMetaQueries:
    """Test system handling of meta/help questions."""

    def test_meta_query_type_recognized(self):
        """The META query type should exist and be valid."""
        assert QueryType.META == "meta"

    def test_meta_plan_skips_validation(self):
        """Meta plans shouldn't require API params."""
        from cheiron.services.query_analyzer import QueryAnalyzer
        from cheiron.models.request import QueryRequest

        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        plan = QueryPlan(
            query_type=QueryType.META,
            suggested_viz=VisualizationType.BAR_CHART,
            primary_entity="system_help",
            group_by=[GroupByField.PHASE],
            api_params=APIParams(),  # empty — no search needed
            fields_needed=["NCTId", "BriefTitle"],
            reasoning="Meta question",
        )
        req = QueryRequest(query="What kind of questions can I ask this system?")
        # Should NOT raise ValueError
        analyzer._validate_and_fix(plan, req)


class TestComparisonEdgeCases:
    """Comparison query edge cases."""

    def test_comparison_with_one_empty_entity(self, processor):
        """If one entity returns no results, comparison should still work."""
        raw_data = {
            "Drug A": [_make_study("NCT001", phase="PHASE3")],
            "Drug B": [],  # no results
        }
        plan = _make_plan(
            query_type=QueryType.COMPARISON,
            group_by=[GroupByField.PHASE],
            comparison_entities=[
                ComparisonEntity(label="Drug A", api_params=APIParams(query_intr="Drug A")),
                ComparisonEntity(label="Drug B", api_params=APIParams(query_intr="Drug B")),
            ],
        )
        result = processor.process(raw_data, plan)

        assert result["query_type"] == "comparison"
        assert len(result["series"]) == 2
        drug_a = next(s for s in result["series"] if s["entity"] == "Drug A")
        drug_b = next(s for s in result["series"] if s["entity"] == "Drug B")
        assert drug_a["total"] == 1
        assert drug_b["total"] == 0