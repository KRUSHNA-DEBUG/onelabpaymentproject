"""Explainability and Audit Narrative Generator."""

from typing import Dict, Any, Optional
from src.models import paise_to_inr_str, InternalDisposition, BankDisposition


def get_explanation(
    disposition: str,
    delta_paise: Optional[int] = None,
    settle_date: Optional[str] = None,
    parent_id: Optional[str] = None,
    utr: Optional[str] = None,
) -> Dict[str, str]:
    """Generate deterministic, plain-language audit explanations and operational advisories."""
    
    safe_delta = delta_paise if delta_paise is not None else 0
    delta_str = paise_to_inr_str(abs(safe_delta))

    explanations: Dict[str, Dict[str, str]] = {
        InternalDisposition.FULLY_RECONCILED.value: {
            "reason": "Exact 1:1 match on UTR and gross settled amount. Cleared within standard SLA.",
            "action": "Auto-reconciled. No operational action required.",
            "category": "Reconciled",
        },
        InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value: {
            "reason": f"UTR matched. Amount variance of {safe_delta:+d} paise ({delta_str}) is within 10-paise tolerance (interchange/GST fractional drift).",
            "action": "Auto-reconciled. Book variance to Rounding Expense Reserve.",
            "category": "Rounding Drift",
        },
        InternalDisposition.AMOUNT_MISMATCH_BREAK.value: {
            "reason": f"UTR matched, but variance of {safe_delta:+d} paise ({delta_str}) exceeds 10-paise tolerance.",
            "action": "Flagged as Break. Escalate to Acquirer Operations for charge dispute.",
            "category": "Operational Break",
        },
        InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value: {
            "reason": f"Authorized near October cutoff within 3-day SLA. Confirmed settled in November bank statement on {settle_date}.",
            "action": "Accrue as In-Transit Asset at October close. Books balanced.",
            "category": "Timing (In-Transit)",
        },
        InternalDisposition.OVERDUE_UNSETTLED_BREAK.value: {
            "reason": "Payment authorized in October remains unsettled after SLA and absent from subsequent clearing statements.",
            "action": "Operational Break. Escalate to Payment Aggregator for missing fund retrieval.",
            "category": "Operational Break",
        },
        InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value: {
            "reason": "Multiple internal records share this UTR. Double webhook delivery or client retry detected.",
            "action": "Quarantined. Verify webhook handler idempotency; avoid duplicate fulfillment.",
            "category": "Duplicate Quarantine",
        },
        InternalDisposition.INTERNAL_HELD_FOR_BANK_DUPLICATE.value: {
            "reason": "Internal record is unique, but bank statement contains duplicate credits for this UTR.",
            "action": "Held. Await bank statement correction / debit reversal for duplicate batch entry.",
            "category": "Duplicate Quarantine",
        },
        InternalDisposition.FULLY_RECONCILED_REFUND.value: {
            "reason": f"Refund matched 1:1 with bank debit. Parent payment {parent_id} confirmed settled.",
            "action": "Auto-reconciled. Legitimate customer refund confirmed.",
            "category": "Reconciled",
        },
        InternalDisposition.RECONCILED_REFUND_MISSING_PARENT.value: {
            "reason": "Refund matched 1:1 with bank debit, but parent transaction reference is missing (NULL).",
            "action": "Informational Advisory: Review customer support ledger for manual refund entry.",
            "category": "Refund Discrepancy",
        },
        InternalDisposition.RECONCILED_REFUND_UNRESOLVED_PARENT.value: {
            "reason": f"Refund matched 1:1 with bank debit, but parent ID '{parent_id}' was not found in current ledger.",
            "action": "Informational Advisory: Verify prior-period ledger or external payment gateway.",
            "category": "Refund Discrepancy",
        },
        BankDisposition.BANK_RECONCILED_CREDIT.value: {
            "reason": "Bank credit matched 1:1 with internal payment authorization.",
            "action": "Audited bank credit.",
            "category": "Reconciled",
        },
        BankDisposition.BANK_CONFIRMED_LATE_CREDIT.value: {
            "reason": "November bank credit matched to October month-end in-transit payment.",
            "action": "Cleared in-transit fund.",
            "category": "Timing (In-Transit)",
        },
        BankDisposition.SUSPECTED_DUPLICATE_BANK.value: {
            "reason": "Duplicate bank credit line item detected in statement batch.",
            "action": "Quarantined. Notify bank operations of duplicate settlement credit.",
            "category": "Duplicate Quarantine",
        },
        BankDisposition.BANK_HELD_FOR_INTERNAL_DUPLICATE.value: {
            "reason": "Bank credit held because internal system logged duplicate entries for this UTR.",
            "action": "Held pending internal webhook deduplication review.",
            "category": "Duplicate Quarantine",
        },
        BankDisposition.BANK_RECONCILED_DEBIT.value: {
            "reason": "Bank debit matched 1:1 with internal refund authorization.",
            "action": "Audited bank debit.",
            "category": "Reconciled",
        },
        BankDisposition.ORPHAN_BANK_DEBIT.value: {
            "reason": "Bank debited funds from merchant account without any matching internal refund record.",
            "action": "High Priority: Investigate unexpected bank chargeback, penalty, or unauthorized debit.",
            "category": "Operational Break",
        },
        BankDisposition.UNMATCHED_BANK_CREDIT.value: {
            "reason": "Direct funds received in bank account with no matching internal customer payment order.",
            "action": "Investigate direct NEFT/IMPS customer deposit; contact customer or book manual order.",
            "category": "Operational Break",
        },
    }

    return explanations.get(
        disposition,
        {
            "reason": f"Classified under {disposition}.",
            "action": "Review record in discrepancy workbench.",
            "category": "Unclassified",
        },
    )
