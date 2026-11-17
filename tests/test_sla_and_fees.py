"""Tests for SLA Date Arithmetic (Weekends/Holidays) and Fee Invariants (TC-17 to TC-19)."""

import pytest
import pandas as pd
from src.engine.normalizer import calculate_business_days
from src.models import BankSettlement, PostingType


# -------------------------------------------------------------
# TC-17: Weekend and Holiday SLA Business Day Calculation
# -------------------------------------------------------------
def test_tc17_weekend_and_holiday_sla_calculation():
    # 1. Friday to Tuesday over regular weekend:
    # Oct 23, 2026 (Friday) to Oct 27, 2026 (Tuesday)
    # Business days should be exactly 2 (Monday Oct 26 and Tuesday Oct 27)
    bus_days_weekend = calculate_business_days("2026-10-23", "2026-10-27")
    assert bus_days_weekend == 2, f"Expected 2 business days over weekend, got {bus_days_weekend}"

    # 2. Thursday to Monday over Gandhi Jayanti holiday (Oct 02, Friday):
    # Oct 01, 2026 (Thursday) to Oct 05, 2026 (Monday)
    # Friday Oct 02 is a national holiday, Oct 03-04 is weekend.
    # Business days between Oct 01 and Oct 05 should be 1 (only Monday Oct 05).
    bus_days_holiday = calculate_business_days("2026-10-01", "2026-10-05")
    assert bus_days_holiday == 1, f"Expected 1 business day with holiday, got {bus_days_holiday}"


# -------------------------------------------------------------
# TC-18: Bank Credit Fee Invariant (gross - fee == net)
# -------------------------------------------------------------
def test_tc18_bank_credit_fee_invariant():
    valid_credit = BankSettlement(
        bank_stmt_id="STMT_TEST_CREDIT_OK",
        bank_utr_number="430518000018",
        settlement_date="2026-10-15",
        posting_type=PostingType.CREDIT,
        gross_amount_paise=100000,
        gross_amount_inr="₹1,000.00",
        fee_paise=180,
        net_amount_paise=99820,  # 100000 - 180 = 99820
        narration="UPI-FEE-CHECK",
    )
    assert valid_credit.net_amount_paise == valid_credit.gross_amount_paise - valid_credit.fee_paise

    # Expect validation failure when net != gross - fee
    with pytest.raises(ValueError):
        BankSettlement(
            bank_stmt_id="STMT_TEST_CREDIT_FAIL",
            bank_utr_number="430518000018_BAD",
            settlement_date="2026-10-15",
            posting_type=PostingType.CREDIT,
            gross_amount_paise=100000,
            gross_amount_inr="₹1,000.00",
            fee_paise=180,
            net_amount_paise=100000,  # Invalid: did not subtract fee
            narration="BAD-NET",
        )


# -------------------------------------------------------------
# TC-19: Bank Debit Fee Invariant (gross + fee == net)
# -------------------------------------------------------------
def test_tc19_bank_debit_fee_invariant():
    valid_debit = BankSettlement(
        bank_stmt_id="STMT_TEST_DEBIT_OK",
        bank_utr_number="REF_430518000019",
        settlement_date="2026-10-18",
        posting_type=PostingType.DEBIT,
        gross_amount_paise=50000,
        gross_amount_inr="₹500.00",
        fee_paise=50,
        net_amount_paise=50050,  # 50000 + 50 = 50050
        narration="REFUND-DEBIT-CHECK",
    )
    assert valid_debit.net_amount_paise == valid_debit.gross_amount_paise + valid_debit.fee_paise

    # Expect validation failure when net != gross + fee for DEBIT
    with pytest.raises(ValueError):
        BankSettlement(
            bank_stmt_id="STMT_TEST_DEBIT_FAIL",
            bank_utr_number="REF_430518000019_BAD",
            settlement_date="2026-10-18",
            posting_type=PostingType.DEBIT,
            gross_amount_paise=50000,
            gross_amount_inr="₹500.00",
            fee_paise=50,
            net_amount_paise=49950,  # Invalid: subtracted fee instead of adding
            narration="BAD-DEBIT",
        )
