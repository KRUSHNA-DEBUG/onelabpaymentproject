"""Duplicate Detection and Quarantine Isolation Engine."""

from typing import Tuple, Set
import pandas as pd
from src.models import InternalDisposition, BankDisposition


def isolate_duplicates(
    df_internal: pd.DataFrame, df_bank: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Identify duplicate clusters, quarantine ambiguous records, and protect counterparts.

    Returns:
        (df_internal_quarantined, df_bank_quarantined, df_internal_clean, df_bank_clean)
    """
    df_int = df_internal.copy()
    df_bnk = df_bank.copy()

    # Initialize disposition columns if not present
    if "internal_disposition" not in df_int.columns:
        df_int["internal_disposition"] = None
    if "bank_disposition" not in df_bnk.columns:
        df_bnk["bank_disposition"] = None

    # Step 1: Detect internal duplicates (count > 1 on utr_number)
    int_utr_counts = df_int["utr_number"].value_counts()
    int_dup_utrs: Set[str] = set(int_utr_counts[int_utr_counts > 1].index)

    # Step 2: Detect bank duplicates (count > 1 on bank_utr_number)
    bnk_utr_counts = df_bnk["bank_utr_number"].value_counts()
    bnk_dup_utrs: Set[str] = set(bnk_utr_counts[bnk_utr_counts > 1].index)

    # Tagging Internal Records
    # 1A. Direct internal duplicates
    is_int_dup = df_int["utr_number"].isin(int_dup_utrs)
    df_int.loc[is_int_dup, "internal_disposition"] = InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value

    # 1B. Internal counterparts to bank duplicates (internal row is unique, but bank has duplicates)
    is_int_held_for_bnk_dup = (~is_int_dup) & (df_int["utr_number"].isin(bnk_dup_utrs))
    df_int.loc[is_int_held_for_bnk_dup, "internal_disposition"] = InternalDisposition.INTERNAL_HELD_FOR_BANK_DUPLICATE.value

    # Tagging Bank Records
    # 2A. Direct bank duplicates
    is_bnk_dup = df_bnk["bank_utr_number"].isin(bnk_dup_utrs)
    df_bnk.loc[is_bnk_dup, "bank_disposition"] = BankDisposition.SUSPECTED_DUPLICATE_BANK.value

    # 2B. Bank counterparts to internal duplicates (bank row is unique, but internal has duplicates)
    is_bnk_held_for_int_dup = (~is_bnk_dup) & (df_bnk["bank_utr_number"].isin(int_dup_utrs))
    df_bnk.loc[is_bnk_held_for_int_dup, "bank_disposition"] = BankDisposition.BANK_HELD_FOR_INTERNAL_DUPLICATE.value

    # Quarantine vs Clean partitions
    mask_int_quarantine = df_int["internal_disposition"].notna()
    df_internal_quarantined = df_int[mask_int_quarantine].copy()
    df_internal_clean = df_int[~mask_int_quarantine].copy()

    mask_bnk_quarantine = df_bnk["bank_disposition"].notna()
    df_bank_quarantined = df_bnk[mask_bnk_quarantine].copy()
    df_bank_clean = df_bnk[~mask_bnk_quarantine].copy()

    return df_internal_quarantined, df_bank_quarantined, df_internal_clean, df_bank_clean
