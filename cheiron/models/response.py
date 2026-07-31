from pydantic import BaseModel
from cheiron.models.visualization import VisualizationSpec, ResponseMeta


class QueryResponse(BaseModel):
    visualization: VisualizationSpec
    meta: ResponseMeta
