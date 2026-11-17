"""Multi-Pass Deterministic Reconciliation Engine with Two-Stage Month-End Clearing."""

from typing import Dict, Any, Tuple
import pandas as pd
from src.config import (
    ROUNDING_TOLERANCE_PAISE,
    SLA_BUSINESS_DAYS,
    OCTOBER_CUTOFF_DATE,
)
from src.models import (
    InternalDisposition,
    BankDisposition,
    paise_to_inr_str,
)
from src.engine.normalizer import (
    normalize_internal_df,
    normalize_bank_df,
    calculate_business_days,
)
from src.engine.duplicate_detector import isolate_duplicates
from src.engine.refund_tracker import evaluate_refund_lineage
from src.engine.explainability import get_explanation


def reconcile_datasets(
    df_internal_raw: pd.DataFrame,
    df_bank_oct_raw: pd.DataFrame,
    df_bank_nov_raw: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Execute complete 2-stage reconciliation workflow with deterministic audit trail.

    Returns:
        (df_internal_result, df_bank_oct_result, df_bank_nov_result, summary_metrics)
    """
    # -------------------------------------------------------------
    # 1. Normalization
    # -------------------------------------------------------------
    df_int = normalize_internal_df(df_internal_raw)
    df_oct = normalize_bank_df(df_bank_oct_raw)
    df_nov = normalize_bank_df(df_bank_nov_raw)

    # Initialize result tracking columns on internal df
    df_int["internal_disposition"] = None
    df_int["october_snapshot_status"] = None
    df_int["delta_paise"] = 0
    df_int["matched_bank_stmt_id"] = None
    df_int["matched_settlement_date"] = None
    df_int["matched_bank_gross_paise"] = None
    df_int["matched_bank_fee_paise"] = None

    # Initialize result tracking columns on bank dfs
    df_oct["bank_disposition"] = None
    df_oct["delta_paise"] = 0
    df_oct["matched_internal_txn_id"] = None

    df_nov["bank_disposition"] = None
    df_nov["delta_paise"] = 0
    df_nov["matched_internal_txn_id"] = None

    # -------------------------------------------------------------
    # 2. Duplicate Detection & Quarantine
    # -------------------------------------------------------------
    int_quarantine, oct_quarantine, int_clean, oct_clean = isolate_duplicates(df_int, df_oct)

    # Apply quarantined dispositions back to master dfs
    df_int.update(int_quarantine[["internal_disposition"]])
    df_oct.update(oct_quarantine[["bank_disposition"]])

    # -------------------------------------------------------------
    # 3. Clean 1:1 Matching on Payments
    # -------------------------------------------------------------
    # Split clean candidate pools
    clean_payments = int_clean[int_clean["txn_type"] == "PAYMENT"].copy()
    clean_refunds = int_clean[int_clean["txn_type"] == "REFUND"].copy()
    
    clean_credits = oct_clean[oct_clean["posting_type"] == "CREDIT"].copy()
    clean_debits = oct_clean[oct_clean["posting_type"] == "DEBIT"].copy()

    # Index October bank credits by bank_utr_number
    # (Safe: duplicate UTRs were already isolated to quarantine)
    oct_credit_dict = {
        row["bank_utr_number"]: row for _, row in clean_credits.iterrows()
    }
    consumed_oct_credit_utrs = set()
    settled_payment_txn_ids = set()

    for idx, row in clean_payments.iterrows():
        utr = row["utr_number"]
        amt = row["amount_paise"]
        
        if utr in oct_credit_dict:
            bank_row = oct_credit_dict[utr]
            gross = bank_row["gross_amount_paise"]
            delta = amt - gross  # positive if internal > bank
            
            df_int.loc[idx, "delta_paise"] = delta
            df_int.loc[idx, "matched_bank_stmt_id"] = bank_row["bank_stmt_id"]
            df_int.loc[idx, "matched_settlement_date"] = bank_row["settlement_date"]
            df_int.loc[idx, "matched_bank_gross_paise"] = gross
            df_int.loc[idx, "matched_bank_fee_paise"] = bank_row["fee_paise"]
            
            # Find the corresponding bank index
            bank_idx = df_oct[df_oct["bank_stmt_id"] == bank_row["bank_stmt_id"]].index[0]
            df_oct.loc[bank_idx, "delta_paise"] = -delta
            df_oct.loc[bank_idx, "matched_internal_txn_id"] = row["internal_txn_id"]

            if delta == 0:
                df_int.loc[idx, "internal_disposition"] = InternalDisposition.FULLY_RECONCILED.value
                df_int.loc[idx, "october_snapshot_status"] = InternalDisposition.FULLY_RECONCILED.value
                df_oct.loc[bank_idx, "bank_disposition"] = BankDisposition.BANK_RECONCILED_CREDIT.value
                settled_payment_txn_ids.add(row["internal_txn_id"])
            elif abs(delta) <= ROUNDING_TOLERANCE_PAISE:
                df_int.loc[idx, "internal_disposition"] = InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value
                df_int.loc[idx, "october_snapshot_status"] = InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value
                df_oct.loc[bank_idx, "bank_disposition"] = BankDisposition.BANK_RECONCILED_CREDIT.value
                settled_payment_txn_ids.add(row["internal_txn_id"])
            else:
                df_int.loc[idx, "internal_disposition"] = InternalDisposition.AMOUNT_MISMATCH_BREAK.value
                df_int.loc[idx, "october_snapshot_status"] = InternalDisposition.AMOUNT_MISMATCH_BREAK.value
                df_oct.loc[bank_idx, "bank_disposition"] = BankDisposition.BANK_RECONCILED_CREDIT.value
            
            consumed_oct_credit_utrs.add(utr)

    # -------------------------------------------------------------
    # 4. Clean 1:1 Matching on Refunds & Lineage Validation
    # -------------------------------------------------------------
    oct_debit_dict = {
        row["bank_utr_number"]: row for _, row in clean_debits.iterrows()
    }
    consumed_oct_debit_utrs = set()

    for idx, row in clean_refunds.iterrows():
        utr = row["utr_number"]
        amt = row["amount_paise"]
        parent_id = row["parent_txn_id"]

        if utr in oct_debit_dict:
            bank_row = oct_debit_dict[utr]
            gross = bank_row["gross_amount_paise"]
            delta = amt - gross

            df_int.loc[idx, "delta_paise"] = delta
            df_int.loc[idx, "matched_bank_stmt_id"] = bank_row["bank_stmt_id"]
            df_int.loc[idx, "matched_settlement_date"] = bank_row["settlement_date"]
            df_int.loc[idx, "matched_bank_gross_paise"] = gross
            df_int.loc[idx, "matched_bank_fee_paise"] = bank_row["fee_paise"]

            bank_idx = df_oct[df_oct["bank_stmt_id"] == bank_row["bank_stmt_id"]].index[0]
            df_oct.loc[bank_idx, "delta_paise"] = -delta
            df_oct.loc[bank_idx, "matched_internal_txn_id"] = row["internal_txn_id"]
            df_oct.loc[bank_idx, "bank_disposition"] = BankDisposition.BANK_RECONCILED_DEBIT.value

            # Validate lineage
            refund_disp = evaluate_refund_lineage(parent_id, settled_payment_txn_ids)
            df_int.loc[idx, "internal_disposition"] = refund_disp.value
            df_int.loc[idx, "october_snapshot_status"] = refund_disp.value
            
            consumed_oct_debit_utrs.add(utr)
        else:
            # Unsettled internal refund
            df_int.loc[idx, "internal_disposition"] = "UNSETTLED_INTERNAL_REFUND"
            df_int.loc[idx, "october_snapshot_status"] = "UNSETTLED_INTERNAL_REFUND"

    # Unconsumed clean October bank credits -> UNMATCHED_BANK_CREDIT
    for _, bank_row in clean_credits.iterrows():
        utr = bank_row["bank_utr_number"]
        if utr not in consumed_oct_credit_utrs:
            b_idx = df_oct[df_oct["bank_stmt_id"] == bank_row["bank_stmt_id"]].index[0]
            df_oct.loc[b_idx, "bank_disposition"] = BankDisposition.UNMATCHED_BANK_CREDIT.value

    # Unconsumed clean October bank debits -> ORPHAN_BANK_DEBIT
    for _, bank_row in clean_debits.iterrows():
        utr = bank_row["bank_utr_number"]
        if utr not in consumed_oct_debit_utrs:
            b_idx = df_oct[df_oct["bank_stmt_id"] == bank_row["bank_stmt_id"]].index[0]
            df_oct.loc[b_idx, "bank_disposition"] = BankDisposition.ORPHAN_BANK_DEBIT.value

    # -------------------------------------------------------------
    # 5. Month-End Temporal Window Aging at October Cutoff (Stage 1)
    # -------------------------------------------------------------
    unmatched_int_payments = df_int[
        (df_int["txn_type"] == "PAYMENT") & (df_int["internal_disposition"].isna())
    ].copy()

    for idx, row in unmatched_int_payments.iterrows():
        txn_date_str = row["date_str"]
        bus_days = calculate_business_days(txn_date_str, "2026-10-31")
        
        if bus_days <= SLA_BUSINESS_DAYS:
            # Within 3 business days SLA at October cutoff -> In-Transit
            df_int.loc[idx, "october_snapshot_status"] = "PENDING_SETTLEMENT_AT_OCT_CUTOFF"
        else:
            # Stale payment (>3 business days) -> Overdue break
            df_int.loc[idx, "october_snapshot_status"] = InternalDisposition.OVERDUE_UNSETTLED_BREAK.value
            df_int.loc[idx, "internal_disposition"] = InternalDisposition.OVERDUE_UNSETTLED_BREAK.value

    # -------------------------------------------------------------
    # 6. November Subsequent Clearing Verification (Stage 2)
    # -------------------------------------------------------------
    nov_credit_dict = {
        row["bank_utr_number"]: row for _, row in df_nov.iterrows()
    }
    consumed_nov_utrs = set()

    pending_at_cutoff = df_int[df_int["october_snapshot_status"] == "PENDING_SETTLEMENT_AT_OCT_CUTOFF"].copy()

    for idx, row in pending_at_cutoff.iterrows():
        utr = row["utr_number"]
        amt = row["amount_paise"]

        if utr in nov_credit_dict:
            nov_bank_row = nov_credit_dict[utr]
            gross = nov_bank_row["gross_amount_paise"]
            delta = amt - gross

            df_int.loc[idx, "delta_paise"] = delta
            df_int.loc[idx, "matched_bank_stmt_id"] = nov_bank_row["bank_stmt_id"]
            df_int.loc[idx, "matched_settlement_date"] = nov_bank_row["settlement_date"]
            df_int.loc[idx, "matched_bank_gross_paise"] = gross
            df_int.loc[idx, "matched_bank_fee_paise"] = nov_bank_row["fee_paise"]
            df_int.loc[idx, "internal_disposition"] = InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value

            nov_idx = df_nov[df_nov["bank_stmt_id"] == nov_bank_row["bank_stmt_id"]].index[0]
            df_nov.loc[nov_idx, "bank_disposition"] = BankDisposition.BANK_CONFIRMED_LATE_CREDIT.value
            df_nov.loc[nov_idx, "matched_internal_txn_id"] = row["internal_txn_id"]
            consumed_nov_utrs.add(utr)
        else:
            # Absent from November statement as well -> Overdue Break
            df_int.loc[idx, "internal_disposition"] = InternalDisposition.OVERDUE_UNSETTLED_BREAK.value

    # Any unconsumed in Nov gets fallback
    for idx, row in df_nov.iterrows():
        if df_nov.loc[idx, "bank_disposition"] is None:
            df_nov.loc[idx, "bank_disposition"] = "BANK_NOV_UNMATCHED_CREDIT"

    # -------------------------------------------------------------
    # 7. Attach Explainability & Audit Narratives
    # -------------------------------------------------------------
    df_int["explanation_reason"] = ""
    df_int["explanation_action"] = ""
    df_int["discrepancy_category"] = ""

    for idx, row in df_int.iterrows():
        disp = row["internal_disposition"]
        delta = row["delta_paise"]
        settle_date = row["matched_settlement_date"]
        parent_id = row["parent_txn_id"]
        exp = get_explanation(disp, delta_paise=delta, settle_date=settle_date, parent_id=parent_id)
        df_int.loc[idx, "explanation_reason"] = exp["reason"]
        df_int.loc[idx, "explanation_action"] = exp["action"]
        df_int.loc[idx, "discrepancy_category"] = exp["category"]

    df_oct["bank_explanation_reason"] = ""
    df_oct["bank_explanation_action"] = ""
    df_oct["bank_category"] = ""

    for idx, row in df_oct.iterrows():
        b_disp = row["bank_disposition"]
        b_exp = get_explanation(b_disp)
        df_oct.loc[idx, "bank_explanation_reason"] = b_exp["reason"]
        df_oct.loc[idx, "bank_explanation_action"] = b_exp["action"]
        df_oct.loc[idx, "bank_category"] = b_exp["category"]

    # -------------------------------------------------------------
    # 8. Compute Master Summary & Financial Metrics
    # -------------------------------------------------------------
    int_payments_all = df_int[df_int["txn_type"] == "PAYMENT"]
    int_refunds_all = df_int[df_int["txn_type"] == "REFUND"]

    total_internal_authorized_gross_paise = int(int_payments_all["amount_paise"].sum())
    total_internal_refunds_paise = int(int_refunds_all["amount_paise"].sum())
    total_internal_authorized_net_paise = total_internal_authorized_gross_paise - total_internal_refunds_paise

    oct_credits_all = df_oct[df_oct["posting_type"] == "CREDIT"]
    oct_debits_all = df_oct[df_oct["posting_type"] == "DEBIT"]

    total_bank_oct_gross_credits_paise = int(oct_credits_all["gross_amount_paise"].sum())
    total_bank_oct_gross_debits_paise = int(oct_debits_all["gross_amount_paise"].sum())
    total_bank_oct_gross_net_paise = total_bank_oct_gross_credits_paise - total_bank_oct_gross_debits_paise

    total_bank_oct_fees_paise = int(df_oct["fee_paise"].sum())
    total_bank_oct_cash_posted_paise = total_bank_oct_gross_net_paise - total_bank_oct_fees_paise

    # Discrepancy & In-Transit terms
    in_transit_paise = int(df_int[df_int["internal_disposition"] == InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value]["amount_paise"].sum())
    
    rounding_rows = df_int[df_int["internal_disposition"] == InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value]
    net_rounding_drift_paise = int(rounding_rows["delta_paise"].sum())

    overdue_breaks_paise = int(df_int[df_int["internal_disposition"] == InternalDisposition.OVERDUE_UNSETTLED_BREAK.value]["amount_paise"].sum())

    # Quarantine variance:
    # 1. Internal duplicate variance: internal has duplicates, bank has 1 credit
    int_dups = df_int[df_int["internal_disposition"] == InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value]
    bank_held_for_int_dup = df_oct[df_oct["bank_disposition"] == BankDisposition.BANK_HELD_FOR_INTERNAL_DUPLICATE.value]
    int_dup_variance_paise = int(int_dups["amount_paise"].sum()) - int(bank_held_for_int_dup["gross_amount_paise"].sum())

    # 2. Bank duplicate variance: bank has duplicate credits, internal has 1 payment
    bank_dups = df_oct[df_oct["bank_disposition"] == BankDisposition.SUSPECTED_DUPLICATE_BANK.value]
    int_held_for_bank_dup = df_int[df_int["internal_disposition"] == InternalDisposition.INTERNAL_HELD_FOR_BANK_DUPLICATE.value]
    bank_dup_variance_paise = int(bank_dups["gross_amount_paise"].sum()) - int(int_held_for_bank_dup["amount_paise"].sum())

    unmatched_bank_credits_paise = int(df_oct[df_oct["bank_disposition"] == BankDisposition.UNMATCHED_BANK_CREDIT.value]["gross_amount_paise"].sum())
    orphan_bank_debits_paise = int(df_oct[df_oct["bank_disposition"] == BankDisposition.ORPHAN_BANK_DEBIT.value]["gross_amount_paise"].sum())

    # Reconciled count
    reconciled_disps = [
        InternalDisposition.FULLY_RECONCILED.value,
        InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value,
        InternalDisposition.FULLY_RECONCILED_REFUND.value,
        InternalDisposition.RECONCILED_REFUND_MISSING_PARENT.value,
        InternalDisposition.RECONCILED_REFUND_UNRESOLVED_PARENT.value,
    ]
    reconciled_internal_count = int(df_int["internal_disposition"].isin(reconciled_disps).sum())
    reconciled_rate_pct = round((reconciled_internal_count / len(df_int)) * 100.0, 2) if len(df_int) > 0 else 0.0

    # Master Reconciliation Balance Equation Check:
    # Net_internal - In_Transit - Rounding_Drift - Overdue_Breaks - Int_Dup_Variance + Bank_Dup_Variance + Unmatched_Bank_Credits - Orphan_Bank_Debits == Gross_bank_oct
    calculated_bank_oct_gross_paise = (
        total_internal_authorized_net_paise
        - in_transit_paise
        - net_rounding_drift_paise
        - overdue_breaks_paise
        - int_dup_variance_paise
        + bank_dup_variance_paise
        + unmatched_bank_credits_paise
        - orphan_bank_debits_paise
    )
    balance_residual_paise = calculated_bank_oct_gross_paise - total_bank_oct_gross_net_paise

    summary_metrics = {
        "total_internal_records": len(df_int),
        "total_bank_oct_records": len(df_oct),
        "total_bank_nov_records": len(df_nov),
        "reconciled_internal_count": reconciled_internal_count,
        "reconciled_rate_pct": reconciled_rate_pct,
        "total_internal_authorized_gross_paise": total_internal_authorized_gross_paise,
        "total_internal_refunds_paise": total_internal_refunds_paise,
        "total_internal_authorized_net_paise": total_internal_authorized_net_paise,
        "total_bank_oct_gross_net_paise": total_bank_oct_gross_net_paise,
        "total_bank_oct_fees_paise": total_bank_oct_fees_paise,
        "total_bank_oct_cash_posted_paise": total_bank_oct_cash_posted_paise,
        "in_transit_paise": in_transit_paise,
        "net_rounding_drift_paise": net_rounding_drift_paise,
        "overdue_breaks_paise": overdue_breaks_paise,
        "int_dup_variance_paise": int_dup_variance_paise,
        "bank_dup_variance_paise": bank_dup_variance_paise,
        "unmatched_bank_credits_paise": unmatched_bank_credits_paise,
        "orphan_bank_debits_paise": orphan_bank_debits_paise,
        "calculated_bank_oct_gross_paise": calculated_bank_oct_gross_paise,
        "balance_residual_paise": balance_residual_paise,
        "is_master_balanced": (balance_residual_paise == 0),
    }

    return df_int, df_oct, df_nov, summary_metrics
