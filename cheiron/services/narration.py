import logging
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from cheiron.models.query_plan import QueryPlan
from cheiron.prompts.narration_system import NARRATION_SYSTEM_PROMPT
from cheiron.services.query_analyzer import _make_strict_schema

logger = logging.getLogger(__name__)


class NarrationOutput(BaseModel):
    title: str = Field(max_length=100)
    notes: str = Field(max_length=1000)


class NarrationService:
    """LLM Phase 2: Generates a human-readable title and interpretive notes.

    This is the minimal, tightly constrained second LLM call. It receives ONLY
    pre-aggregated counts — never raw study data or _nct_ids. Failure here is
    non-fatal; the system falls back to a generated title.
    """

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4.1-mini"):
        self.client = client
        self.model = model

    async def narrate(
        self, question: str, plan: QueryPlan, aggregated: dict
    ) -> NarrationOutput:
        clean_summary = self._summarize_for_llm(aggregated)

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": NARRATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n\n"
                            f"Query type: {plan.query_type.value}\n"
                            f"Visualization type: {plan.suggested_viz.value}\n"
                            f"Entity: {plan.primary_entity}\n\n"
                            f"Aggregated data summary:\n{clean_summary}"
                        ),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "narration",
                        "schema": _make_strict_schema(NarrationOutput.model_json_schema()),
                        "strict": True,
                    }
                },
            )
            return NarrationOutput.model_validate_json(response.output_text)
        except Exception as e:
            logger.warning("Narration LLM failed, using fallback: %s", e)
            return self._fallback(plan, aggregated)

    def _fallback(self, plan: QueryPlan, aggregated: dict) -> NarrationOutput:
        group_label = plan.group_by[0].value if plan.group_by else "category"
        total = aggregated.get("total_studies", 0)
        return NarrationOutput(
            title=f"{plan.primary_entity} Trials by {group_label.replace('_', ' ').title()}",
            notes=f"Analysis of {total} clinical trials from ClinicalTrials.gov.",
        )

    def _summarize_for_llm(self, aggregated: dict) -> str:
        """Create a compact text summary. Strips _nct_ids to avoid leaking
        raw identifiers to the LLM."""
        lines = [f"Total studies: {aggregated.get('total_studies', 'N/A')}"]

        if "data_points" in aggregated:
            for dp in aggregated["data_points"][:30]:
                clean = {k: v for k, v in dp.items() if not k.startswith("_")}
                lines.append(str(clean))
        elif "series" in aggregated:
            for s in aggregated["series"]:
                lines.append(f"\n{s['entity']} (total: {s['total']}):")
                for dp in s["data_points"][:15]:
                    clean = {k: v for k, v in dp.items() if not k.startswith("_")}
                    lines.append(f"  {clean}")
        elif "nodes" in aggregated:
            lines.append(f"Nodes: {len(aggregated['nodes'])}")
            lines.append(f"Edges: {len(aggregated['edges'])}")
            for e in aggregated["edges"][:10]:
                lines.append(
                    f"  {e['source']} -> {e['target']} (weight: {e['weight']})"
                )

        return "\n".join(lines)