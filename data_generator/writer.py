"""
Batch writer for synthetic landing files (Parquet and CSV).
"""

from pathlib import Path

import pandas as pd

from data_generator.entities import Account, Customer, Merchant, Transaction


def export_batch_to_landing(
    records: list[Customer | Account | Merchant | Transaction],
    entity_name: str,
    output_dir: str,
    file_format: str = "parquet",
    batch_id: str = "batch_001",
) -> str:
    """
    Exports a list of entities to a landing zone in Parquet or CSV format.
    Returns the file path created.
    """
    target_dir = Path(output_dir) / entity_name / f"batch_id={batch_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    data = [r.model_dump() for r in records]
    df = pd.DataFrame(data)

    if file_format.lower() == "parquet":
        file_path = target_dir / f"{entity_name}_{batch_id}.parquet"
        df.to_parquet(file_path, index=False, engine="pyarrow")
    elif file_format.lower() == "csv":
        file_path = target_dir / f"{entity_name}_{batch_id}.csv"
        df.to_csv(file_path, index=False)
    else:
        raise ValueError(
            f"Unsupported format: {file_format}. Choose 'parquet' or 'csv'."
        )

    return str(file_path)
