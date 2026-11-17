# Payment Reconciliation and Discrepancy Detection System
**AI Native Engineer Intern Assessment Project**  
**Domain:** Financial Technology / Indian Payment Infrastructure (UPI, IMPS, NEFT, CARD)  
**Standard:** Enterprise Audit & Institutional Financial Ledger Specifications  

---

## 1. Executive Summary & Architecture Overview

In modern financial operations, reconciliation between internal transaction ledgers and external bank statements is the bedrock of accounting truth. 

This system resolves a fundamental business reality:
* **The Payment Gateway** records intent, authorizations, and refunds instantly ($T+0$).
* **The Banking Clearing Network** (RBI RTGS/NEFT batches, NPCI UPI settlement windows, Acquirer card clearing) settles actual funds with a $1$ to $2$ business-day lag ($T+1$, $T+2$).
* At month-end closing, an internal ledger and bank statement will never match naively.

### Core Engineering Principles:
1. **Timing Differences $\neq$ Financial Loss:** Month-end transactions that settle in early November are recognized as valid **In-Transit Assets**, not missing money.
2. **Zero Floating-Point Precision:** To prevent binary floating-point errors ($0.1 + 0.2 \neq 0.3$), all calculations are executed strictly in **Integer Paise** ($₹1.00 = 100\text{ paise}$) using `int64`. Display strings in INR are formatted representations derived from paise.
3. **Strict 1:1 Matching Guarantee:** Enforced via deduplication quarantine. Ambiguous records cannot enter automatic matching, mathematically preventing Cartesian many-to-many join explosions.
4. **Conservation of Records & Monetary Value:** Every single input row receives exactly one terminal disposition. Total records and financial values balance across all categories with **0 paise residual**.
5. **Deterministic Explainability:** Clear, audit-grade diagnostic reasons and recommended operational workflows are generated for every record.

---

## 2. Documented Dataset Counts & Refund Inconsistency Resolution

Per the intern assessment requirements, the synthetic dataset is strictly controlled with **exactly 1,000 internal October records**, plus corresponding October and November bank settlement files.

### Exact Internal Ledger Breakdown (`internal_transactions_october.csv`: 1,000 rows)

| Category | Record Count | Description |
| :--- | :---: | :--- |
| **Clean 1:1 Payments** | 810 | Normal payments authorized Oct 01–27, settled in October bank statement. |
| **Internal Counterparts to Bank Duplicates** | 10 | Unique internal payments whose UTR appears twice in bank statement. |
| **Month-End Timing Delays (Oct 29–31)** | 50 | In-transit at cutoff. 45 clear in Nov (Late); 5 remain unsettled (Overdue). |
| **Minor Rounding Differences** | 40 | Exact UTR match with gross amount variance within $\le 10$ paise. |
| **Suspected Internal Duplicates** | 30 | 15 unique UTRs, each appearing twice internally (double webhook bug). |
| **Internal Refunds** | 30 | Categorized by parent lineage: 15 valid, 8 missing parent, 7 unresolved parent. |
| **Internal Stale Breaks** | 30 | Authorized Oct 05–25, past 3-day SLA, never settled by bank. |
| **TOTAL INTERNAL OCTOBER RECORDS** | **1,000** | **Exact row count verified** |

### Resolution of Refund Counts:
* **Internal Refunds (30 rows):**
  * `15` Valid Linked Refunds: `parent_txn_id` points to a settled clean payment.
  * `8` Missing Parent References: `parent_txn_id` is NULL / empty.
  * `7` Unresolved Parent References: `parent_txn_id` references a non-existent transaction.
* **Bank October Statement (`bank_settlements_october.csv`: 945 rows):**
  * $810$ clean payment credits
  * $40$ rounding difference credits
  * $15$ bank credits held for internal duplicates (1 for each duplicate UTR)
  * $20$ bank duplicate credits (10 unique UTRs $\times$ 2 entries)
  * $30$ bank debit entries matching the 30 internal refunds 1:1 on cash movement
  * $15$ orphan bank debits (bank debited funds with unknown UTRs)
  * $15$ unmatched bank credits (unidentified direct customer NEFT/IMPS deposits)
  * **Total Bank October Rows = 945**
* **Bank November Statement (`bank_settlements_november.csv`: 45 rows):**
  * Contains the clearing records for the 45 late October payments that settled on Nov 01–03.

---

## 3. Implementation of the Four Mandatory Scenarios

