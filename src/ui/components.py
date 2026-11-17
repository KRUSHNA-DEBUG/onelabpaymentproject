"""Reusable UI Components for Streamlit Reconciliation Dashboard."""

import streamlit as st
import pandas as pd
from typing import Dict, Any
from src.models import paise_to_inr_str, InternalDisposition, BankDisposition


def render_kpi_cards(metrics: Dict[str, Any]):
    """Render top-level executive KPI cards with responsive formatting to avoid truncation."""
    # Custom CSS to guarantee full visibility of large INR values without truncation
    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
            white-space: nowrap !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.95rem !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns([1.35, 1.0, 1.05, 1.05])

    with col1:
        net_paise = metrics["total_internal_authorized_net_paise"]
        st.metric(
            label="Internal Authorized Net",
            value=paise_to_inr_str(net_paise),
            help=f"Exact value: {net_paise:,} paise across {metrics['total_internal_records']} internal records",
        )

    with col2:
        reconciled_pct = metrics["reconciled_rate_pct"]
        st.metric(
            label="Reconciliation Rate",
            value=f"{reconciled_pct:.1f}%",
            delta=f"{metrics['reconciled_internal_count']} / {metrics['total_internal_records']} records",
            help="Includes exact matches, rounding tolerance matches, and reconciled refunds",
        )

    with col3:
        in_transit_paise = metrics["in_transit_paise"]
        st.metric(
            label="In-Transit (Cleared Nov)",
            value=paise_to_inr_str(in_transit_paise),
            help=f"Timing difference: {in_transit_paise:,} paise cleared in Nov 01–03 bank statement",
        )

    with col4:
        break_paise = metrics["overdue_breaks_paise"]
        st.metric(
            label="Overdue Unsettled Breaks",
            value=paise_to_inr_str(break_paise),
            delta="Action Required",
            delta_color="inverse",
            help=f"Uncollected merchant funds: {break_paise:,} paise past SLA threshold",
        )


