"""Tests for input validation and sanitization."""

import pytest
from pydantic import ValidationError
from cheiron.models.request import QueryRequest


class TestQueryValidation:
    def test_valid_request(self):
        req = QueryRequest(query="How has the number of trials for Pembrolizumab changed over time?")
        assert req.query.startswith("How")

    def test_query_too_short(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="Hi")

    def test_query_sanitized(self):
        req = QueryRequest(query="How   has the   number\x00 of trials changed?")
        assert "\x00" not in req.query
        assert "  " not in req.query

    def test_year_range_validation(self):
        with pytest.raises(ValidationError):
            QueryRequest(
                query="Show trials from 2020 to 2015",
                start_year=2020,
                end_year=2015,
            )

    def test_valid_year_range(self):
        req = QueryRequest(
            query="Show trials from 2015 to 2020",
            start_year=2015,
            end_year=2020,
        )
        assert req.start_year == 2015
        assert req.end_year == 2020

    def test_phase_validation(self):
        with pytest.raises(ValidationError):
            QueryRequest(
                query="Show phase 99 trials for testing",
                trial_phase="Phase 99",
            )

    def test_valid_phase(self):
        req = QueryRequest(
            query="Show phase 3 trials for testing",
            trial_phase="Phase 3",
        )
        assert req.trial_phase == "Phase 3"

    def test_optional_fields_default_none(self):
        req = QueryRequest(query="How many breast cancer trials are recruiting?")
        assert req.drug_name is None
        assert req.condition is None
        assert req.start_year is None
