from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class QueryType(str, Enum):
    TIME_TREND = "time_trend"
    DISTRIBUTION = "distribution"
    COMPARISON = "comparison"
    GEOGRAPHIC = "geographic"
    RELATIONSHIP_NETWORK = "relationship_network"
    META = "meta"  # Questions about the system itself, not clinical trials data


class VisualizationType(str, Enum):
    BAR_CHART = "bar_chart"
    TIME_SERIES = "time_series"
    SCATTER_PLOT = "scatter_plot"
    HISTOGRAM = "histogram"
    NETWORK_GRAPH = "network_graph"
    GROUPED_BAR_CHART = "grouped_bar_chart"


class AggregationMethod(str, Enum):
    COUNT = "count"
    SUM_ENROLLMENT = "sum_enrollment"
    AVERAGE_ENROLLMENT = "average_enrollment"
    COUNT_DISTINCT = "count_distinct"


class GroupByField(str, Enum):
    YEAR = "year"
    PHASE = "phase"
    STATUS = "status"
    SPONSOR = "lead_sponsor"
    SPONSOR_CLASS = "sponsor_class"
    CONDITION = "condition"
    INTERVENTION = "intervention"
    INTERVENTION_TYPE = "intervention_type"
    COUNTRY = "country"
    STUDY_TYPE = "study_type"


class DateField(str, Enum):
    START_DATE = "start_date"
    COMPLETION_DATE = "completion_date"
    FIRST_POSTED = "first_posted"


class APIParams(BaseModel):
    query_term: Optional[str] = Field(
        None, description="General search term for query.term"
    )
    query_cond: Optional[str] = Field(
        None, description="Condition search for query.cond"
    )
    query_intr: Optional[str] = Field(
        None, description="Intervention search for query.intr"
    )
    query_locn: Optional[str] = Field(
        None, description="Location search for query.locn"
    )
    filter_status: Optional[list[str]] = Field(
        None,
        description="Status filter values: RECRUITING, COMPLETED, etc.",
    )
    filter_phase: Optional[list[str]] = Field(None)
    filter_advanced: Optional[str] = Field(
        None,
        description="Advanced filter, e.g. AREA[StartDate]RANGE[01/01/2015,12/31/2023]",
    )


class ComparisonEntity(BaseModel):
    label: str
    api_params: APIParams


class QueryPlan(BaseModel):
    query_type: QueryType
    suggested_viz: VisualizationType
    primary_entity: str = Field(
        description="The main drug, condition, or topic being queried"
    )
    group_by: list[GroupByField] = Field(
        description="Fields to group/aggregate by"
    )
    aggregation: AggregationMethod = Field(default=AggregationMethod.COUNT)
    date_field: Optional[DateField] = Field(
        None, description="Which date field to use for time-based queries"
    )
    api_params: APIParams = Field(
        description="Parameters to pass to ClinicalTrials.gov API"
    )
    comparison_entities: Optional[list[ComparisonEntity]] = Field(
        None,
        description="For comparison queries: multiple entities to query separately",
    )
    fields_needed: list[str] = Field(
        description="ClinicalTrials.gov API field names to request",
        examples=[["NCTId", "BriefTitle", "Phase", "StartDate", "LeadSponsorName"]],
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum studies to retrieve",
    )
    reasoning: str = Field(
        description="Brief explanation of interpretation for debugging"
    )