### Scenario 1: Late Settlements (Timing Differences)
* **Cutoff Snapshot (October 31, 23:59:59 IST):** Transactions authorized on Oct 29, 30, and 31 (within the 3-business-day SLA) that have not posted to the October bank statement are classified as `PENDING_SETTLEMENT_AT_OCT_CUTOFF`.
* **Subsequent Clearing Verification (November 5, 23:59:59 IST):** Evaluated against `bank_settlements_november.csv`.
  * **45 transactions** matched on UTR and settled on Nov 1–3 $\implies$ `CONFIRMED_LATE_SETTLEMENT` (Accrued as in-transit asset).
  * **5 transactions** absent from November statement $\implies$ `OVERDUE_UNSETTLED_BREAK` (Escalated to operations).

### Scenario 2: Rounding Differences
* **Tolerance:** $\le 10\text{ paise}$ ($₹0.10$).
* Transactions where the UTR matches 1:1, but the bank gross amount differs by $1$ to $10$ paise due to fractional interchange or GST truncation are categorized as `RECONCILED_ROUNDING_VARIANCE`.
* The system sums individual variances $\sum \Delta_i$ across all 40 records to track cumulative net balance drift for accounting reserve allocation.

### Scenario 3: Duplicate Entries & Counterpart Protection
* **Intra-dataset duplicate detection:**
  * If a UTR appears $>1$ time in internal records $\implies$ quarantined as `SUSPECTED_DUPLICATE_INTERNAL`. The single bank credit for that UTR is classified as `BANK_HELD_FOR_INTERNAL_DUPLICATE`.
  * If a UTR appears $>1$ time in bank records $\implies$ quarantined as `SUSPECTED_DUPLICATE_BANK`. The single internal payment is classified as `INTERNAL_HELD_FOR_BANK_DUPLICATE`.
* Counterparts are never misclassified as ordinary unmatched breaks.

### Scenario 4: Orphan Refunds & Lineage Validation
* Cash movement matching is strictly decoupled from internal audit lineage validation:
  * In all 30 internal refund cases, cash movement matched the bank debit 1:1 $\implies$ bank record is `BANK_RECONCILED_DEBIT`.
  * If parent payment is verified $\implies$ `FULLY_RECONCILED_REFUND`.
  * If parent reference is NULL $\implies$ `RECONCILED_REFUND_MISSING_PARENT`.
  * If parent reference is not found in ledger $\implies$ `RECONCILED_REFUND_UNRESOLVED_PARENT`.
  * True bank orphan debits (debits with no internal record) $\implies$ `ORPHAN_BANK_DEBIT`.

---

## 4. Master Conservation Invariants & Reconciliation Equation

Before publishing reports, the system automatically proves that no record is lost and no paisa is unrecorded:

### Invariant 1: Record Count Conservation
* Internal: $\sum \text{Disposition Counts} \equiv 1,000$ (0 nulls).
* Bank October: $\sum \text{Disposition Counts} \equiv 945$ (0 nulls).
* Bank November: $\sum \text{Disposition Counts} \equiv 45$ (0 nulls).

### Invariant 2: Master Monetary Value Conservation (0 Paise Residual)
$$\begin{aligned}
\text{Net}_{\text{internal}} &- \text{In\_Transit} - \text{Rounding\_Drift} - \text{Overdue\_Breaks} - \text{Int\_Dup\_Variance} \\
&+ \text{Bank\_Dup\_Variance} + \text{Unmatched\_Bank\_Credits} - \text{Orphan\_Bank\_Debits} \equiv \text{Gross}_{\text{bank\_oct}}
\end{aligned}$$
* **Residual:** Exactly **0 paise** ($₹0.00$).

---

## 5. Automated Test Suite Results (20 / 20 Tests Passed)

All 20 test cases pass with 100% green status:

