"""Tests for Conservation Invariants and Full System Balance (TC-20)."""

import pytest
from src.engine.matcher import reconcile_datasets
from src.engine.invariants import verify_all_invariants
from src.models import InternalDisposition, BankDisposition


# -------------------------------------------------------------
# TC-20: Full Invariant Assertion on 1,000 Internal Records
# -------------------------------------------------------------
def test_tc20_full_dataset_invariants_and_zero_residual(generated_datasets):
    df_int_raw, df_oct_raw, df_nov_raw = generated_datasets

    # Run complete reconciliation engine
    df_int, df_oct, df_nov, metrics = reconcile_datasets(df_int_raw, df_oct_raw, df_nov_raw)
    inv = verify_all_invariants(df_int, df_oct, df_nov, metrics)

    # 1. Total row count conservation
    assert len(df_int) == 1000, "Internal count must be exactly 1,000"
    assert len(df_oct) == 945, "October bank count must be exactly 945"
    assert len(df_nov) == 45, "November bank count must be exactly 45"

    assert inv["internal_count_conserved"] is True
    assert inv["oct_bank_count_conserved"] is True
    assert inv["nov_bank_count_conserved"] is True

    # 2. Bank fee invariants
    assert inv["bank_fee_invariants_hold"] is True

    # 3. Master monetary value conservation (0 paise residual)
    assert metrics["is_master_balanced"] is True
    assert metrics["balance_residual_paise"] == 0
    assert inv["master_monetary_balanced"] is True
    assert inv["all_passed"] is True

    # 4. Verify all 4 mandatory scenarios are represented
    # Scenario 1: Late Settlements
    late_count = (df_int["internal_disposition"] == InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value).sum()
    assert late_count == 45, f"Expected 45 confirmed late settlements, got {late_count}"

    # Scenario 2: Rounding Differences
    rounding_count = (df_int["internal_disposition"] == InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value).sum()
    assert rounding_count == 40, f"Expected 40 rounding difference records, got {rounding_count}"

    # Scenario 3: Duplicate Entries
    int_dups = (df_int["internal_disposition"] == InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value).sum()
    bank_dups = (df_oct["bank_disposition"] == BankDisposition.SUSPECTED_DUPLICATE_BANK.value).sum()
    assert int_dups == 30, f"Expected 30 internal duplicate records, got {int_dups}"
    assert bank_dups == 20, f"Expected 20 bank duplicate records, got {bank_dups}"

    # Scenario 4: Orphan / Lineage Refunds
    orphan_bank_debits = (df_oct["bank_disposition"] == BankDisposition.ORPHAN_BANK_DEBIT.value).sum()
    missing_parent_refunds = (df_int["internal_disposition"] == InternalDisposition.RECONCILED_REFUND_MISSING_PARENT.value).sum()
    unresolved_parent_refunds = (df_int["internal_disposition"] == InternalDisposition.RECONCILED_REFUND_UNRESOLVED_PARENT.value).sum()
    assert orphan_bank_debits == 15, f"Expected 15 orphan bank debits, got {orphan_bank_debits}"
    assert missing_parent_refunds == 8, f"Expected 8 refunds with missing parent, got {missing_parent_refunds}"
    assert unresolved_parent_refunds == 7, f"Expected 7 refunds with unresolved parent, got {unresolved_parent_refunds}"
