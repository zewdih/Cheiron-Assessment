from collections import Counter, defaultdict
from cheiron.models.query_plan import (
    QueryPlan,
    QueryType,
    GroupByField,
    DateField,
)

# Clean display labels for phases and their sort order
PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE1/PHASE2": "Phase 1/2",
    "PHASE2": "Phase 2",
    "PHASE2/PHASE3": "Phase 2/3",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "Not Applicable",
    "NOT_APPLICABLE": "Not Applicable",
}

PHASE_ORDER = [
    "Early Phase 1", "Phase 1", "Phase 1/2", "Phase 2",
    "Phase 2/3", "Phase 3", "Phase 4", "Not Applicable",
]

# Values to filter out from visualizations — missing/placeholder data
NOISE_VALUES = {"Unknown", "UNKNOWN", "unknown", ""}


class DataProcessor:
    """Deterministic aggregation engine.

    This is the core of the 'Data Firewall' pattern. All data transformation
    happens here via pure Python — no LLM is ever called. Every count, grouping,
    and data point is produced by Counter/defaultdict operations on raw API data.
    """

    def process(self, raw_data: dict | list[dict], plan: QueryPlan) -> dict:
        if plan.comparison_entities and isinstance(raw_data, dict):
            return self._process_comparison(raw_data, plan)

        studies = raw_data
        match plan.query_type:
            case QueryType.TIME_TREND:
                return self._process_time_trend(studies, plan)
            case QueryType.DISTRIBUTION:
                return self._process_distribution(studies, plan)
            case QueryType.GEOGRAPHIC:
                return self._process_geographic(studies, plan)
            case QueryType.RELATIONSHIP_NETWORK:
                return self._process_network(studies, plan)
            case _:
                return self._process_distribution(studies, plan)

    # ── Field extraction helpers ──

    def _extract_field(self, study: dict, field: GroupByField) -> list[str]:
        """Extract field values from a study. Returns a list because some
        fields are multi-valued (conditions, interventions, countries)."""
        ps = study.get("protocolSection", {})
        match field:
            case GroupByField.YEAR:
                return []  # handled via _extract_date_year
            case GroupByField.PHASE:
                raw_phases = ps.get("designModule", {}).get("phases", [])
                if not raw_phases:
                    return ["Not Applicable"]
                return [PHASE_LABELS.get(p, p) for p in raw_phases]
            case GroupByField.STATUS:
                status = ps.get("statusModule", {}).get("overallStatus")
                return [status] if status else ["UNKNOWN"]
            case GroupByField.SPONSOR:
                name = (
                    ps.get("sponsorCollaboratorsModule", {})
                    .get("leadSponsor", {})
                    .get("name")
                )
                return [name] if name else ["Unknown"]
            case GroupByField.SPONSOR_CLASS:
                cls = (
                    ps.get("sponsorCollaboratorsModule", {})
                    .get("leadSponsor", {})
                    .get("class")
                )
                return [cls] if cls else ["UNKNOWN"]
            case GroupByField.CONDITION:
                return ps.get("conditionsModule", {}).get("conditions", ["Unknown"])
            case GroupByField.INTERVENTION:
                interventions = ps.get("armsInterventionsModule", {}).get(
                    "interventions", []
                )
                return [i.get("name", "Unknown") for i in interventions] or ["Unknown"]
            case GroupByField.INTERVENTION_TYPE:
                interventions = ps.get("armsInterventionsModule", {}).get(
                    "interventions", []
                )
                return [i.get("type", "Unknown") for i in interventions] or ["Unknown"]
            case GroupByField.COUNTRY:
                locations = ps.get("contactsLocationsModule", {}).get("locations", [])
                countries = list({loc.get("country", "Unknown") for loc in locations})
                return countries if countries else ["Unknown"]
            case GroupByField.STUDY_TYPE:
                st = ps.get("designModule", {}).get("studyType")
                return [st] if st else ["UNKNOWN"]
            case _:
                return ["Unknown"]

    def _extract_date_year(self, study: dict, date_field: DateField) -> int | None:
        ps = study.get("protocolSection", {})
        date_str = None
        match date_field:
            case DateField.START_DATE:
                date_str = (
                    ps.get("statusModule", {})
                    .get("startDateStruct", {})
                    .get("date")
                )
            case DateField.COMPLETION_DATE:
                date_str = (
                    ps.get("statusModule", {})
                    .get("completionDateStruct", {})
                    .get("date")
                )
            case DateField.FIRST_POSTED:
                date_str = (
                    ps.get("statusModule", {})
                    .get("studyFirstPostDateStruct", {})
                    .get("date")
                )
        if date_str and len(date_str) >= 4:
            try:
                return int(date_str[:4])
            except ValueError:
                return None
        return None

    def _get_nct_id(self, study: dict) -> str:
        return (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId", "UNKNOWN")
        )

    def _get_brief_title(self, study: dict) -> str:
        return (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("briefTitle", "")
        )

    # ── Query type processors ──

    def _process_time_trend(self, studies: list[dict], plan: QueryPlan) -> dict:
        date_field = plan.date_field or DateField.START_DATE
        year_counts: Counter = Counter()
        year_ncts: dict[int, list[str]] = defaultdict(list)

        for study in studies:
            year = self._extract_date_year(study, date_field)
            if year is not None:
                year_counts[year] += 1
                year_ncts[year].append(self._get_nct_id(study))

        sorted_years = sorted(year_counts.keys())
        data_points = [
            {
                "year": y,
                "trial_count": year_counts[y],
                "_nct_ids": year_ncts[y],
            }
            for y in sorted_years
        ]

        return {
            "data_points": data_points,
            "total_studies": len(studies),
            "query_type": "time_trend",
            "x_field": "year",
            "y_field": "trial_count",
        }

    def _process_distribution(self, studies: list[dict], plan: QueryPlan) -> dict:
        group_field = plan.group_by[0] if plan.group_by else GroupByField.PHASE
        category_counts: Counter = Counter()
        category_ncts: dict[str, list[str]] = defaultdict(list)

        for study in studies:
            values = self._extract_field(study, group_field)
            nct_id = self._get_nct_id(study)
            for val in values:
                if val in NOISE_VALUES:
                    continue
                category_counts[val] += 1
                category_ncts[val].append(nct_id)

        # Sort phases in logical order; everything else by count descending
        if group_field == GroupByField.PHASE:
            sorted_cats = sorted(
                category_counts.keys(),
                key=lambda c: PHASE_ORDER.index(c) if c in PHASE_ORDER else 999,
            )
            sorted_items = [(cat, category_counts[cat]) for cat in sorted_cats]
        else:
            sorted_items = category_counts.most_common(20)

        data_points = [
            {
                group_field.value: cat,
                "trial_count": count,
                "_nct_ids": category_ncts[cat],
            }
            for cat, count in sorted_items
        ]

        return {
            "data_points": data_points,
            "total_studies": len(studies),
            "query_type": "distribution",
            "x_field": group_field.value,
            "y_field": "trial_count",
        }

    def _process_geographic(self, studies: list[dict], plan: QueryPlan) -> dict:
        plan_copy = plan.model_copy(deep=True)
        plan_copy.group_by = [GroupByField.COUNTRY]
        result = self._process_distribution(studies, plan_copy)
        result["query_type"] = "geographic"
        return result

    def _process_comparison(self, raw_data: dict, plan: QueryPlan) -> dict:
        group_field = plan.group_by[0] if plan.group_by else GroupByField.PHASE
        series = []

        for entity_label, studies in raw_data.items():
            category_counts: Counter = Counter()
            category_ncts: dict[str, list[str]] = defaultdict(list)

            for study in studies:
                values = self._extract_field(study, group_field)
                nct_id = self._get_nct_id(study)
                for val in values:
                    if val in NOISE_VALUES:
                        continue
                    category_counts[val] += 1
                    category_ncts[val].append(nct_id)

            series.append(
                {
                    "entity": entity_label,
                    "data_points": [
                        {
                            group_field.value: cat,
                            "trial_count": count,
                            "_nct_ids": category_ncts[cat],
                        }
                        for cat, count in category_counts.most_common(20)
                    ],
                    "total": len(studies),
                }
            )

        return {
            "series": series,
            "total_studies": sum(s["total"] for s in series),
            "query_type": "comparison",
            "x_field": group_field.value,
            "y_field": "trial_count",
            "series_field": "entity",
        }

    def _process_network(self, studies: list[dict], plan: QueryPlan) -> dict:
        if len(plan.group_by) >= 2:
            dim_a, dim_b = plan.group_by[0], plan.group_by[1]
        else:
            dim_a = GroupByField.INTERVENTION
            dim_b = GroupByField.CONDITION

        nodes: set[tuple[str, str]] = set()
        edge_counts: Counter = Counter()
        edge_ncts: dict[tuple[str, str], list[str]] = defaultdict(list)

        for study in studies:
            a_vals = self._extract_field(study, dim_a)
            b_vals = self._extract_field(study, dim_b)
            nct_id = self._get_nct_id(study)

            for a in a_vals:
                if a in NOISE_VALUES:
                    continue
                nodes.add((dim_a.value, a))
                for b in b_vals:
                    if b in NOISE_VALUES:
                        continue
                    nodes.add((dim_b.value, b))
                    edge_key = (a, b)
                    edge_counts[edge_key] += 1
                    edge_ncts[edge_key].append(nct_id)

        top_edges = edge_counts.most_common(50)

        # Filter nodes to only those appearing in top edges
        active_node_ids = set()
        for (a, b), _ in top_edges:
            active_node_ids.add(a)
            active_node_ids.add(b)

        node_list = [
            {"id": n[1], "type": n[0]}
            for n in nodes
            if n[1] in active_node_ids
        ]
        edge_list = [
            {
                "source": a,
                "target": b,
                "weight": count,
                "_nct_ids": edge_ncts[(a, b)][:10],
            }
            for (a, b), count in top_edges
        ]

        return {
            "nodes": node_list,
            "edges": edge_list,
            "total_studies": len(studies),
            "query_type": "relationship_network",
        }