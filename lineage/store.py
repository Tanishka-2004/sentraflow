"""
Lineage Store and Graph Traversal API for SentraFlow.
"""

from collections import deque
from typing import Any

from lineage.models import LineageEdge, LineageNode, LineageRun


class LineageStore:
    """
    Stores and queries column-level lineage graph in memory or persisted database.
    """

    def __init__(self):
        self.nodes: dict[str, LineageNode] = {}
        self.edges: list[LineageEdge] = []
        self.runs: list[LineageRun] = []

    def add_node(self, node: LineageNode):
        self.nodes[node.node_id] = node

    def add_edge(self, edge: LineageEdge):
        self.edges.append(edge)

    def record_run(self, run: LineageRun):
        self.runs.append(run)

    def to_graph_json(self) -> dict[str, Any]:
        """Export nodes and edges in serialized dictionary format."""
        return {
            "nodes": [n.model_dump() for n in self.nodes.values()],
            "edges": [e.model_dump() for e in self.edges],
        }

    def trace_upstream(self, target_node_id: str) -> dict[str, Any]:
        """
        Traces backwards from target column to find all upstream sources
        down to the raw Landing/Bronze layer.
        """
        visited_nodes: set[str] = set()
        traversed_edges: list[dict[str, Any]] = []
        queue = deque([target_node_id])

        # Adjacency map: target -> incoming edges
        incoming_map: dict[str, list[LineageEdge]] = {}
        for e in self.edges:
            incoming_map.setdefault(e.target_node_id, []).append(e)

        while queue:
            curr = queue.popleft()
            if curr in visited_nodes:
                continue
            visited_nodes.add(curr)

            for edge in incoming_map.get(curr, []):
                traversed_edges.append(edge.model_dump())
                if edge.source_node_id not in visited_nodes:
                    queue.append(edge.source_node_id)

        source_roots = [nid for nid in visited_nodes if not incoming_map.get(nid)]

        return {
            "target_node": target_node_id,
            "upstream_nodes": [
                self.nodes[n].model_dump() for n in visited_nodes if n in self.nodes
            ],
            "edges": traversed_edges,
            "root_sources": source_roots,
            "total_depth": len(traversed_edges),
        }

    def trace_downstream(self, source_node_id: str) -> dict[str, Any]:
        """
        Impact analysis: traces forwards from a source column to find all affected
        downstream models, facts, and analytical marts.
        """
        visited_nodes: set[str] = set()
        traversed_edges: list[dict[str, Any]] = []
        queue = deque([source_node_id])

        # Adjacency map: source -> outgoing edges
        outgoing_map: dict[str, list[LineageEdge]] = {}
        for e in self.edges:
            outgoing_map.setdefault(e.source_node_id, []).append(e)

        while queue:
            curr = queue.popleft()
            if curr in visited_nodes:
                continue
            visited_nodes.add(curr)

            for edge in outgoing_map.get(curr, []):
                traversed_edges.append(edge.model_dump())
                if edge.target_node_id not in visited_nodes:
                    queue.append(edge.target_node_id)

        impacted_marts = [
            nid
            for nid in visited_nodes
            if "mart" in nid.lower() or "fct" in nid.lower() or "dim" in nid.lower()
        ]

        return {
            "source_node": source_node_id,
            "downstream_nodes": [
                self.nodes[n].model_dump() for n in visited_nodes if n in self.nodes
            ],
            "edges": traversed_edges,
            "impacted_gold_nodes": impacted_marts,
        }

    def verify_zero_gate_bypasses(self) -> tuple[bool, list[dict[str, Any]]]:
        """
        AUDIT VERIFICATION:
        Ensures that every lineage path from a raw PII column to Gold marts
        passes through the governance masking gate.
        Returns (is_clean, list_of_violations).
        """
        pii_keywords = ["pan", "email", "phone", "aadhaar", "dob", "address"]
        bypasses: list[dict[str, Any]] = []

        # Find all raw bronze/landing nodes with PII names
        raw_pii_nodes = [
            n
            for n in self.nodes.values()
            if any(k in n.column_name.lower() for k in pii_keywords)
            and (
                n.layer in ["BRONZE", "LANDING"]
                or "bronze" in n.node_id.lower()
                or "landing" in n.node_id.lower()
            )
        ]

        for pii_node in raw_pii_nodes:
            # Check all downstream paths
            impact = self.trace_downstream(pii_node.node_id)
            for edge in impact["edges"]:
                if not edge.get("passes_gate", True):
                    bypasses.append(
                        {
                            "source": pii_node.node_id,
                            "bypassed_edge": edge,
                            "reason": "Direct unmasked edge bypassed PII gate",
                        }
                    )

        return len(bypasses) == 0, bypasses

    def get_react_flow_graph(self) -> dict[str, Any]:
        """
        Exports lineage graph structure in React Flow node & edge format
        for direct rendering in the Next.js analyst dashboard.
        """
        rf_nodes = []
        for i, node in enumerate(self.nodes.values()):
            rf_nodes.append(
                {
                    "id": node.node_id,
                    "data": {
                        "label": f"{node.table_name}.{node.column_name}",
                        "layer": node.layer,
                        "is_masked": node.is_masked,
                    },
                    "position": {"x": 200 * (i % 5), "y": 100 * (i // 5)},
                }
            )

        rf_edges = []
        for j, edge in enumerate(self.edges):
            rf_edges.append(
                {
                    "id": f"e_{j}_{edge.source_node_id}_{edge.target_node_id}",
                    "source": edge.source_node_id,
                    "target": edge.target_node_id,
                    "label": edge.transformation_type,
                    "animated": edge.transformation_type == "MASKED",
                }
            )

        return {"nodes": rf_nodes, "edges": rf_edges}
