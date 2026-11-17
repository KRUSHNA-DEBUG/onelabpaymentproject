"""Payment Reconciliation & Discrepancy Detection System - Streamlit Dashboard."""

import streamlit as st
import pandas as pd
from src.config import (
    INTERNAL_TRANSACTIONS_OCTOBER,
    BANK_SETTLEMENTS_OCTOBER,
    BANK_SETTLEMENTS_NOVEMBER,
    ROUNDING_TOLERANCE_PAISE,
    SLA_BUSINESS_DAYS,
)
from src.models import (
    paise_to_inr_str,
    InternalDisposition,
    BankDisposition,
)
from src.data_generator import generate_synthetic_data
from src.engine.matcher import reconcile_datasets
from src.engine.invariants import verify_all_invariants
from src.ui.components import (
    render_kpi_cards,
    render_waterfall_table,
    render_explainability_card,
)

# Page configuration
st.set_page_config(
    page_title="Payment Reconciliation & Discrepancy Detector",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom header styling
st.title("💳 Payment Reconciliation & Discrepancy Detection System")
st.caption("AI-Native Institutional Financial Ledger Reconciliation Engine | Indian Payment Rails (INR / Paise)")

# -------------------------------------------------------------
# Sidebar: Controls & Dataset Parameters
# -------------------------------------------------------------
st.sidebar.header("⚙️ Configuration & Controls")

if st.sidebar.button("🔄 Regenerate Synthetic Datasets (Seed=42)"):
    with st.spinner("Generating fresh synthetic datasets..."):
        generate_synthetic_data()
    st.sidebar.success("Datasets regenerated successfully!")

st.sidebar.markdown("---")
st.sidebar.subheader("Reconciliation Parameters")
st.sidebar.info(
    f"• **Currency:** INR (₹)\n"
    f"• **Unit:** Integer Paise (Zero float)\n"
    f"• **Rounding Tolerance:** {ROUNDING_TOLERANCE_PAISE} paise (₹0.10)\n"
    f"• **Settlement SLA:** {SLA_BUSINESS_DAYS} Business Days\n"
    f"• **Cutoff Snapshot:** Oct 31, 2026 23:59:59 IST\n"
    f"• **Subsequent Verification:** Nov 05, 2026"
)

# -------------------------------------------------------------
# Data Loading & Live Reconciliation Engine Execution
# -------------------------------------------------------------
@st.cache_data
def load_and_reconcile():
    df_int_raw = pd.read_csv(INTERNAL_TRANSACTIONS_OCTOBER)
    df_oct_raw = pd.read_csv(BANK_SETTLEMENTS_OCTOBER)
    df_nov_raw = pd.read_csv(BANK_SETTLEMENTS_NOVEMBER)
    df_int, df_oct, df_nov, metrics = reconcile_datasets(df_int_raw, df_oct_raw, df_nov_raw)
    inv = verify_all_invariants(df_int, df_oct, df_nov, metrics)
    return df_int, df_oct, df_nov, metrics, inv

try:
    df_int, df_oct, df_nov, metrics, inv = load_and_reconcile()
except Exception as e:
    st.error(f"Error loading datasets: {e}")
    st.stop()

# -------------------------------------------------------------
# Top-Level KPI Cards
# -------------------------------------------------------------
render_kpi_cards(metrics)

st.markdown("---")

# -------------------------------------------------------------
# Two-Stage Month-End Waterfall
# -------------------------------------------------------------
render_waterfall_table(metrics)

st.markdown("---")

# -------------------------------------------------------------
# Operational Discrepancy Workbench
# -------------------------------------------------------------
st.subheader("🛠️ Operational Discrepancy Workbench")

# Search and Filters
f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
with f_col1:
    search_query = st.text_input("🔎 Search by UTR / RRN or Internal Txn ID:", "")
with f_col2:
    selected_rail = st.selectbox("Filter by Payment Rail:", ["All", "UPI", "IMPS", "NEFT", "CARD"])
with f_col3:
    selected_category = st.selectbox(
        "Filter by Category:",
        ["All", "Reconciled", "Timing (In-Transit)", "Rounding Drift", "Duplicate Quarantine", "Refund Discrepancy", "Operational Break"]
    )

# Filter internal records
filtered_int = df_int.copy()
if search_query:
    filtered_int = filtered_int[
        filtered_int["utr_number"].str.contains(search_query, case=False, na=False)
        | filtered_int["internal_txn_id"].str.contains(search_query, case=False, na=False)
    ]
if selected_rail != "All":
    filtered_int = filtered_int[filtered_int["payment_rail"] == selected_rail]
if selected_category != "All":
    filtered_int = filtered_int[filtered_int["discrepancy_category"] == selected_category]

# Tabs for the 4 mandatory scenarios + Bank breaks + Full Ledger
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "⏳ 1. Timing & Late Settlements",
    "⚖️ 2. Rounding Drift",
    "👥 3. Duplicate Suspects",
    "↩️ 4. Refund Lineage",
    "🏦 5. Bank Discrepancies",
    "📋 6. Master Reconciled Ledger & Export",
])

