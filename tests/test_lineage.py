"""
Unit and Integration tests for Column-Level Lineage (Phase 6).
"""

from lineage.models import LineageEdge, LineageNode
from lineage.spark_tracker import LineageRegistry, track_lineage
from lineage.sql_parser import SqlglotLineageParser
from lineage.store import LineageStore


def test_sqlglot_column_lineage_parsing():
    """
    Asserts SQLGlot AST parsing extracts column-to-column edges and transformation types.
    """
    parser = SqlglotLineageParser()
    sql = """
    SELECT
        c.customer_id,
        c.pan as masked_pan,
        SUM(f.amount) as total_volume_inr,
        AVG(f.amount) as avg_amount
    FROM fct_transactions f
    JOIN dim_customer c ON f.customer_id = c.customer_id
    GROUP BY c.customer_id, c.pan
    """

    nodes, edges = parser.parse_query_lineage(
        sql_query=sql,
        target_table="mart_customer_spend",
        target_layer="GOLD",
    )

    assert len(nodes) > 0
    assert len(edges) > 0

    edge_map = {
        (e.source_node_id, e.target_node_id): e.transformation_type for e in edges
    }

    # Sum must be classified as AGGREGATED
    assert any(
        ttype == "AGGREGATED"
        for (s, t), ttype in edge_map.items()
        if "amount" in s and "total_volume" in t
    )
    # Direct column projection
    assert any(
        ttype == "DIRECT"
        for (s, t), ttype in edge_map.items()
        if "customer_id" in s and "customer_id" in t
    )


def test_track_lineage_decorator():
    """
    Asserts @track_lineage decorator records execution runs and edges.
    """
    LineageRegistry.clear()

    @track_lineage(
        inputs=["bronze_customers"],
        outputs=["silver_customers"],
        job_name="clean_customers_job",
        column_map={"pan": "pan", "phone": "phone"},
        transformation_type="MASKED",
    )
    def dummy_clean_step(batch_id: str):
        return f"Processed {batch_id}"

    res = dummy_clean_step("b_test_42")
    assert res == "Processed b_test_42"

    _nodes, edges, runs = LineageRegistry.get_all()
    assert len(runs) == 1
    assert runs[0].status == "SUCCESS"
    assert runs[0].job_name == "clean_customers_job"
    assert len(edges) == 2
    assert all(e.transformation_type == "MASKED" for e in edges)


def test_upstream_trace_to_source():
    """
    Asserts tracing backwards from a Gold column identifies the root source file/column.
    """
    store = LineageStore()

    # Build chain: landing -> bronze -> gate -> silver -> gold_fct -> gold_mart
    chain = [
        ("landing.customers.pan", "bronze.customers.pan", "DIRECT"),
        ("bronze.customers.pan", "gate.customers.pan", "MASKED"),
        ("gate.customers.pan", "silver.customers.pan", "DIRECT"),
        ("silver.customers.pan", "gold.dim_customer.pan", "DIRECT"),
        ("gold.dim_customer.pan", "gold.mart_customer_360.masked_pan", "DIRECT"),
    ]

    for src, tgt, ttype in chain:
        store.add_node(
            LineageNode(
                node_id=src,
                table_name=src.split(".")[1],
                column_name=src.split(".")[2],
                layer=src.split(".")[0].upper(),
            )
        )
        store.add_node(
            LineageNode(
                node_id=tgt,
                table_name=tgt.split(".")[1],
                column_name=tgt.split(".")[2],
                layer=tgt.split(".")[0].upper(),
            )
        )
        store.add_edge(
            LineageEdge(
                source_node_id=src,
                target_node_id=tgt,
                transformation_type=ttype,
                job_name="pipe",
                run_id="r1",
                passes_gate=True,
            )
        )

    trace = store.trace_upstream("gold.mart_customer_360.masked_pan")

    assert trace["target_node"] == "gold.mart_customer_360.masked_pan"
    assert "landing.customers.pan" in trace["root_sources"]
    assert trace["total_depth"] == 5


