import pandas as pd
import numpy as np


def csv_profile(df: pd.DataFrame):
    lines = []
    lines.append(f"Rows: {len(df):,}")
    lines.append(f"Columns: {len(df.columns):,}")
    lines.append("\n### Columns")
    for col in df.columns:
        missing = df[col].isna().sum()
        dtype = df[col].dtype
        lines.append(f"- **{col}**: {dtype}, missing {missing:,}")
    numeric = df.select_dtypes(include=[np.number])
    if not numeric.empty:
        lines.append("\n### Numeric summary")
        lines.append(numeric.describe().to_markdown())
    return "\n".join(lines)
