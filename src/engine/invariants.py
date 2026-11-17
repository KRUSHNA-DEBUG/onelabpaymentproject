"""Strict Invariant Assertion Engine for Record and Value Conservation."""

from typing import Dict, Any
import pandas as pd
from src.models import InternalDisposition, BankDisposition


def verify_all_invariants(
    df_int: pd.DataFrame,
    df_oct: pd.DataFrame,
    df_nov: pd.DataFrame,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify all mathematical invariants: record counts, paise conservation, and fee equations."""
    results = {}

    # Invariant 1: Internal Record Count Conservation
    internal_count = len(df_int)
    null_int_disps = df_int["internal_disposition"].isna().sum()
    int_disposition_counts = df_int["internal_disposition"].value_counts().to_dict()
    sum_int_disps = sum(int_disposition_counts.values())

    results["internal_count_conserved"] = (
        internal_count == 1000 and null_int_disps == 0 and sum_int_disps == 1000
    )

    # Invariant 2: October Bank Record Count Conservation
    oct_count = len(df_oct)
    null_oct_disps = df_oct["bank_disposition"].isna().sum()
    oct_disposition_counts = df_oct["bank_disposition"].value_counts().to_dict()
    sum_oct_disps = sum(oct_disposition_counts.values())

    results["oct_bank_count_conserved"] = (
        oct_count == 945 and null_oct_disps == 0 and sum_oct_disps == 945
    )

    # Invariant 3: November Bank Record Count Conservation
    nov_count = len(df_nov)
    null_nov_disps = df_nov["bank_disposition"].isna().sum()
    nov_disposition_counts = df_nov["bank_disposition"].value_counts().to_dict()
    sum_nov_disps = sum(nov_disposition_counts.values())

    results["nov_bank_count_conserved"] = (
        nov_count == 45 and null_nov_disps == 0 and sum_nov_disps == 45
    )

    # Invariant 4: Bank Fee Structure Invariant
    credits = df_oct[df_oct["posting_type"] == "CREDIT"]
    credit_fee_ok = bool((credits["gross_amount_paise"] - credits["fee_paise"] == credits["net_amount_paise"]).all())

    debits = df_oct[df_oct["posting_type"] == "DEBIT"]
    debit_fee_ok = bool((debits["gross_amount_paise"] + debits["fee_paise"] == debits["net_amount_paise"]).all())

    results["bank_fee_invariants_hold"] = credit_fee_ok and debit_fee_ok

    # Invariant 5: Master Monetary Value Conservation (Residual == 0 paise)
    results["master_monetary_balanced"] = bool(metrics.get("is_master_balanced", False))
    results["balance_residual_paise"] = metrics.get("balance_residual_paise", -999)

    # All invariants passed boolean
    results["all_passed"] = bool(
        results["internal_count_conserved"]
        and results["oct_bank_count_conserved"]
        and results["nov_bank_count_conserved"]
        and results["bank_fee_invariants_hold"]
        and results["master_monetary_balanced"]
    )

    return results
