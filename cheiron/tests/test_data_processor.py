"""Tests for the deterministic data processor — the core of the Data Firewall.

These tests verify that aggregation logic produces exact, correct counts
from raw API data. No LLM is involved at any point.
"""

import pytest
from cheiron.services.data_processor import DataProcessor
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


def _make_study(
    nct_id: str,
    phase: str = "PHASE3",
    status: str = "COMPLETED",
    start_date: str = "2020-05-01",
    sponsor: str = "TestSponsor",
    sponsor_class: str = "INDUSTRY",
    conditions: list[str] | None = None,
    interventions: list[dict] | None = None,
    countries: list[str] | None = None,
) -> dict:
    """Helper to build a study dict matching ClinicalTrials.gov API v2 shape."""
    study = {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": f"Study {nct_id}",
            },
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
            "conditionsModule": {
                "conditions": conditions or ["TestCondition"]
            },
            "armsInterventionsModule": {
                "interventions": interventions
                or [{"name": "TestDrug", "type": "DRUG"}]
            },
            "contactsLocationsModule": {
                "locations": [{"country": c} for c in (countries or ["United States"])]
            },
        }
    }
    return study


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
def processor():
    return DataProcessor()


class TestTimeTrend:
    def test_counts_by_year(self, processor):
        studies = [
            _make_study("NCT001", start_date="2020-03-15"),
            _make_study("NCT002", start_date="2020-07-01"),
            _make_study("NCT003", start_date="2021-01-10"),
            _make_study("NCT004", start_date="2022-06-20"),
        ]
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            suggested_viz=VisualizationType.TIME_SERIES,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        result = processor.process(studies, plan)

        assert result["query_type"] == "time_trend"
        assert result["total_studies"] == 4
        assert len(result["data_points"]) == 3  # 2020, 2021, 2022

        year_map = {dp["year"]: dp["trial_count"] for dp in result["data_points"]}
        assert year_map[2020] == 2
        assert year_map[2021] == 1
        assert year_map[2022] == 1

    def test_nct_ids_tracked(self, processor):
        studies = [
            _make_study("NCT001", start_date="2020-01-01"),
            _make_study("NCT002", start_date="2020-06-01"),
        ]
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        result = processor.process(studies, plan)

        dp_2020 = result["data_points"][0]
        assert set(dp_2020["_nct_ids"]) == {"NCT001", "NCT002"}

    def test_missing_date_skipped(self, processor):
        studies = [
            _make_study("NCT001", start_date="2020-01-01"),
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT002", "briefTitle": "No date"},
                    "statusModule": {},
                    "designModule": {},
                }
            },
        ]
        plan = _make_plan(
            query_type=QueryType.TIME_TREND,
            group_by=[GroupByField.YEAR],
            date_field=DateField.START_DATE,
        )
        result = processor.process(studies, plan)
        assert len(result["data_points"]) == 1
        assert result["total_studies"] == 2


