"""Refund Lineage and Parent Reference Validator."""

from typing import Set, Optional
from src.models import InternalDisposition


def evaluate_refund_lineage(
    parent_txn_id: Optional[str],
    settled_parent_ids: Set[str],
) -> InternalDisposition:
    """Evaluate whether an internal refund traces to a valid settled payment.

    Distinguishes:
    - Missing parent reference (parent_txn_id is None or empty)
    - Unresolved parent lookup (parent_txn_id not in settled ledger)
    - Valid linked refund (parent_txn_id confirmed settled)
    """
    if not parent_txn_id or str(parent_txn_id).strip() in ["", "None", "nan"]:
        return InternalDisposition.RECONCILED_REFUND_MISSING_PARENT

    cleaned_parent_id = str(parent_txn_id).strip()
    if cleaned_parent_id in settled_parent_ids:
        return InternalDisposition.FULLY_RECONCILED_REFUND
    else:
        return InternalDisposition.RECONCILED_REFUND_UNRESOLVED_PARENT