def render_waterfall_table(metrics: Dict[str, Any]):
    """Render the master two-stage month-end financial waterfall table.
    
    Verifies that bank fees, internal duplicates, bank duplicates, held counterpart records,
    rounding differences, refunds and unmatched bank entries are accounted for exactly once.
    """
    st.subheader("📊 Two-Stage Month-End Reconciliation Waterfall")
    st.caption("Reconciles internal gateway authorized net balance with bank statement gross and net settled cash.")

    waterfall_data = [
        {
            "Step": "1. Internal Authorized Net Balance",
            "Sign": "(+)",
            "Amount (INR)": paise_to_inr_str(metrics["total_internal_authorized_net_paise"]),
            "Amount (Paise)": f"{metrics['total_internal_authorized_net_paise']:,}",
            "Accounting Category": "Internal Book Balance (Gross Auth - Refunds)",
        },
        {
            "Step": "2. (-) Confirmed In-Transit (Cleared Nov 1-3)",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(metrics['in_transit_paise'])}",
            "Amount (Paise)": f"-{metrics['in_transit_paise']:,}",
            "Accounting Category": "Timing Difference (In-Transit Asset)",
        },
        {
            "Step": "3. (-) Net Rounding Variance",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(abs(metrics['net_rounding_drift_paise']))}",
            "Amount (Paise)": f"-{metrics['net_rounding_drift_paise']:,}",
            "Accounting Category": "Rounding & Fee Expense Reserve",
        },
        {
            "Step": "4. (-) Overdue Unsettled Breaks",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(metrics['overdue_breaks_paise'])}",
            "Amount (Paise)": f"-{metrics['overdue_breaks_paise']:,}",
            "Accounting Category": "Operational Break (Escalation to Bank Ops)",
        },
        {
            "Step": "5. (-) Internal Duplicate Quarantine Variance",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(metrics['int_dup_variance_paise'])}",
            "Amount (Paise)": f"-{metrics['int_dup_variance_paise']:,}",
            "Accounting Category": "Quarantine Variance (Internal Double Webhooks)",
        },
        {
            "Step": "6. (+) Bank Duplicate Quarantine Variance",
            "Sign": "(+)",
            "Amount (INR)": f"+{paise_to_inr_str(metrics['bank_dup_variance_paise'])}",
            "Amount (Paise)": f"+{metrics['bank_dup_variance_paise']:,}",
            "Accounting Category": "Quarantine Variance (Bank Batch Duplicates)",
        },
        {
            "Step": "7. (+) Unmatched Direct Bank Credits",
            "Sign": "(+)",
            "Amount (INR)": f"+{paise_to_inr_str(metrics['unmatched_bank_credits_paise'])}",
            "Amount (Paise)": f"+{metrics['unmatched_bank_credits_paise']:,}",
            "Accounting Category": "Unidentified Bank Deposit (Surplus Cash)",
        },
        {
            "Step": "8. (-) Orphan Bank Debits",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(metrics['orphan_bank_debits_paise'])}",
            "Amount (Paise)": f"-{metrics['orphan_bank_debits_paise']:,}",
            "Accounting Category": "Bank Chargeback / Unauthorized Debit",
        },
        {
            "Step": "9. (=) Audited Bank October Gross Cash",
            "Sign": "(=)",
            "Amount (INR)": paise_to_inr_str(metrics["total_bank_oct_gross_net_paise"]),
            "Amount (Paise)": f"{metrics['total_bank_oct_gross_net_paise']:,}",
            "Accounting Category": "Audited Bank Gross Statement Total",
        },
        {
            "Step": "10. (-) Total Bank Processing Fees Deducted",
            "Sign": "(-)",
            "Amount (INR)": f"-{paise_to_inr_str(metrics['total_bank_oct_fees_paise'])}",
            "Amount (Paise)": f"-{metrics['total_bank_oct_fees_paise']:,}",
            "Accounting Category": "Bank Interchange & Processing Fees Retained",
        },
        {
            "Step": "11. (=) Final Net Cash Posted to Bank Account",
            "Sign": "(=)",
            "Amount (INR)": paise_to_inr_str(metrics["total_bank_oct_cash_posted_paise"]),
            "Amount (Paise)": f"{metrics['total_bank_oct_cash_posted_paise']:,}",
            "Accounting Category": "Net Cash Deposited in Merchant Bank Account",
        },
    ]

    df_wf = pd.DataFrame(waterfall_data)
    st.table(df_wf)

    # Invariant alert
    if metrics["is_master_balanced"]:
        st.success("✅ **Master Monetary Conservation Satisfied:** Balance residual between internal ledger and bank gross settlement is exactly **0 paise** (₹0.00). All terms accounted for exactly once.")
    else:
        st.error(f"❌ **Reconciliation Imbalance:** Balance residual is {metrics['balance_residual_paise']} paise.")


def render_explainability_card(row: pd.Series):
    """Render detailed diagnostic explainability card for a selected transaction."""
    st.markdown("### 🔍 Transaction Diagnostic & Explainability Inspector")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.write(f"**Transaction ID:** `{row.get('internal_txn_id', 'N/A')}`")
        st.write(f"**UTR Number:** `{row.get('utr_number', 'N/A')}`")
    with c2:
        st.write(f"**Payment Rail:** `{row.get('payment_rail', 'N/A')}`")
        st.write(f"**Transaction Type:** `{row.get('txn_type', 'N/A')}`")
    with c3:
        st.write(f"**Internal Amount:** `{row.get('amount_inr', 'N/A')}` ({row.get('amount_paise', 0):,} paise)")
        matched_gross = row.get("matched_bank_gross_paise")
        if pd.notna(matched_gross):
            st.write(f"**Bank Gross:** `{paise_to_inr_str(int(matched_gross))}`")
        else:
            st.write("**Bank Gross:** `Unsettled / N/A`")
    with c4:
        delta = row.get("delta_paise", 0)
        st.write(f"**Amount Delta:** `{delta:+d} paise`")
        
        # Display "Not applicable" instead of NaN for missing Parent Txn IDs
        parent_id = row.get("parent_txn_id")
        if pd.isna(parent_id) or parent_id is None or str(parent_id).strip() in ["", "None", "nan", "NaN", "<NA>"]:
            parent_display = "Not applicable"
        else:
            parent_display = str(parent_id).strip()
        st.write(f"**Parent Txn ID:** `{parent_display}`")

    st.info(f"**Audit Diagnosis:** {row.get('explanation_reason', 'N/A')}")
    st.warning(f"**Recommended Advisory Action:** {row.get('explanation_action', 'N/A')}")
