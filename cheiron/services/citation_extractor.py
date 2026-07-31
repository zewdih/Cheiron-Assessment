from cheiron.models.query_plan import QueryPlan

CITATIONS_PER_POINT = 5


class CitationExtractor:
    """Extracts deep citations linking each data point back to source records.

    Entirely deterministic — builds excerpts from actual API response fields.
    The _nct_ids embedded during aggregation are the linkage mechanism.
    """

    def extract(
        self,
        raw_studies: dict | list[dict],
        aggregated: dict,
    ) -> dict[str, list[dict]]:
        study_lookup = self._build_lookup(raw_studies)
        query_type = aggregated.get("query_type", "")

        if query_type == "relationship_network":
            return self._cite_network(aggregated, study_lookup)
        elif query_type == "comparison":
            return self._cite_comparison(aggregated, study_lookup)
        else:
            return self._cite_standard(aggregated, study_lookup)

    def _build_lookup(self, raw_studies: dict | list[dict]) -> dict[str, dict]:
        if isinstance(raw_studies, dict):
            lookup = {}
            for entity_studies in raw_studies.values():
                for s in entity_studies:
                    nct = self._get_nct_id(s)
                    lookup[nct] = s
            return lookup
        else:
            return {self._get_nct_id(s): s for s in raw_studies}

    def _cite_standard(
        self, aggregated: dict, lookup: dict[str, dict]
    ) -> dict[str, list[dict]]:
        citations = {}
        x_field = aggregated.get("x_field", "label")
        for dp in aggregated.get("data_points", []):
            key = str(dp.get(x_field, list(dp.values())[0]))
            citations[key] = self._build_citations(
                dp.get("_nct_ids", []), lookup
            )
        return citations

    def _cite_comparison(
        self, aggregated: dict, lookup: dict[str, dict]
    ) -> dict[str, list[dict]]:
        citations = {}
        x_field = aggregated.get("x_field", "label")
        for series_item in aggregated.get("series", []):
            entity = series_item["entity"]
            for dp in series_item["data_points"]:
                x_val = dp.get(x_field, list(dp.values())[0])
                key = f"{entity}:{x_val}"
                citations[key] = self._build_citations(
                    dp.get("_nct_ids", []), lookup
                )
        return citations

    def _cite_network(
        self, aggregated: dict, lookup: dict[str, dict]
    ) -> dict[str, list[dict]]:
        citations = {}
        for edge in aggregated.get("edges", []):
            key = f"{edge['source']}->{edge['target']}"
            citations[key] = self._build_citations(
                edge.get("_nct_ids", []), lookup
            )
        return citations

    def _build_citations(
        self, nct_ids: list[str], lookup: dict[str, dict]
    ) -> list[dict]:
        result = []
        for nct_id in nct_ids[:CITATIONS_PER_POINT]:
            study = lookup.get(nct_id, {})
            result.append(
                {
                    "nct_id": nct_id,
                    "url": f"https://clinicaltrials.gov/study/{nct_id}",
                    "excerpt": self._build_excerpt(study),
                }
            )
        return result

    def _build_excerpt(self, study: dict) -> str:
        ps = study.get("protocolSection", {})
        parts = []

        title = ps.get("identificationModule", {}).get("briefTitle", "")
        if title:
            parts.append(title)

        status = ps.get("statusModule", {}).get("overallStatus", "")
        if status:
            parts.append(f"Status: {status}")

        phases = ps.get("designModule", {}).get("phases", [])
        if phases:
            parts.append(f"Phase: {', '.join(phases)}")

        start = (
            ps.get("statusModule", {}).get("startDateStruct", {}).get("date")
        )
        if start:
            parts.append(f"Start: {start}")

        sponsor = (
            ps.get("sponsorCollaboratorsModule", {})
            .get("leadSponsor", {})
            .get("name")
        )
        if sponsor:
            parts.append(f"Sponsor: {sponsor}")

        return " | ".join(parts) if parts else "No details available"

    def _get_nct_id(self, study: dict) -> str:
        return (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId", "UNKNOWN")
        )