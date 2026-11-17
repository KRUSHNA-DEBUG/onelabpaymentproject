"""Data Normalizer and Temporal Aging Utility."""

from datetime import datetime
import numpy as np
import pandas as pd
from src.config import BANK_HOLIDAYS, SLA_BUSINESS_DAYS


def calculate_business_days(start_date: str, end_date: str, holidays=BANK_HOLIDAYS) -> int:
    """Calculate business days between two YYYY-MM-DD dates excluding weekends & holidays."""
    # Using weekmask '1111100' (Mon-Fri)
    holidays_arr = np.array(holidays, dtype='datetime64[D]')
    d_start = np.datetime64(start_date, 'D')
    d_end = np.datetime64(end_date, 'D')
    
    if d_start > d_end:
        return 0
    
    return int(np.busday_count(d_start, d_end, weekmask='1111100', holidays=holidays_arr))


def normalize_internal_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize internal transactions dataframe with strict integer types."""
    df = df.copy()
    df["internal_txn_id"] = df["internal_txn_id"].astype(str).str.strip()
    df["utr_number"] = df["utr_number"].astype(str).str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date_str"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["amount_paise"] = df["amount_paise"].astype("int64")
    df["txn_type"] = df["txn_type"].astype(str).str.upper()
    df["payment_rail"] = df["payment_rail"].astype(str).str.upper()
    df["status"] = df["status"].astype(str).str.upper()
    if "parent_txn_id" in df.columns:
        df["parent_txn_id"] = df["parent_txn_id"].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ["None", "nan", ""] else None
        )
    else:
        df["parent_txn_id"] = None
    return df


def normalize_bank_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize bank statement dataframe with strict integer types."""
    df = df.copy()
    df["bank_stmt_id"] = df["bank_stmt_id"].astype(str).str.strip()
    df["bank_utr_number"] = df["bank_utr_number"].astype(str).str.strip()
    df["settlement_date"] = pd.to_datetime(df["settlement_date"]).dt.strftime("%Y-%m-%d")
    df["posting_type"] = df["posting_type"].astype(str).str.upper()
    df["gross_amount_paise"] = df["gross_amount_paise"].astype("int64")
    df["fee_paise"] = df["fee_paise"].fillna(0).astype("int64")
    df["net_amount_paise"] = df["net_amount_paise"].astype("int64")
    if "narration" in df.columns:
        df["narration"] = df["narration"].astype(str)
    else:
        df["narration"] = ""
    return df
