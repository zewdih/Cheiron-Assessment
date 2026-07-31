import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cheiron.models.query_plan import QueryPlan, APIParams

logger = logging.getLogger(__name__)

CT_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


class CTClientError(Exception):
    """Raised when ClinicalTrials.gov API returns an error after retries."""
    pass


class CTClient:
    """ClinicalTrials.gov API v2 client.

    Handles pagination, field selection, retry with exponential backoff.
    This is entirely deterministic — no LLM involvement.
    """

    def __init__(self, base_url: str = CT_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.client.aclose()

    async def fetch_studies(self, plan: QueryPlan) -> dict | list[dict]:
        """Execute the query plan against ClinicalTrials.gov.

        Returns:
            list[dict] for standard queries
            dict[str, list[dict]] for comparison queries (keyed by entity label)
        """
        if plan.comparison_entities:
            all_results = {}
            for entity in plan.comparison_entities:
                merged_params = self._merge_params(plan.api_params, entity.api_params)
                studies = await self._fetch_all_pages(
                    merged_params, plan.fields_needed, plan.max_results
                )
                all_results[entity.label] = studies
                logger.info(
                    "Fetched %d studies for comparison entity '%s'",
                    len(studies),
                    entity.label,
                )
            return all_results
        else:
            studies = await self._fetch_all_pages(
                plan.api_params, plan.fields_needed, plan.max_results
            )
            logger.info("Fetched %d studies", len(studies))
            return studies

    def _merge_params(self, base: APIParams, entity: APIParams) -> APIParams:
        """Merge base params with entity-specific params. Entity overrides base."""
        return APIParams(
            query_term=entity.query_term or base.query_term,
            query_cond=entity.query_cond or base.query_cond,
            query_intr=entity.query_intr or base.query_intr,
            query_locn=entity.query_locn or base.query_locn,
            filter_status=entity.filter_status or base.filter_status,
            filter_phase=entity.filter_phase or base.filter_phase,
            filter_advanced=entity.filter_advanced or base.filter_advanced,
        )

    async def _fetch_all_pages(
        self, params: APIParams, fields: list[str], max_results: int
    ) -> list[dict]:
        studies = []
        next_token = None
        page_size = min(max_results, 1000)

        while len(studies) < max_results:
            response_data = await self._fetch_page(
                params, fields, page_size, next_token
            )
            batch = response_data.get("studies", [])
            studies.extend(batch)
            next_token = response_data.get("nextPageToken")
            if not next_token or not batch:
                break

        return studies[:max_results]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _fetch_page(
        self,
        params: APIParams,
        fields: list[str],
        page_size: int,
        page_token: str | None,
    ) -> dict:
        query: dict[str, str] = {}
        if params.query_term:
            query["query.term"] = params.query_term
        if params.query_cond:
            query["query.cond"] = params.query_cond
        if params.query_intr:
            query["query.intr"] = params.query_intr
        if params.query_locn:
            query["query.locn"] = params.query_locn
        if params.filter_status:
            query["filter.overallStatus"] = ",".join(params.filter_status)
        if params.filter_phase:
            # ClinicalTrials.gov doesn't have a filter.phase param — use filter.advanced
            phase_filter = " OR ".join(
                f"AREA[Phase]{p}" for p in params.filter_phase
            )
            # Merge with existing filter_advanced if present
            if "filter.advanced" in query:
                query["filter.advanced"] += f" AND ({phase_filter})"
            else:
                query["filter.advanced"] = phase_filter
        if params.filter_advanced:
            query["filter.advanced"] = params.filter_advanced

        query["fields"] = ",".join(fields)
        query["pageSize"] = str(page_size)
        query["countTotal"] = "true"
        if page_token:
            query["pageToken"] = page_token

        logger.debug("CT API request: %s", query)
        response = await self.client.get(self.base_url, params=query)
        response.raise_for_status()
        data = response.json()
        logger.debug(
            "CT API response: %d studies, total=%s",
            len(data.get("studies", [])),
            data.get("totalCount", "N/A"),
        )
        return data
