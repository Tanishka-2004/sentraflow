from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List

def get_column_lineage(db: Session, table: str, column: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Executes a recursive CTE query to build an upstream lineage graph for a given target column.
    Formats the output for React Flow rendering.
    """
    query = text("""
        WITH RECURSIVE lineage_path AS (
            -- Anchor member: start at the target column
            SELECT id, run_id, step_name, source_table, source_column, target_table, target_column, event_type, timestamp, 1 as depth
            FROM lineage_events
            WHERE target_table = :table AND target_column = :column
            
            UNION ALL
            
            -- Recursive member: link source columns of existing path to targets of upstream steps
            SELECT le.id, le.run_id, le.step_name, le.source_table, le.source_column, le.target_table, le.target_column, le.event_type, le.timestamp, lp.depth + 1
            FROM lineage_events le
            INNER JOIN lineage_path lp ON le.target_table = lp.source_table AND le.target_column = lp.source_column
            WHERE lp.depth < 10 -- Safety cap to prevent infinite loop/cycles
        )
        SELECT DISTINCT run_id, step_name, source_table, source_column, target_table, target_column, event_type 
        FROM lineage_path;
    """)
    
    result = db.execute(query, {"table": table, "column": column})
    rows = result.fetchall()
    
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()
    
    # If the rows are empty, add the queried node as a standalone node
    target_node_id = f"{table}.{column}"
    seen_nodes.add(target_node_id)
    nodes.append({
        "id": target_node_id,
        "label": target_node_id,
        "type": "column"
    })
    
    for row in rows:
        run_id, step_name, src_tbl, src_col, tgt_tbl, tgt_col, evt_type = row
        
        src_node_id = f"{src_tbl}.{src_col}" if src_col else src_tbl
        tgt_node_id = f"{tgt_tbl}.{tgt_col}" if tgt_col else tgt_tbl
        
        if src_node_id not in seen_nodes:
            seen_nodes.add(src_node_id)
            nodes.append({
                "id": src_node_id,
                "label": src_node_id,
                "type": "column" if src_col else "table"
            })
            
        if tgt_node_id not in seen_nodes:
            seen_nodes.add(tgt_node_id)
            nodes.append({
                "id": tgt_node_id,
                "label": tgt_node_id,
                "type": "column" if tgt_col else "table"
            })
            
        edge_id = f"edge-{src_node_id}-to-{tgt_node_id}"
        if edge_id not in seen_edges:
            seen_edges.add(edge_id)
            edges.append({
                "id": edge_id,
                "source": src_node_id,
                "target": tgt_node_id
            })
            
    return {"nodes": nodes, "edges": edges}
