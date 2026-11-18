"""
Deduplication Engine for SentraFlow Silver Layer.
"""

import pandas as pd


def deduplicate_records(
    df: pd.DataFrame,
    business_keys: list[str],
    order_by_col: str = "_ingest_ts",
    ascending: bool = False,
) -> pd.DataFrame:
    """
    Deduplicates records based on primary business keys, keeping the latest record
    according to the specified ordering column.
    """
    if df.empty:
        return df

    # Check that required columns exist
    for k in business_keys:
        if k not in df.columns:
            return df

    sort_col = order_by_col if order_by_col in df.columns else None

    if sort_col:
        # Sort and take the first record per business key
        sorted_df = df.sort_values(by=sort_col, ascending=ascending)
        deduped = sorted_df.drop_duplicates(subset=business_keys, keep="first").copy()
    else:
        deduped = df.drop_duplicates(subset=business_keys, keep="last").copy()

    return deduped.reset_index(drop=True)
