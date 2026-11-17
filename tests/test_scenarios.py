"""Unit Tests for Test Cases TC-01 to TC-16 (Mandatory Scenarios and Discrepancies)."""

import pytest
import pandas as pd
from src.engine.matcher import reconcile_datasets
from src.models import InternalDisposition, BankDisposition


def build_single_txn_pipeline(internal_row: dict, bank_oct_row: dict = None, bank_nov_row: dict = None):
    """Helper to run miniature single-record reconciliation pipelines."""
    df_int = pd.DataFrame([internal_row]) if internal_row else pd.DataFrame(columns=[
        "internal_txn_id", "utr_number", "timestamp", "customer_id", "payment_rail",
        "txn_type", "amount_paise", "amount_inr", "status", "parent_txn_id"
    ])
    
    df_oct = pd.DataFrame([bank_oct_row]) if bank_oct_row else pd.DataFrame(columns=[
        "bank_stmt_id", "bank_utr_number", "settlement_date", "posting_type",
        "gross_amount_paise", "gross_amount_inr", "fee_paise", "net_amount_paise", "narration"
    ])
    
    df_nov = pd.DataFrame([bank_nov_row]) if bank_nov_row else pd.DataFrame(columns=[
        "bank_stmt_id", "bank_utr_number", "settlement_date", "posting_type",
        "gross_amount_paise", "gross_amount_inr", "fee_paise", "net_amount_paise", "narration"
    ])
    
    return reconcile_datasets(df_int, df_oct, df_nov)


