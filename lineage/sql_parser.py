"""
SQLGlot-powered column-level lineage parser for dbt SQL models.
"""

import sqlglot
from sqlglot import exp

from lineage.models import LineageEdge, LineageNode


class SqlglotLineageParser:
    """
    Parses compiled SQL queries to extract source_column -> target_column lineage edges.
    """

    def __init__(self, dialect: str = "spark"):
        self.dialect = dialect

    def parse_query_lineage(
        self,
        sql_query: str,
        target_table: str,
        target_layer: str = "GOLD",
        job_name: str = "dbt_transform",
        run_id: str = "run_001",
    ) -> tuple[list[LineageNode], list[LineageEdge]]:
        """
        Parses SQL to identify input tables, input columns, and their mapping
        to output columns in target_table.
        """
        nodes: dict[str, LineageNode] = {}
        edges: list[LineageEdge] = []

        try:
            parsed = sqlglot.parse_one(sql_query, read=self.dialect)
        except Exception:  # noqa: BLE001
            # Fallback to standard dialect
            parsed = sqlglot.parse_one(sql_query)

        # Identify source tables
        source_tables = [t.name for t in parsed.find_all(exp.Table) if t.name]

        # Extract select expressions
        select_expressions = parsed.find_all(exp.Select)
        main_select = next(select_expressions, None)

        if not main_select:
            return list(nodes.values()), edges

        for item in main_select.expressions:
            target_col_name = item.alias_or_name

            # Determine target node
            target_node_id = f"{target_table}.{target_col_name}"
            if target_node_id not in nodes:
                nodes[target_node_id] = LineageNode(
                    node_id=target_node_id,
                    table_name=target_table,
                    column_name=target_col_name,
                    layer=target_layer,
                    is_masked="mask" in target_col_name.lower(),
                )

            # Determine transformation type
            is_agg = bool(list(item.find_all(exp.AggFunc)))
            is_case = bool(list(item.find_all(exp.Case)))
            is_func = bool(list(item.find_all(exp.Anonymous))) or is_case

            if is_agg:
                transform_type = "AGGREGATED"
            elif is_func:
                transform_type = "DERIVED"
            else:
                transform_type = "DIRECT"

            # Find source columns
            cols = list(item.find_all(exp.Column))
            for c in cols:
                source_col = c.name
                # Determine source table
                source_tbl = c.table or (
                    source_tables[0] if source_tables else "unknown_source"
                )
                source_node_id = f"{source_tbl}.{source_col}"

                if source_node_id not in nodes:
                    nodes[source_node_id] = LineageNode(
                        node_id=source_node_id,
                        table_name=source_tbl,
                        column_name=source_col,
                        layer="SILVER"
                        if "silver" in source_tbl.lower() or "stg" in source_tbl.lower()
                        else "UNKNOWN",
                        is_masked="mask" in source_col.lower(),
                    )

                edges.append(
                    LineageEdge(
                        source_node_id=source_node_id,
                        target_node_id=target_node_id,
                        transformation_type=transform_type,
                        job_name=job_name,
                        run_id=run_id,
                        passes_gate=True,
                    )
                )

        return list(nodes.values()), edges
