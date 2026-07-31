"""Tests for citation extraction — verifying source traceability."""

import pytest
from cheiron.services.citation_extractor import CitationExtractor


def _make_study(nct_id: str, title: str = "", phase: str = "PHASE3") -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title or f"Study {nct_id}"},
            "statusModule": {
                "overallStatus": "COMPLETED",
                "startDateStruct": {"date": "2021-06-01"},
            },
            "designModule": {"phases": [phase]},
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "TestSponsor", "class": "INDUSTRY"}
            },
        }
    }


@pytest.fixture
def extractor():
    return CitationExtractor()


class TestStandardCitations:
    def test_citations_link_to_correct_ncts(self, extractor):
        raw_studies = [
            _make_study("NCT001", "Alpha Study"),
            _make_study("NCT002", "Beta Study"),
            _make_study("NCT003", "Gamma Study"),
        ]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {"phase": "PHASE3", "trial_count": 3, "_nct_ids": ["NCT001", "NCT002", "NCT003"]},
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)

        assert "PHASE3" in citations
        cites = citations["PHASE3"]
        assert len(cites) == 3
        assert {c["nct_id"] for c in cites} == {"NCT001", "NCT002", "NCT003"}

    def test_citations_have_urls(self, extractor):
        raw_studies = [_make_study("NCT12345")]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {"phase": "PHASE3", "trial_count": 1, "_nct_ids": ["NCT12345"]},
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)
        cite = citations["PHASE3"][0]
        assert cite["url"] == "https://clinicaltrials.gov/study/NCT12345"

    def test_excerpt_contains_real_fields(self, extractor):
        raw_studies = [_make_study("NCT001", "My Real Title", "PHASE2")]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {"phase": "PHASE2", "trial_count": 1, "_nct_ids": ["NCT001"]},
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)
        excerpt = citations["PHASE2"][0]["excerpt"]
        assert "My Real Title" in excerpt
        assert "PHASE2" in excerpt
        assert "TestSponsor" in excerpt

    def test_max_citations_per_point(self, extractor):
        raw_studies = [_make_study(f"NCT{i:03d}") for i in range(20)]
        aggregated = {
            "query_type": "distribution",
            "x_field": "phase",
            "data_points": [
                {
                    "phase": "PHASE3",
                    "trial_count": 20,
                    "_nct_ids": [f"NCT{i:03d}" for i in range(20)],
                },
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)
        # Capped at CITATIONS_PER_POINT (5)
        assert len(citations["PHASE3"]) == 5


class TestComparisonCitations:
    def test_comparison_keyed_by_entity(self, extractor):
        raw_studies = {
            "DrugA": [_make_study("NCT001")],
            "DrugB": [_make_study("NCT002")],
        }
        aggregated = {
            "query_type": "comparison",
            "x_field": "phase",
            "series": [
                {
                    "entity": "DrugA",
                    "data_points": [
                        {"phase": "PHASE3", "trial_count": 1, "_nct_ids": ["NCT001"]}
                    ],
                    "total": 1,
                },
                {
                    "entity": "DrugB",
                    "data_points": [
                        {"phase": "PHASE3", "trial_count": 1, "_nct_ids": ["NCT002"]}
                    ],
                    "total": 1,
                },
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)
        assert "DrugA:PHASE3" in citations
        assert "DrugB:PHASE3" in citations
        assert citations["DrugA:PHASE3"][0]["nct_id"] == "NCT001"
        assert citations["DrugB:PHASE3"][0]["nct_id"] == "NCT002"


class TestNetworkCitations:
    def test_network_keyed_by_edge(self, extractor):
        raw_studies = [_make_study("NCT001")]
        aggregated = {
            "query_type": "relationship_network",
            "edges": [
                {"source": "DrugA", "target": "Cancer", "weight": 1, "_nct_ids": ["NCT001"]}
            ],
        }
        citations = extractor.extract(raw_studies, aggregated)
        assert "DrugA->Cancer" in citations
        assert citations["DrugA->Cancer"][0]["nct_id"] == "NCT001"