def test_downstream_impact_analysis():
    """
    Asserts tracing forwards from a source column detects all affected downstream Gold models.
    """
    store = LineageStore()

    store.add_node(
        LineageNode(
            node_id="bronze.customers.pan",
            table_name="customers",
            column_name="pan",
            layer="BRONZE",
        )
    )
    store.add_node(
        LineageNode(
            node_id="silver.customers.pan",
            table_name="customers",
            column_name="pan",
            layer="SILVER",
        )
    )
    store.add_node(
        LineageNode(
            node_id="gold.mart_customer_360.masked_pan",
            table_name="mart_customer_360",
            column_name="masked_pan",
            layer="GOLD",
        )
    )

    store.add_edge(
        LineageEdge(
            source_node_id="bronze.customers.pan",
            target_node_id="silver.customers.pan",
            transformation_type="MASKED",
            job_name="pipe",
            run_id="r1",
        )
    )
    store.add_edge(
        LineageEdge(
            source_node_id="silver.customers.pan",
            target_node_id="gold.mart_customer_360.masked_pan",
            transformation_type="DIRECT",
            job_name="pipe",
            run_id="r1",
        )
    )

    impact = store.trace_downstream("bronze.customers.pan")
    assert "gold.mart_customer_360.masked_pan" in impact["impacted_gold_nodes"]


def test_zero_gate_bypass_enforcement():
    """
    CRITICAL LINEAGE SECURITY TEST:
    Asserts zero bypasses through the masking gate. If a path avoids the gate,
    verify_zero_gate_bypasses() must return False and identify the leak.
    """
    store = LineageStore()

    # Legitimate path: bronze -> gate -> silver -> gold
    store.add_node(
        LineageNode(
            node_id="bronze.customers.pan",
            table_name="customers",
            column_name="pan",
            layer="BRONZE",
        )
    )
    store.add_node(
        LineageNode(
            node_id="gate.customers.pan",
            table_name="customers",
            column_name="pan",
            layer="GATE",
        )
    )
    store.add_node(
        LineageNode(
            node_id="silver.customers.pan",
            table_name="customers",
            column_name="pan",
            layer="SILVER",
        )
    )
    store.add_node(
        LineageNode(
            node_id="gold.dim_customer.pan",
            table_name="dim_customer",
            column_name="pan",
            layer="GOLD",
        )
    )

    store.add_edge(
        LineageEdge(
            source_node_id="bronze.customers.pan",
            target_node_id="gate.customers.pan",
            transformation_type="MASKED",
            job_name="gate_job",
            run_id="r1",
            passes_gate=True,
        )
    )
    store.add_edge(
        LineageEdge(
            source_node_id="gate.customers.pan",
            target_node_id="silver.customers.pan",
            transformation_type="DIRECT",
            job_name="silver_job",
            run_id="r1",
            passes_gate=True,
        )
    )
    store.add_edge(
        LineageEdge(
            source_node_id="silver.customers.pan",
            target_node_id="gold.dim_customer.pan",
            transformation_type="DIRECT",
            job_name="gold_job",
            run_id="r1",
            passes_gate=True,
        )
    )

    is_clean, violations = store.verify_zero_gate_bypasses()
    assert is_clean is True, "Legitimate lineage should have zero bypasses"
    assert len(violations) == 0

    # Injected bypass: direct unmasked edge from bronze to a rogue gold table
    store.add_node(
        LineageNode(
            node_id="gold.rogue_unmasked_mart.raw_pan",
            table_name="rogue_mart",
            column_name="raw_pan",
            layer="GOLD",
        )
    )
    store.add_edge(
        LineageEdge(
            source_node_id="bronze.customers.pan",
            target_node_id="gold.rogue_unmasked_mart.raw_pan",
            transformation_type="DIRECT",
            job_name="rogue_job",
            run_id="leak_run",
            passes_gate=False,  # Bypassed the gate!
        )
    )

    is_clean_after, violations_after = store.verify_zero_gate_bypasses()
    assert is_clean_after is False, "Gate bypass must be flagged"
    assert len(violations_after) == 1
    assert violations_after[0]["source"] == "bronze.customers.pan"