class TestDistribution:
    def test_phase_distribution(self, processor):
        studies = [
            _make_study("NCT001", phase="PHASE1"),
            _make_study("NCT002", phase="PHASE2"),
            _make_study("NCT003", phase="PHASE3"),
            _make_study("NCT004", phase="PHASE3"),
            _make_study("NCT005", phase="PHASE3"),
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        assert result["query_type"] == "distribution"
        assert result["total_studies"] == 5

        phase_map = {dp["phase"]: dp["trial_count"] for dp in result["data_points"]}
        assert phase_map["Phase 3"] == 3
        assert phase_map["Phase 2"] == 1
        assert phase_map["Phase 1"] == 1

    def test_sorted_in_logical_phase_order(self, processor):
        studies = [_make_study(f"NCT{i:03d}", phase="PHASE3") for i in range(10)]
        studies += [_make_study(f"NCT{i:03d}", phase="PHASE1") for i in range(10, 13)]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        # Phases sorted logically: Phase 1 before Phase 3
        assert result["data_points"][0]["phase"] == "Phase 1"
        assert result["data_points"][1]["phase"] == "Phase 3"


class TestComparison:
    def test_two_entity_comparison(self, processor):
        drug_a_studies = [
            _make_study("NCT001", phase="PHASE1"),
            _make_study("NCT002", phase="PHASE3"),
        ]
        drug_b_studies = [
            _make_study("NCT003", phase="PHASE2"),
            _make_study("NCT004", phase="PHASE2"),
            _make_study("NCT005", phase="PHASE3"),
        ]
        raw_data = {"Drug A": drug_a_studies, "Drug B": drug_b_studies}
        plan = _make_plan(
            query_type=QueryType.COMPARISON,
            suggested_viz=VisualizationType.GROUPED_BAR_CHART,
            group_by=[GroupByField.PHASE],
            comparison_entities=[
                ComparisonEntity(label="Drug A", api_params=APIParams(query_intr="Drug A")),
                ComparisonEntity(label="Drug B", api_params=APIParams(query_intr="Drug B")),
            ],
        )
        result = processor.process(raw_data, plan)

        assert result["query_type"] == "comparison"
        assert result["total_studies"] == 5
        assert len(result["series"]) == 2

        drug_a = next(s for s in result["series"] if s["entity"] == "Drug A")
        drug_b = next(s for s in result["series"] if s["entity"] == "Drug B")
        assert drug_a["total"] == 2
        assert drug_b["total"] == 3


class TestGeographic:
    def test_country_grouping(self, processor):
        studies = [
            _make_study("NCT001", countries=["United States"]),
            _make_study("NCT002", countries=["United States", "Canada"]),
            _make_study("NCT003", countries=["Germany"]),
        ]
        plan = _make_plan(
            query_type=QueryType.GEOGRAPHIC,
            group_by=[GroupByField.COUNTRY],
        )
        result = processor.process(studies, plan)

        assert result["query_type"] == "geographic"
        country_map = {dp["country"]: dp["trial_count"] for dp in result["data_points"]}
        assert country_map["United States"] == 2
        assert country_map["Canada"] == 1
        assert country_map["Germany"] == 1


class TestNetwork:
    def test_drug_condition_network(self, processor):
        studies = [
            _make_study(
                "NCT001",
                conditions=["Lung Cancer"],
                interventions=[{"name": "DrugA", "type": "DRUG"}],
            ),
            _make_study(
                "NCT002",
                conditions=["Lung Cancer"],
                interventions=[
                    {"name": "DrugA", "type": "DRUG"},
                    {"name": "DrugB", "type": "DRUG"},
                ],
            ),
            _make_study(
                "NCT003",
                conditions=["Breast Cancer"],
                interventions=[{"name": "DrugB", "type": "DRUG"}],
            ),
        ]
        plan = _make_plan(
            query_type=QueryType.RELATIONSHIP_NETWORK,
            suggested_viz=VisualizationType.NETWORK_GRAPH,
            group_by=[GroupByField.INTERVENTION, GroupByField.CONDITION],
        )
        result = processor.process(studies, plan)

        assert result["query_type"] == "relationship_network"
        assert len(result["nodes"]) > 0
        assert len(result["edges"]) > 0

        # DrugA -> Lung Cancer should have weight 2
        edge = next(
            (e for e in result["edges"] if e["source"] == "DrugA" and e["target"] == "Lung Cancer"),
            None,
        )
        assert edge is not None
        assert edge["weight"] == 2


class TestAntiHallucination:
    """Verify that aggregated counts exactly match manual counting of input data."""

    def test_counts_match_input_exactly(self, processor):
        studies = [
            _make_study(f"NCT{i:03d}", phase="PHASE1") for i in range(7)
        ] + [
            _make_study(f"NCT{i:03d}", phase="PHASE2") for i in range(7, 15)
        ] + [
            _make_study(f"NCT{i:03d}", phase="PHASE3") for i in range(15, 20)
        ]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        total_from_data_points = sum(dp["trial_count"] for dp in result["data_points"])
        assert total_from_data_points == 20
        assert result["total_studies"] == 20

        phase_map = {dp["phase"]: dp["trial_count"] for dp in result["data_points"]}
        assert phase_map["Phase 1"] == 7
        assert phase_map["Phase 2"] == 8
        assert phase_map["Phase 3"] == 5

    def test_all_nct_ids_traceable(self, processor):
        """Every NCT ID in aggregated output must exist in the input."""
        input_ncts = {f"NCT{i:03d}" for i in range(10)}
        studies = [_make_study(nct, phase="PHASE1") for nct in input_ncts]
        plan = _make_plan(group_by=[GroupByField.PHASE])
        result = processor.process(studies, plan)

        output_ncts = set()
        for dp in result["data_points"]:
            output_ncts.update(dp.get("_nct_ids", []))

        assert output_ncts == input_ncts