# Tab 1: Late Settlements
with tab1:
    st.markdown("#### Scenario 1: Month-End Timing Delays & Subsequent Verification")
    st.caption("Transactions authorized near October 31 cutoff: evaluated at cutoff snapshot, then verified against November bank statement.")
    
    late_df = df_int[df_int["internal_disposition"].isin([
        InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value,
        InternalDisposition.OVERDUE_UNSETTLED_BREAK.value,
    ])]
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.metric("Confirmed Late Settlements (Nov Cleared)", f"{len(df_int[df_int['internal_disposition'] == InternalDisposition.CONFIRMED_LATE_SETTLEMENT.value])} records", paise_to_inr_str(metrics["in_transit_paise"]))
    with col_t2:
        st.metric("Overdue Unsettled Breaks (>3 Business Days)", f"{len(df_int[df_int['internal_disposition'] == InternalDisposition.OVERDUE_UNSETTLED_BREAK.value])} records", paise_to_inr_str(metrics["overdue_breaks_paise"]))

    display_cols = ["internal_txn_id", "utr_number", "timestamp", "payment_rail", "amount_inr", "october_snapshot_status", "internal_disposition", "matched_settlement_date", "explanation_action"]
    st.dataframe(late_df[display_cols], use_container_width=True)

# Tab 2: Rounding Drift
with tab2:
    st.markdown(r"#### Scenario 2: Rounding Differences (Tolerance: $\le 10$ paise)")
    st.caption("Individual fractional cent/paise differences arising from interchange or GST calculations aggregated to track balance drift.")
    
    round_df = df_int[df_int["internal_disposition"] == InternalDisposition.RECONCILED_ROUNDING_VARIANCE.value]
    st.metric("Cumulative Net Rounding Drift", f"{metrics['net_rounding_drift_paise']:+d} paise ({paise_to_inr_str(abs(metrics['net_rounding_drift_paise']))})", f"{len(round_df)} transactions")
    
    display_cols_r = ["internal_txn_id", "utr_number", "payment_rail", "amount_inr", "matched_bank_gross_paise", "delta_paise", "explanation_reason", "explanation_action"]
    st.dataframe(round_df[display_cols_r], use_container_width=True)

# Tab 3: Duplicate Suspects
with tab3:
    st.markdown("#### Scenario 3: Duplicate Detection & Counterpart Protection")
    st.caption("Quarantines duplicate internal or bank records to prevent corrupting clean 1:1 auto-matching.")
    
    dup_col1, dup_col2 = st.columns(2)
    with dup_col1:
        st.write("##### Internal Duplicates (Double Webhook Callbacks)")
        int_dup_df = df_int[df_int["internal_disposition"] == InternalDisposition.SUSPECTED_DUPLICATE_INTERNAL.value]
        st.dataframe(int_dup_df[["internal_txn_id", "utr_number", "timestamp", "amount_inr", "internal_disposition", "explanation_action"]], use_container_width=True)
    
    with dup_col2:
        st.write("##### Bank Statement Duplicates (Batch Glitch)")
        bnk_dup_df = df_oct[df_oct["bank_disposition"] == BankDisposition.SUSPECTED_DUPLICATE_BANK.value]
        st.dataframe(bnk_dup_df[["bank_stmt_id", "bank_utr_number", "settlement_date", "gross_amount_inr", "bank_disposition", "bank_explanation_action"]], use_container_width=True)

# Tab 4: Refund Lineage
with tab4:
    st.markdown("#### Scenario 4: Refund Lineage & Parent Reference Traversal")
    st.caption("Separates bank amount matching from internal parent charge audit lineage validation.")
    
    refund_df = df_int[df_int["txn_type"] == "REFUND"]
    display_cols_ref = ["internal_txn_id", "utr_number", "amount_inr", "parent_txn_id", "internal_disposition", "explanation_reason", "explanation_action"]
    st.dataframe(refund_df[display_cols_ref], use_container_width=True)

# Tab 5: Bank Discrepancies
with tab5:
    st.markdown("#### Direct Bank Discrepancies (Unmatched Credits & Orphan Debits)")
    st.caption("Bank statement entries with no corresponding internal transaction authorizations.")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.write("##### Unmatched Bank Direct Credits (Surplus Cash)")
        unmatched_credits = df_oct[df_oct["bank_disposition"] == BankDisposition.UNMATCHED_BANK_CREDIT.value]
        st.dataframe(unmatched_credits[["bank_stmt_id", "bank_utr_number", "settlement_date", "gross_amount_inr", "bank_explanation_action"]], use_container_width=True)
    
    with b_col2:
        st.write("##### Orphan Bank Debits (Unaccounted Outflow)")
        orphan_debits = df_oct[df_oct["bank_disposition"] == BankDisposition.ORPHAN_BANK_DEBIT.value]
        st.dataframe(orphan_debits[["bank_stmt_id", "bank_utr_number", "settlement_date", "gross_amount_inr", "bank_explanation_action"]], use_container_width=True)

# Tab 6: Master Reconciled Ledger & Export
with tab6:
    st.markdown("#### Master Reconciled Internal Ledger (All 1,000 Records)")
    st.write(f"Showing **{len(filtered_int)}** records based on active workbench filters.")
    st.dataframe(filtered_int, use_container_width=True)
    
    # CSV Export Button
    csv_bytes = filtered_int.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Filtered Reconciliation Audit Report (CSV)",
        data=csv_bytes,
        file_name="reconciliation_audit_report.csv",
        mime="text/csv",
    )

st.markdown("---")

# -------------------------------------------------------------
# Diagnostic Explainability Inspector
# -------------------------------------------------------------
st.subheader("🔍 Transaction Diagnostic & Explainability Inspector")
txn_ids = df_int["internal_txn_id"].tolist()
selected_txn_id = st.selectbox("Select any Internal Transaction to inspect complete audit lineage:", txn_ids)

if selected_txn_id:
    selected_row = df_int[df_int["internal_txn_id"] == selected_txn_id].iloc[0]
    render_explainability_card(selected_row)
