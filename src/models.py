"""Domain Data Models, Enums, and Schema Definitions."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class PostingType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class PaymentRail(str, Enum):
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    CARD = "CARD"


class GatewayStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class InternalDisposition(str, Enum):
    """Mutually exclusive terminal dispositions for internal transactions."""
    FULLY_RECONCILED = "FULLY_RECONCILED"
    RECONCILED_ROUNDING_VARIANCE = "RECONCILED_ROUNDING_VARIANCE"
    AMOUNT_MISMATCH_BREAK = "AMOUNT_MISMATCH_BREAK"
    CONFIRMED_LATE_SETTLEMENT = "CONFIRMED_LATE_SETTLEMENT"
    OVERDUE_UNSETTLED_BREAK = "OVERDUE_UNSETTLED_BREAK"
    SUSPECTED_DUPLICATE_INTERNAL = "SUSPECTED_DUPLICATE_INTERNAL"
    INTERNAL_HELD_FOR_BANK_DUPLICATE = "INTERNAL_HELD_FOR_BANK_DUPLICATE"
    FULLY_RECONCILED_REFUND = "FULLY_RECONCILED_REFUND"
    RECONCILED_REFUND_MISSING_PARENT = "RECONCILED_REFUND_MISSING_PARENT"
    RECONCILED_REFUND_UNRESOLVED_PARENT = "RECONCILED_REFUND_UNRESOLVED_PARENT"


class BankDisposition(str, Enum):
    """Mutually exclusive terminal dispositions for bank settlement entries."""
    BANK_RECONCILED_CREDIT = "BANK_RECONCILED_CREDIT"
    BANK_CONFIRMED_LATE_CREDIT = "BANK_CONFIRMED_LATE_CREDIT"
    SUSPECTED_DUPLICATE_BANK = "SUSPECTED_DUPLICATE_BANK"
    BANK_HELD_FOR_INTERNAL_DUPLICATE = "BANK_HELD_FOR_INTERNAL_DUPLICATE"
    BANK_RECONCILED_DEBIT = "BANK_RECONCILED_DEBIT"
    ORPHAN_BANK_DEBIT = "ORPHAN_BANK_DEBIT"
    UNMATCHED_BANK_CREDIT = "UNMATCHED_BANK_CREDIT"
    BANK_UNMATCHED_OCT_RESIDUAL = "BANK_UNMATCHED_OCT_RESIDUAL"


def paise_to_inr_str(paise: int) -> str:
    """Format paise integer into display INR string (e.g., 150050 -> '₹1,500.50')."""
    rupees = paise / 100.0
    return f"₹{rupees:,.2f}"


class InternalTransaction(BaseModel):
    internal_txn_id: str
    utr_number: str
    timestamp: str
    customer_id: str
    payment_rail: PaymentRail
    txn_type: TransactionType
    amount_paise: int = Field(gt=0, description="Amount in integer paise (strictly > 0)")
    amount_inr: str
    status: GatewayStatus = GatewayStatus.SUCCESS
    parent_txn_id: Optional[str] = None

    @field_validator("amount_paise")
    @classmethod
    def validate_positive_paise(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount in paise must be positive integer")
        return v


class BankSettlement(BaseModel):
    bank_stmt_id: str
    bank_utr_number: str
    settlement_date: str
    posting_type: PostingType
    gross_amount_paise: int = Field(gt=0, description="Gross settled amount in integer paise")
    gross_amount_inr: str
    fee_paise: int = Field(ge=0, description="Fee retained by bank in integer paise")
    net_amount_paise: int = Field(gt=0, description="Net settled amount in integer paise")
    narration: Optional[str] = None

    @field_validator("net_amount_paise")
    @classmethod
    def validate_fee_invariant(cls, v: int, info) -> int:
        values = info.data
        gross = values.get("gross_amount_paise")
        fee = values.get("fee_paise", 0)
        p_type = values.get("posting_type")
        if gross is not None:
            if p_type == PostingType.CREDIT:
                expected_net = gross - fee
                if v != expected_net:
                    raise ValueError(f"For CREDIT, net ({v}) must equal gross ({gross}) - fee ({fee})")
            elif p_type == PostingType.DEBIT:
                expected_net = gross + fee
                if v != expected_net:
                    raise ValueError(f"For DEBIT, net ({v}) must equal gross ({gross}) + fee ({fee})")
        return v