| Test ID | Test Name | Scenario Tested | Status |
| :---: | :--- | :--- | :---: |
| **TC-01** | `test_tc01_clean_upi_exact_match` | Standard 1:1 UPI match, $\Delta = 0$ | **PASSED** |
| **TC-02** | `test_tc02_clean_neft_high_value` | High-value NEFT exact match (₹1,50,000) | **PASSED** |
| **TC-03** | `test_tc03_rounding_drift_positive` | Rounding drift under tolerance (+4 paise) | **PASSED** |
| **TC-04** | `test_tc04_rounding_drift_negative` | Rounding drift under tolerance (-7 paise) | **PASSED** |
| **TC-05** | `test_tc05_amount_mismatch_break` | Amount mismatch exceeding 10 paise (>₹150) | **PASSED** |
| **TC-06** | `test_tc06_confirmed_late_settlement_nov` | Month-end UPI cleared Nov 02 | **PASSED** |
| **TC-07** | `test_tc07_confirmed_late_card_t_plus_2` | Month-end Card settlement cleared Nov 03 | **PASSED** |
| **TC-08** | `test_tc08_month_end_overdue_unsettled` | Month-end payment failing to clear in Nov | **PASSED** |
| **TC-09** | `test_tc09_stale_mid_month_unsettled_break` | Stale payment >3 business days old | **PASSED** |
| **TC-10** | `test_tc10_suspected_duplicate_internal` | Double webhook callback duplicate quarantine | **PASSED** |
| **TC-11** | `test_tc11_suspected_duplicate_bank` | Duplicate bank batch credit quarantine | **PASSED** |
| **TC-12** | `test_tc12_valid_linked_refund` | Valid refund linked to settled parent | **PASSED** |
| **TC-13** | `test_tc13_refund_missing_parent_reference` | Refund matched, parent ID is NULL | **PASSED** |
| **TC-14** | `test_tc14_refund_unresolved_parent` | Refund matched, parent ID not in ledger | **PASSED** |
| **TC-15** | `test_tc15_unmatched_bank_credit` | Direct bank deposit (surplus credit) | **PASSED** |
| **TC-16** | `test_tc16_orphan_bank_debit` | Orphan bank debit (unexpected cash outflow) | **PASSED** |
| **TC-17** | `test_tc17_weekend_and_holiday_sla` | Weekend & Gandhi Jayanti SLA date math | **PASSED** |
| **TC-18** | `test_tc18_bank_credit_fee_invariant` | Credit fee invariant: `gross - fee == net` | **PASSED** |
| **TC-19** | `test_tc19_bank_debit_fee_invariant` | Debit fee invariant: `gross + fee == net` | **PASSED** |
| **TC-20** | `test_tc20_full_dataset_invariants` | Full 1,000 internal + 945 bank conservation | **PASSED** |

---

## 6. Project Structure

```
Payment-Reconciliation-System/
├── data/
│   ├── internal_transactions_october.csv   # Exactly 1,000 internal transactions
│   ├── bank_settlements_october.csv        # 945 October bank statement lines
│   └── bank_settlements_november.csv       # 45 November clearing lines
├── src/
│   ├── __init__.py
│   ├── config.py                           # SLA thresholds, banking holidays, file paths
│   ├── models.py                           # Pydantic schemas, Enums, fee validators
│   ├── data_generator.py                   # Deterministic synthetic data generator (seed=42)
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── normalizer.py                   # Type coercion, business-day calendar math
│   │   ├── duplicate_detector.py           # Pre-matching duplicate isolation & counterpart hold
│   │   ├── matcher.py                      # Multi-pass 1:1 matcher & 2-stage month-end resolver
│   │   ├── refund_tracker.py               # Refund lineage traversal engine
│   │   ├── explainability.py               # Rule-to-narrative explainability generator
│   │   └── invariants.py                   # Conservation of records and paise verification
│   └── ui/
│       ├── __init__.py
│       ├── app.py                          # Streamlit application entrypoint
│       └── components.py                   # KPI cards, Waterfall table, and diagnostic inspector
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         # Pytest dataset fixtures
│   ├── test_scenarios.py                   # Tests TC-01 to TC-16
│   ├── test_sla_and_fees.py                # Tests TC-17 to TC-19
│   └── test_invariants.py                  # Test TC-20 (Full dataset conservation)
├── requirements.txt                        # Pinned dependencies
└── README.md                               # Comprehensive system documentation
```

---

## 7. Execution Instructions

### Prerequisites
* Python 3.10+ (tested on Python 3.14)

### Step 1: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 2: Regenerate Synthetic Datasets (Optional)
```powershell
python -m src.data_generator
```

### Step 3: Run the Complete Automated Test Suite
```powershell
python -m pytest -v
```

### Step 4: Launch the Streamlit Interactive Dashboard
```powershell
python -m streamlit run src/ui/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser to interact with the executive KPI summary, two-stage waterfall reconciliation, discrepancy workbench, and transaction inspector.
