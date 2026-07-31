import json
import logging
from openai import AsyncOpenAI
from cheiron.models.query_plan import QueryPlan, QueryType, DateField
from cheiron.models.request import QueryRequest
from cheiron.prompts.query_analyzer_system import QUERY_ANALYZER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _make_strict_schema(schema: dict, _is_property_map: bool = False) -> dict:
    """Recursively transform a Pydantic JSON schema to be compatible with
    OpenAI's strict structured output mode.

    Requirements:
    1. additionalProperties: false on all objects
    2. All properties must be in 'required'
    3. No 'default' values alongside $ref
    4. Remove 'title' metadata (not property keys)
    5. Remove 'examples' fields
    """
    if not isinstance(schema, dict):
        return schema

    # If this is a properties map ({prop_name: schema, ...}), just recurse into values
    if _is_property_map:
        for key, value in schema.items():
            if isinstance(value, dict):
                _make_strict_schema(value)
        return schema

    # Remove JSON Schema metadata that conflicts with strict mode
    schema.pop("title", None)
    schema.pop("examples", None)

    # If it has $ref, remove default (can't coexist in strict mode)
    if "$ref" in schema:
        schema.pop("default", None)
        schema.pop("description", None)
        return schema

    if schema.get("type") == "object" and "properties" in schema:
        schema["additionalProperties"] = False
        schema["required"] = list(schema["properties"].keys())

    # Recurse into all values, marking 'properties' dicts specially
    for key, value in list(schema.items()):
        if isinstance(value, dict):
            _make_strict_schema(value, _is_property_map=(key == "properties"))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _make_strict_schema(item)

    return schema


class QueryAnalyzer:
    """LLM Phase 1: Converts a natural-language question into a structured QueryPlan.

    The LLM receives ONLY the user's question and optional structured fields.
    It outputs ONLY a QueryPlan. It never sees any clinical trial data.
    """

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4.1"):
        self.client = client
        self.model = model

    async def analyze(self, request: QueryRequest) -> QueryPlan:
        user_message = self._build_user_message(request)

        response = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": QUERY_ANALYZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "query_plan",
                    "schema": _make_strict_schema(QueryPlan.model_json_schema()),
                    "strict": True,
                }
            },
        )

        plan = QueryPlan.model_validate_json(response.output_text)
        self._validate_and_fix(plan, request)
        logger.info(
            "Query plan: type=%s, viz=%s, entity=%s",
            plan.query_type,
            plan.suggested_viz,
            plan.primary_entity,
        )
        return plan

    def _build_user_message(self, request: QueryRequest) -> str:
        msg = f"Question: {request.query}"
        if request.drug_name:
            msg += f"\nDrug: {request.drug_name}"
        if request.condition:
            msg += f"\nCondition: {request.condition}"
        if request.trial_phase:
            msg += f"\nPhase: {request.trial_phase}"
        if request.sponsor:
            msg += f"\nSponsor: {request.sponsor}"
        if request.country:
            msg += f"\nCountry: {request.country}"
        if request.start_year:
            msg += f"\nStart year: {request.start_year}"
        if request.end_year:
            msg += f"\nEnd year: {request.end_year}"
        return msg

    def _validate_and_fix(self, plan: QueryPlan, request: QueryRequest) -> None:
        """Post-LLM validation to catch nonsensical plans and apply fixes."""
        # Meta queries don't need API params
        if plan.query_type == QueryType.META:
            return

        # Ensure at least one API query param is populated
        params = plan.api_params
        has_query = any(
            [params.query_term, params.query_cond, params.query_intr, params.query_locn]
        )
        has_comparison = bool(plan.comparison_entities)
        if not has_query and not has_comparison:
            raise ValueError(
                "Could not determine search parameters from your question. "
                "Try specifying a drug name, condition, or sponsor."
            )

        # Ensure NCTId and BriefTitle are in fields_needed (required for citations)
        if "NCTId" not in plan.fields_needed:
            plan.fields_needed.insert(0, "NCTId")
        if "BriefTitle" not in plan.fields_needed:
            plan.fields_needed.insert(1, "BriefTitle")

        # Ensure time queries have a date_field
        if plan.query_type == QueryType.TIME_TREND and not plan.date_field:
            plan.date_field = DateField.START_DATE

        # Override with user-provided structured fields when LLM missed them
        if request.drug_name and not params.query_intr:
            params.query_intr = request.drug_name
        if request.condition and not params.query_cond:
            params.query_cond = request.condition
        if request.country and not params.query_locn:
            params.query_locn = request.country
