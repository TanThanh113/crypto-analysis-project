import os
import logging
from datetime import datetime
import pandas as pd

def save_dataframe_to_parquet(
    df: pd.DataFrame, 
    base_dir: str, 
    partition_cols: list = None, 
    file_prefix: str = "data", 
    compression: str = "snappy"
) -> list:
    """
    Args:
        df: The Pandas DataFrame to be saved.
        base_dir: The root directory containing the data.
        partition_cols: A list of columns used to divide the directory (e.g., ['year', 'month']). If None, save to a single file.
        file_prefix: File name prefix (e.g., 'tiingo_raw', 'user_logs').
        compression: Data compression standard (snappy, gzip, brotli, None).
        
    Returns:
        List: A list of file paths that have been successfully saved.
    """
    if df is None or df.empty:
        logging.warning("⚠️ If the DataFrame is empty, skip the save operation.")
        return []

    saved_files = []
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    # ---------------------------------------------------------
    # CASE 1: SAVE AS A SINGLE ICEBERG/FLAT FILE
    # ---------------------------------------------------------
    if not partition_cols:
        os.makedirs(base_dir, exist_ok=True)
        filename = os.path.join(base_dir, f"{file_prefix}_{timestamp}.parquet")
        
        df.to_parquet(filename, index=False, engine='pyarrow', compression=compression)
        logging.info(f"✅ [ICEBERG MODE] All the data has been saved to one file: {filename}")
        
        saved_files.append(filename)
        return saved_files

    # ---------------------------------------------------------
    # CASE 2: SAVE BY PARTITION (HIVE STYLE)
    # ---------------------------------------------------------
    # Security check: Ensure that partition columns exist in the DF.
    missing_cols = [col for col in partition_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ The columns used for partitioning do not exist in the DataFrame: {missing_cols}")

    groups = df.groupby(partition_cols)
    for group_keys, subset in groups:
        # Pandas returns `group_keys` as a tuple if there is more than one column, and a value if there is only one column. Consistent handling:
        if not isinstance(group_keys, tuple):
            group_keys = (group_keys,)
        
        # Automatically create Hive folder structure: base_dir/col1=val1/col2=val2/...
        partition_path_parts = [f"{col}={val}" for col, val in zip(partition_cols, group_keys)]
        partition_dir = os.path.join(base_dir, *partition_path_parts)
        os.makedirs(partition_dir, exist_ok=True)

        # Create filenames that include the partition values ​​for easier debugging.
        val_str = "_".join(str(v) for v in group_keys)
        filename = os.path.join(partition_dir, f"{file_prefix}_{val_str}_part-{timestamp}.parquet")
        
        subset.to_parquet(filename, index=False, engine='pyarrow', compression=compression)
        saved_files.append(filename)
        
    logging.info(f"✅ Successfully saved {len(saved_files)} Hive partitions to: {base_dir}")
    return saved_files