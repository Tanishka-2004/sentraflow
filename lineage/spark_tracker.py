"""
PySpark & Python job lineage tracker decorator for SentraFlow.
"""

import functools
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import ClassVar

from lineage.models import LineageEdge, LineageNode, LineageRun


class LineageRegistry:
    """Singleton registry tracking runtime lineage events."""

    _nodes: ClassVar[dict[str, LineageNode]] = {}
    _edges: ClassVar[list[LineageEdge]] = []
    _runs: ClassVar[list[LineageRun]] = []

    @classmethod
    def register_nodes(cls, nodes: list[LineageNode]):
        for n in nodes:
            cls._nodes[n.node_id] = n

    @classmethod
    def register_edges(cls, edges: list[LineageEdge]):
        cls._edges.extend(edges)

    @classmethod
    def register_run(cls, run: LineageRun):
        cls._runs.append(run)

    @classmethod
    def get_all(cls) -> tuple[list[LineageNode], list[LineageEdge], list[LineageRun]]:
        return list(cls._nodes.values()), list(cls._edges), list(cls._runs)

    @classmethod
    def clear(cls):
        cls._nodes.clear()
        cls._edges.clear()
        cls._runs.clear()


def track_lineage(
    inputs: list[str],
    outputs: list[str],
    job_name: str,
    column_map: dict[str, str] | None = None,
    transformation_type: str = "DIRECT",
    passes_gate: bool = True,
):
    """
    Decorator that tracks data lineage across pipeline stages.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            run_id = f"run_{uuid.uuid4().hex[:8]}"
            start_ts = datetime.now(timezone.utc).isoformat()
            status = "SUCCESS"

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = "FAILED"
                raise
            finally:
                end_ts = datetime.now(timezone.utc).isoformat()
                nodes_to_add: list[LineageNode] = []
                edges_to_add: list[LineageEdge] = []

                # Register input and output nodes
                in_tbl = inputs[0] if inputs else "source"
                out_tbl = outputs[0] if outputs else "target"

                if column_map:
                    for src_col, tgt_col in column_map.items():
                        src_id = f"{in_tbl}.{src_col}"
                        tgt_id = f"{out_tbl}.{tgt_col}"

                        nodes_to_add.append(
                            LineageNode(
                                node_id=src_id,
                                table_name=in_tbl,
                                column_name=src_col,
                                layer="BRONZE"
                                if "bronze" in in_tbl.lower()
                                else "GATE",
                            )
                        )
                        nodes_to_add.append(
                            LineageNode(
                                node_id=tgt_id,
                                table_name=out_tbl,
                                column_name=tgt_col,
                                layer="SILVER"
                                if "silver" in out_tbl.lower()
                                else "GATE",
                                is_masked="mask" in tgt_col.lower()
                                or "pan" in tgt_col.lower(),
                            )
                        )
                        edges_to_add.append(
                            LineageEdge(
                                source_node_id=src_id,
                                target_node_id=tgt_id,
                                transformation_type=transformation_type,
                                job_name=job_name,
                                run_id=run_id,
                                passes_gate=passes_gate,
                            )
                        )

                LineageRegistry.register_nodes(nodes_to_add)
                LineageRegistry.register_edges(edges_to_add)
                LineageRegistry.register_run(
                    LineageRun(
                        run_id=run_id,
                        job_name=job_name,
                        status=status,
                        started_at=start_ts,
                        completed_at=end_ts,
                        nodes_count=len(nodes_to_add),
                        edges_count=len(edges_to_add),
                    )
                )

        return wrapper

    return decorator
