import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Natural language question about clinical trials",
        examples=[
            "How has the number of trials for Pembrolizumab changed over time?"
        ],
    )
    drug_name: Optional[str] = Field(
        None, max_length=200, description="Specific drug or intervention name"
    )
    condition: Optional[str] = Field(
        None, max_length=200, description="Disease or condition name"
    )
    trial_phase: Optional[str] = Field(
        None,
        pattern=r"^(Phase [1-4]|PHASE[1-4]|NA|EARLY_PHASE1)$",
        description="Trial phase filter",
    )
    sponsor: Optional[str] = Field(
        None, max_length=200, description="Sponsor organization name"
    )
    country: Optional[str] = Field(
        None, max_length=100, description="Country name for location filtering"
    )
    start_year: Optional[int] = Field(
        None, ge=1990, le=2030, description="Start of year range filter"
    )
    end_year: Optional[int] = Field(
        None, ge=1990, le=2030, description="End of year range filter"
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", v)
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 10:
            raise ValueError("Query too short after sanitization")
        return v

    @field_validator("end_year")
    @classmethod
    def validate_year_range(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None and info.data.get("start_year") is not None:
            if v < info.data["start_year"]:
                raise ValueError("end_year must be >= start_year")
        return v
