from pydantic import BaseModel, Field
from typing import Optional, Any


class Citation(BaseModel):
    nct_id: str
    url: str
    excerpt: str


class DataPoint(BaseModel):
    values: dict[str, Any] = Field(
        description="Field-value pairs, e.g. {'phase': 'PHASE3', 'trial_count': 42}"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source records supporting this data point",
    )


class NetworkNode(BaseModel):
    id: str
    type: str


class NetworkEdge(BaseModel):
    source: str
    target: str
    weight: int
    citations: list[Citation] = Field(default_factory=list)


class AxisEncoding(BaseModel):
    field: str
    type: str = Field(
        description="nominal, ordinal, quantitative, temporal"
    )
    title: Optional[str] = None


class Encoding(BaseModel):
    x: Optional[AxisEncoding] = None
    y: Optional[AxisEncoding] = None
    color: Optional[AxisEncoding] = None
    size: Optional[AxisEncoding] = None
    nodes: Optional[str] = None
    edges: Optional[str] = None


class VisualizationSpec(BaseModel):
    type: str = Field(
        description="bar_chart, time_series, scatter_plot, histogram, "
        "network_graph, grouped_bar_chart"
    )
    title: str
    encoding: Encoding
    data: list[DataPoint] = Field(default_factory=list)
    network_data: Optional[dict] = Field(
        None,
        description="For network_graph: {nodes: [...], edges: [...]}",
    )
    notes: Optional[str] = Field(
        None, description="Interpretive notes about the visualization"
    )
    query_interpretation: Optional[str] = Field(
        None, description="How the system interpreted the query"
    )


class ResponseMeta(BaseModel):
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    total_studies_analyzed: int
    source: str = "clinicaltrials.gov"
    api_version: str = "v2"
    timestamp: str
