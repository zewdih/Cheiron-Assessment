"""Run example queries against the Cheiron service and save JSON outputs.

Usage:
    python -m cheiron.examples.run_examples

Requires the service to be running at http://localhost:8000
"""

import asyncio
import json
import sys
from pathlib import Path
import httpx

EXAMPLES = [
    {
        "name": "01_time_trend_pembrolizumab",
        "request": {
            "query": "How has the number of trials for Pembrolizumab changed over time?",
            "drug_name": "Pembrolizumab",
        },
    },
    {
        "name": "02_distribution_diabetes_phases",
        "request": {
            "query": "How are diabetes trials distributed across phases?",
            "condition": "diabetes",
        },
    },
    {
        "name": "03_comparison_pembrolizumab_vs_nivolumab",
        "request": {
            "query": "Compare the phase distribution of trials for Pembrolizumab vs Nivolumab",
        },
    },
    {
        "name": "04_geographic_oncology",
        "request": {
            "query": "Which countries have the most recruiting oncology trials?",
            "condition": "cancer",
        },
    },
    {
        "name": "05_network_breast_cancer",
        "request": {
            "query": "Show a network of drugs and conditions in breast cancer trials",
            "condition": "breast cancer",
        },
    },
]

BASE_URL = "http://localhost:8000/api/v1"


async def run_examples():
    output_dir = Path(__file__).parent
    async with httpx.AsyncClient(timeout=120.0) as client:
        for example in EXAMPLES:
            name = example["name"]
            print(f"\nRunning: {name}")
            print(f"  Query: {example['request']['query']}")

            try:
                response = await client.post(
                    f"{BASE_URL}/query", json=example["request"]
                )
                response.raise_for_status()
                result = response.json()

                output_file = output_dir / f"{name}.json"
                with open(output_file, "w") as f:
                    json.dump(
                        {"request": example["request"], "response": result},
                        f,
                        indent=2,
                    )
                print(f"  Saved to {output_file}")

                viz = result.get("visualization", {})
                print(f"  Type: {viz.get('type')}")
                print(f"  Title: {viz.get('title')}")
                data_count = len(viz.get("data", []))
                if viz.get("network_data"):
                    nodes = len(viz["network_data"].get("nodes", []))
                    edges = len(viz["network_data"].get("edges", []))
                    print(f"  Network: {nodes} nodes, {edges} edges")
                else:
                    print(f"  Data points: {data_count}")
                print(
                    f"  Total studies: {result.get('meta', {}).get('total_studies_analyzed')}"
                )

            except Exception as e:
                print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(run_examples())