# -------------------------------------------------------------
# TC-01: Standard UPI Exact Match
# -------------------------------------------------------------
def test_tc01_clean_upi_exact_match():
    int_row = {
        "internal_txn_id": "TXN_TEST_01",
        "utr_number": "430518000001",
        "timestamp": "2026-10-10T10:00:00+05:30",
        "customer_id": "CUST_01",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 50000,
        "amount_inr": "₹500.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_row = {
        "bank_stmt_id": "STMT_OCT_01",
        "bank_utr_number": "430518000001",
        "settlement_date": "2026-10-11",
        "posting_type": "CREDIT",
        "gross_amount_paise": 50000,
        "gross_amount_inr": "₹500.00",
        "fee_paise": 50,
        "net_amount_paise": 49950,
        "narration": "UPI-430518000001",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(int_row, oct_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.FULLY_RECONCILED.value
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.BANK_RECONCILED_CREDIT.value
    assert res_int.loc[0, "delta_paise"] == 0


# -------------------------------------------------------------
# TC-02: Clean High-Value NEFT Exact Match
# -------------------------------------------------------------
def test_tc02_clean_neft_high_value():
    int_row = {
        "internal_txn_id": "TXN_TEST_02",
        "utr_number": "N10226000002",
        "timestamp": "2026-10-15T11:00:00+05:30",
        "customer_id": "CUST_02",
        "payment_rail": "NEFT",
        "txn_type": "PAYMENT",
        "amount_paise": 15000000,  # ₹1,50,000.00
        "amount_inr": "₹1,50,000.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_row = {
        "bank_stmt_id": "STMT_OCT_02",
        "bank_utr_number": "N10226000002",
        "settlement_date": "2026-10-16",
        "posting_type": "CREDIT",
        "gross_amount_paise": 15000000,
        "gross_amount_inr": "₹1,50,000.00",
        "fee_paise": 500,
        "net_amount_paise": 14999500,
        "narration": "NEFT-N10226000002",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(int_row, oct_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.FULLY_RECONCILED.value
    assert res_int.loc[0, "delta_paise"] == 0


# -------------------------------------------------------------
# TC-03: Rounding Drift Under Tolerance (+4 paise)
# -------------------------------------------------------------
def test_tc03_rounding_drift_positive():
    int_row = {
        "internal_txn_id": "TXN_TEST_03",
        "utr_number": "430518000003",
        "timestamp": "2026-10-18T12:00:00+05:30",
        "customer_id": "CUST_03",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 100000,
        "amount_inr": "₹1,000.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_row = {
        "bank_stmt_id": "STMT_OCT_03",
        "bank_utr_number": "430518000003",
        "settlement_date": "2026-10-19",
        "posting_type": "CREDIT",
        "gross_amount_paise": 100004,  # +4 paise
        "gross_amount_inr": "₹1,000.04",
        "fee_paise": 100,
        "net_amount_paise": 99904,
        "narration": "UPI-430518000003",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(int_row, oct_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.BANK_RECONCILED_CREDIT.value
    assert res_int.loc[0, "delta_paise"] == -4


# -------------------------------------------------------------
# TC-04: Rounding Drift Under Tolerance (-7 paise)
# -------------------------------------------------------------
def test_tc04_rounding_drift_negative():
    int_row = {
        "internal_txn_id": "TXN_TEST_04",
        "utr_number": "430518000004",
        "timestamp": "2026-10-20T14:00:00+05:30",
        "customer_id": "CUST_04",
        "payment_rail": "CARD",
        "txn_type": "PAYMENT",
        "amount_paise": 249900,
        "amount_inr": "₹2,499.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_row = {
        "bank_stmt_id": "STMT_OCT_04",
        "bank_utr_number": "430518000004",
        "settlement_date": "2026-10-21",
        "posting_type": "CREDIT",
        "gross_amount_paise": 249893,  # -7 paise
        "gross_amount_inr": "₹2,498.93",
        "fee_paise": 200,
        "net_amount_paise": 249693,
        "narration": "CARD-430518000004",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(int_row, oct_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value
    assert res_int.loc[0, "delta_paise"] == 7


# -------------------------------------------------------------
# TC-05: Amount Discrepancy Exceeding Tolerance (>10 paise)
# -------------------------------------------------------------
def test_tc05_amount_mismatch_break():
    int_row = {
        "internal_txn_id": "TXN_TEST_05",
        "utr_number": "430518000005",
        "timestamp": "2026-10-22T15:00:00+05:30",
        "customer_id": "CUST_05",
        "payment_rail": "IMPS",
        "txn_type": "PAYMENT",
        "amount_paise": 500000,  # ₹5,000.00
        "amount_inr": "₹5,000.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_row = {
        "bank_stmt_id": "STMT_OCT_05",
        "bank_utr_number": "430518000005",
        "settlement_date": "2026-10-23",
        "posting_type": "CREDIT",
        "gross_amount_paise": 485000,  # ₹4,850.00 (₹150 break)
        "gross_amount_inr": "₹4,850.00",
        "fee_paise": 500,
        "net_amount_paise": 484500,
        "narration": "IMPS-430518000005",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(int_row, oct_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.AMOUNT_MISMATCH_BREAK.value
    assert res_int.loc[0, "delta_paise"] == 15000


# -------------------------------------------------------------
# TC-06: Month-End UPI Pending at Oct 31, Confirmed Nov 02
# -------------------------------------------------------------
def test_tc06_confirmed_late_settlement_nov():
    int_row = {
        "internal_txn_id": "TXN_TEST_06",
        "utr_number": "430518000006",
        "timestamp": "2026-10-30T18:00:00+05:30",
        "customer_id": "CUST_06",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 125000,
        "amount_inr": "₹1,250.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    nov_row = {
        "bank_stmt_id": "STMT_NOV_01",
        "bank_utr_number": "430518000006",
        "settlement_date": "2026-11-02",
        "posting_type": "CREDIT",
        "gross_amount_paise": 125000,
        "gross_amount_inr": "₹1,250.00",
        "fee_paise": 100,
        "net_amount_paise": 124900,
        "narration": "UPI-SETTL-LATE",
    }
    res_int, _, res_nov, _ = build_single_txn_pipeline(int_row, bank_oct_row=None, bank_nov_row=nov_row)
    assert res_int.loc[0, "october_snapshot_status"] == "PENDING_SETTLEMENT_AT_OCT_CUTOFF"
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value
    assert res_nov.loc[0, "bank_disposition"] == BankDisposition.BANK_CONFIRMED_LATE_CREDIT.value


# -------------------------------------------------------------
# TC-07: Month-End Card Settlement Confirmed Nov 03
# -------------------------------------------------------------
def test_tc07_confirmed_late_card_t_plus_2():
    int_row = {
        "internal_txn_id": "TXN_TEST_07",
        "utr_number": "745210000007",
        "timestamp": "2026-10-31T22:30:00+05:30",
        "customer_id": "CUST_07",
        "payment_rail": "CARD",
        "txn_type": "PAYMENT",
        "amount_paise": 399900,
        "amount_inr": "₹3,999.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    nov_row = {
        "bank_stmt_id": "STMT_NOV_02",
        "bank_utr_number": "745210000007",
        "settlement_date": "2026-11-03",
        "posting_type": "CREDIT",
        "gross_amount_paise": 399900,
        "gross_amount_inr": "₹3,999.00",
        "fee_paise": 400,
        "net_amount_paise": 399500,
        "narration": "CARD-SETTL-LATE",
    }
    res_int, _, res_nov, _ = build_single_txn_pipeline(int_row, bank_oct_row=None, bank_nov_row=nov_row)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value


# -------------------------------------------------------------
# TC-08: Month-End Payment Overdue / Unsettled (Oct 30, not in Nov)
# -------------------------------------------------------------
def test_tc08_month_end_overdue_unsettled():
    int_row = {
        "internal_txn_id": "TXN_TEST_08",
        "utr_number": "430518000008",
        "timestamp": "2026-10-30T11:00:00+05:30",
        "customer_id": "CUST_08",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 85000,
        "amount_inr": "₹850.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    res_int, _, _, _ = build_single_txn_pipeline(int_row, bank_oct_row=None, bank_nov_row=None)
    # Stage 1: Marked pending at cutoff
    assert res_int.loc[0, "october_snapshot_status"] == "PENDING_SETTLEMENT_AT_OCT_CUTOFF"
    # Stage 2: Converted to overdue break because not in November file
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.OVERDUE_UNSETTLED_BREAK.value


# -------------------------------------------------------------
# TC-09: Mid-Month Stale Payment (Oct 05, >3 business days)
# -------------------------------------------------------------
def test_tc09_stale_mid_month_unsettled_break():
    int_row = {
        "internal_txn_id": "TXN_TEST_09",
        "utr_number": "430518000009",
        "timestamp": "2026-10-05T10:00:00+05:30",
        "customer_id": "CUST_09",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 210000,
        "amount_inr": "₹2,100.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    res_int, _, _, _ = build_single_txn_pipeline(int_row, bank_oct_row=None, bank_nov_row=None)
    assert res_int.loc[0, "october_snapshot_status"] == InternalDisposition.OVERDUE_UNSETTLED_BREAK.value
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.OVERDUE_UNSETTLED_BREAK.value


# -------------------------------------------------------------
# TC-10: Suspected Duplicate Internal & Bank Counterpart Held
# -------------------------------------------------------------
def test_tc10_suspected_duplicate_internal_and_bank_held():
    int_rows = [
        {
            "internal_txn_id": "TXN_TEST_10_A",
            "utr_number": "430518000010",
            "timestamp": "2026-10-12T10:00:00+05:30",
            "customer_id": "CUST_10",
            "payment_rail": "UPI",
            "txn_type": "PAYMENT",
            "amount_paise": 75000,
            "amount_inr": "₹750.00",
            "status": "SUCCESS",
            "parent_txn_id": None,
        },
        {
            "internal_txn_id": "TXN_TEST_10_B",
            "utr_number": "430518000010",
            "timestamp": "2026-10-12T10:00:02+05:30",
            "customer_id": "CUST_10",
            "payment_rail": "UPI",
            "txn_type": "PAYMENT",
            "amount_paise": 75000,
            "amount_inr": "₹750.00",
            "status": "SUCCESS",
            "parent_txn_id": None,
        },
    ]
    oct_row = {
        "bank_stmt_id": "STMT_OCT_10",
        "bank_utr_number": "430518000010",
        "settlement_date": "2026-10-13",
        "posting_type": "CREDIT",
        "gross_amount_paise": 75000,
        "gross_amount_inr": "₹750.00",
        "fee_paise": 50,
        "net_amount_paise": 74950,
        "narration": "UPI-430518000010",
    }
    df_int = pd.DataFrame(int_rows)
    df_oct = pd.DataFrame([oct_row])
    df_nov = pd.DataFrame(columns=["bank_stmt_id", "bank_utr_number", "settlement_date", "posting_type", "gross_amount_paise", "gross_amount_inr", "fee_paise", "net_amount_paise", "narration"])
    
    res_int, res_oct, _, _ = reconcile_datasets(df_int, df_oct, df_nov)
    assert (res_int["internal_disposition"] == InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value).all()
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.BANK_HELD_FOR_INTERNAL_DUPLICATE.value


# -------------------------------------------------------------
# TC-11: Suspected Duplicate Bank & Internal Counterpart Held
# -------------------------------------------------------------
def test_tc11_suspected_duplicate_bank_and_internal_held():
    int_row = {
        "internal_txn_id": "TXN_TEST_11",
        "utr_number": "430518000011",
        "timestamp": "2026-10-14T10:00:00+05:30",
        "customer_id": "CUST_11",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 110000,
        "amount_inr": "₹1,100.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    oct_rows = [
        {
            "bank_stmt_id": "STMT_OCT_11_A",
            "bank_utr_number": "430518000011",
            "settlement_date": "2026-10-15",
            "posting_type": "CREDIT",
            "gross_amount_paise": 110000,
            "gross_amount_inr": "₹1,100.00",
            "fee_paise": 100,
            "net_amount_paise": 109900,
            "narration": "BATCH-1",
        },
        {
            "bank_stmt_id": "STMT_OCT_11_B",
            "bank_utr_number": "430518000011",
            "settlement_date": "2026-10-15",
            "posting_type": "CREDIT",
            "gross_amount_paise": 110000,
            "gross_amount_inr": "₹1,100.00",
            "fee_paise": 100,
            "net_amount_paise": 109900,
            "narration": "BATCH-2",
        },
    ]
    df_int = pd.DataFrame([int_row])
    df_oct = pd.DataFrame(oct_rows)
    df_nov = pd.DataFrame(columns=["bank_stmt_id", "bank_utr_number", "settlement_date", "posting_type", "gross_amount_paise", "gross_amount_inr", "fee_paise", "net_amount_paise", "narration"])
    
    res_int, res_oct, _, _ = reconcile_datasets(df_int, df_oct, df_nov)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.INTERNAL_HELD_FOR_BANK_DUPLICATE.value
    assert (res_oct["bank_disposition"] == BankDisposition.SUSPECTED_DUPLICATE_BANK.value).all()


# -------------------------------------------------------------
# TC-12: Valid Linked Refund with Settled Parent
# -------------------------------------------------------------
def test_tc12_valid_linked_refund_with_settled_parent():
    parent_payment = {
        "internal_txn_id": "TXN_OCT_PARENT_12",
        "utr_number": "430518000012_PARENT",
        "timestamp": "2026-10-10T10:00:00+05:30",
        "customer_id": "CUST_12",
        "payment_rail": "UPI",
        "txn_type": "PAYMENT",
        "amount_paise": 200000,
        "amount_inr": "₹2,000.00",
        "status": "SUCCESS",
        "parent_txn_id": None,
    }
    parent_stmt = {
        "bank_stmt_id": "STMT_PARENT_12",
        "bank_utr_number": "430518000012_PARENT",
        "settlement_date": "2026-10-11",
        "posting_type": "CREDIT",
        "gross_amount_paise": 200000,
        "gross_amount_inr": "₹2,000.00",
        "fee_paise": 100,
        "net_amount_paise": 199900,
        "narration": "PARENT-CREDIT",
    }
    refund_txn = {
        "internal_txn_id": "TXN_OCT_REFUND_12",
        "utr_number": "REF_430518000012",
        "timestamp": "2026-10-20T10:00:00+05:30",
        "customer_id": "CUST_12",
        "payment_rail": "UPI",
        "txn_type": "REFUND",
        "amount_paise": 40000,
        "amount_inr": "₹400.00",
        "status": "SUCCESS",
        "parent_txn_id": "TXN_OCT_PARENT_12",
    }
    refund_stmt = {
        "bank_stmt_id": "STMT_REFUND_12",
        "bank_utr_number": "REF_430518000012",
        "settlement_date": "2026-10-21",
        "posting_type": "DEBIT",
        "gross_amount_paise": 40000,
        "gross_amount_inr": "₹400.00",
        "fee_paise": 50,
        "net_amount_paise": 40050,
        "narration": "REFUND-DEBIT",
    }
    df_int = pd.DataFrame([parent_payment, refund_txn])
    df_oct = pd.DataFrame([parent_stmt, refund_stmt])
    df_nov = pd.DataFrame(columns=["bank_stmt_id", "bank_utr_number", "settlement_date", "posting_type", "gross_amount_paise", "gross_amount_inr", "fee_paise", "net_amount_paise", "narration"])
    
    res_int, res_oct, _, _ = reconcile_datasets(df_int, df_oct, df_nov)
    ref_int = res_int[res_int["txn_type"] == "REFUND"].iloc[0]
    ref_oct = res_oct[res_oct["posting_type"] == "DEBIT"].iloc[0]
    assert ref_int["internal_disposition"] == InternalDisposition.FULLY_RECONCILED_REFUND.value
    assert ref_oct["bank_disposition"] == BankDisposition.BANK_RECONCILED_DEBIT.value


# -------------------------------------------------------------
# TC-13: Refund Missing Parent Reference (NULL) Reconciled
# -------------------------------------------------------------
def test_tc13_refund_missing_parent_reference_reconciled():
    refund_txn = {
        "internal_txn_id": "TXN_OCT_REFUND_13",
        "utr_number": "REF_430518000013",
        "timestamp": "2026-10-26T10:00:00+05:30",
        "customer_id": "CUST_13",
        "payment_rail": "IMPS",
        "txn_type": "REFUND",
        "amount_paise": 60000,
        "amount_inr": "₹600.00",
        "status": "SUCCESS",
        "parent_txn_id": None,  # Missing
    }
    refund_stmt = {
        "bank_stmt_id": "STMT_REFUND_13",
        "bank_utr_number": "REF_430518000013",
        "settlement_date": "2026-10-27",
        "posting_type": "DEBIT",
        "gross_amount_paise": 60000,
        "gross_amount_inr": "₹600.00",
        "fee_paise": 50,
        "net_amount_paise": 60050,
        "narration": "REFUND-DEBIT",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(refund_txn, refund_stmt)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.RECONCILED_REFUND_MISSING_PARENT.value
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.BANK_RECONCILED_DEBIT.value


# -------------------------------------------------------------
# TC-14: Refund Unresolved Parent Reference Reconciled
# -------------------------------------------------------------
def test_tc14_refund_unresolved_parent_reference_reconciled():
    refund_txn = {
        "internal_txn_id": "TXN_OCT_REFUND_14",
        "utr_number": "REF_430518000014",
        "timestamp": "2026-10-27T10:00:00+05:30",
        "customer_id": "CUST_14",
        "payment_rail": "IMPS",
        "txn_type": "REFUND",
        "amount_paise": 35000,
        "amount_inr": "₹350.00",
        "status": "SUCCESS",
        "parent_txn_id": "TXN_NONEXISTENT_PARENT",  # Unresolved
    }
    refund_stmt = {
        "bank_stmt_id": "STMT_REFUND_14",
        "bank_utr_number": "REF_430518000014",
        "settlement_date": "2026-10-28",
        "posting_type": "DEBIT",
        "gross_amount_paise": 35000,
        "gross_amount_inr": "₹350.00",
        "fee_paise": 50,
        "net_amount_paise": 35050,
        "narration": "REFUND-DEBIT",
    }
    res_int, res_oct, _, _ = build_single_txn_pipeline(refund_txn, refund_stmt)
    assert res_int.loc[0, "internal_disposition"] == InternalDisposition.RECONCILED_REFUND_UNRESOLVED_PARENT.value
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.BANK_RECONCILED_DEBIT.value


# -------------------------------------------------------------
# TC-15: Direct Bank Deposit / Unmatched Bank Credit
# -------------------------------------------------------------
def test_tc15_unmatched_bank_credit_direct_deposit():
    oct_row = {
        "bank_stmt_id": "STMT_OCT_15",
        "bank_utr_number": "SURPLUS_15",
        "settlement_date": "2026-10-28",
        "posting_type": "CREDIT",
        "gross_amount_paise": 1000000,  # ₹10,000.00
        "gross_amount_inr": "₹10,000.00",
        "fee_paise": 0,
        "net_amount_paise": 1000000,
        "narration": "DIRECT-DEPOSIT",
    }
    _, res_oct, _, _ = build_single_txn_pipeline(None, oct_row)
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.UNMATCHED_BANK_CREDIT.value


# -------------------------------------------------------------
# TC-16: Orphan Bank Debit
# -------------------------------------------------------------
def test_tc16_orphan_bank_debit():
    oct_row = {
        "bank_stmt_id": "STMT_OCT_16",
        "bank_utr_number": "ORPHAN_16",
        "settlement_date": "2026-10-28",
        "posting_type": "DEBIT",
        "gross_amount_paise": 25000,  # ₹250.00
        "gross_amount_inr": "₹250.00",
        "fee_paise": 50,
        "net_amount_paise": 25050,
        "narration": "CHARGEBACK-ORPHAN",
    }
    _, res_oct, _, _ = build_single_txn_pipeline(None, oct_row)
    assert res_oct.loc[0, "bank_disposition"] == BankDisposition.ORPHAN_BANK_DEBIT.value
