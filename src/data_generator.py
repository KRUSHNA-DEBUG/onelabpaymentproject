"""Synthetic Dataset Generator for Payment Reconciliation System.

Generates realistic Indian payment datasets (UPI, IMPS, NEFT, CARD) with:
- Exactly 1,000 October internal transaction records
- 945 October bank settlement records
- 45 November bank settlement records (confirming late settlements)
All amounts are represented in integer paise.
"""

import random
from datetime import datetime, timedelta
import pandas as pd
from src.config import (
    INTERNAL_TRANSACTIONS_OCTOBER,
    BANK_SETTLEMENTS_OCTOBER,
    BANK_SETTLEMENTS_NOVEMBER,
    RANDOM_SEED,
    PAYMENT_RAILS,
)
from src.models import paise_to_inr_str


def generate_utr(rail: str, seq: int) -> str:
    """Generate realistic Indian banking clearing references."""
    if rail == "UPI":
        return f"4305{seq:08d}"  # 12-digit numeric UPI UTR
    elif rail == "IMPS":
        return f"4291{seq:08d}"  # 12-digit numeric IMPS RRN
    elif rail == "NEFT":
        return f"N10226{seq:06d}"  # Alphanumeric NEFT UTR
    else:  # CARD
        return f"745210{seq:10d}"  # 16-digit Card ARN


def generate_synthetic_data(seed: int = RANDOM_SEED):
    random.seed(seed)
    
    internal_records = []
    bank_oct_records = []
    bank_nov_records = []

    seq_counter = 1
    stmt_counter = 1

    # -------------------------------------------------------------
    # 1. CLEAN NORMAL 1:1 PAYMENTS (810 records)
    # Authorized Oct 01 - Oct 27, settling Oct 02 - Oct 29
    # -------------------------------------------------------------
    for i in range(810):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.randint(1, 26)
        hour = random.randint(8, 20)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        txn_time = datetime(2026, 10, day, hour, minute, second)
        
        # Settle in 1 to 2 days
        settle_date = (txn_time + timedelta(days=random.choice([1, 2]))).strftime("%Y-%m-%d")
        
        amount_paise = random.randint(100, 50000) * 100  # ₹100.00 to ₹50,000.00
        customer_id = f"CUST_IND_{random.randint(1000, 9999)}"
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        
        # Internal record
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": customer_id,
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        # Bank record (Credit)
        fee_paise = max(50, int(amount_paise * 0.005))  # 0.5% or min 50 paise
        net_paise = amount_paise - fee_paise
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": amount_paise,
            "gross_amount_inr": paise_to_inr_str(amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": net_paise,
            "narration": f"{rail}-SETTL-{utr}",
        })
        stmt_counter += 1

    # Keep references of first 50 clean transactions for valid refund parents
    clean_settled_txns = list(internal_records[:50])

    # -------------------------------------------------------------
    # 2. INTERNAL RECORDS HELD FOR BANK DUPLICATE (10 records)
    # Internal has 1 record; Bank has 2 records with same UTR (batch glitch)
    # Total: 10 internal records, 20 bank records
    # -------------------------------------------------------------
    for i in range(10):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.randint(5, 20)
        txn_time = datetime(2026, 10, day, 10, 0, 0)
        settle_date = (txn_time + timedelta(days=1)).strftime("%Y-%m-%d")
        amount_paise = random.randint(500, 5000) * 100
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        # Bank row 1
        fee_paise = int(amount_paise * 0.005)
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": amount_paise,
            "gross_amount_inr": paise_to_inr_str(amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": amount_paise - fee_paise,
            "narration": f"{rail}-SETTL-{utr}-BATCH1",
        })
        stmt_counter += 1
        
        # Bank row 2 (duplicate credit in bank batch)
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": amount_paise,
            "gross_amount_inr": paise_to_inr_str(amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": amount_paise - fee_paise,
            "narration": f"{rail}-SETTL-{utr}-BATCH2",
        })
        stmt_counter += 1

    # -------------------------------------------------------------
    # 3. ROUNDING DIFFERENCES (40 records)
    # Exact UTR match, but gross amount differs by 1 to 10 paise
    # -------------------------------------------------------------
    for i in range(40):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.randint(2, 25)
        txn_time = datetime(2026, 10, day, 11, 30, 0)
        settle_date = (txn_time + timedelta(days=1)).strftime("%Y-%m-%d")
        
        internal_amount_paise = random.randint(1000, 10000) * 100
        # Drift: between -10 paise and +10 paise, non-zero
        drift_paise = random.choice([-10, -8, -5, -3, -1, 1, 2, 4, 7, 9, 10])
        bank_gross_paise = internal_amount_paise + drift_paise
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": internal_amount_paise,
            "amount_inr": paise_to_inr_str(internal_amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        fee_paise = int(bank_gross_paise * 0.005)
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": bank_gross_paise,
            "gross_amount_inr": paise_to_inr_str(bank_gross_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": bank_gross_paise - fee_paise,
            "narration": f"{rail}-SETTL-{utr}-ROUNDDRIFT",
        })
        stmt_counter += 1

    # -------------------------------------------------------------
    # 4. SUSPECTED INTERNAL DUPLICATES (30 records = 15 pairs)
    # 15 unique UTRs; each appears twice internally (double webhook)
    # Bank has 1 single credit for each UTR (15 bank records)
    # -------------------------------------------------------------
    for i in range(15):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.randint(3, 24)
        txn_time = datetime(2026, 10, day, 14, 0, 0)
        settle_date = (txn_time + timedelta(days=1)).strftime("%Y-%m-%d")
        amount_paise = random.randint(500, 4000) * 100
        
        # Internal Row 1
        txn_id_1 = f"TXN_OCT_{seq_counter:05d}_A"
        internal_records.append({
            "internal_txn_id": txn_id_1,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        # Internal Row 2 (duplicate delivery after 2 seconds)
        txn_id_2 = f"TXN_OCT_{seq_counter:05d}_B"
        internal_records.append({
            "internal_txn_id": txn_id_2,
            "utr_number": utr,
            "timestamp": (txn_time + timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        # Single bank credit for this UTR (held for duplicate)
        fee_paise = int(amount_paise * 0.005)
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": amount_paise,
            "gross_amount_inr": paise_to_inr_str(amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": amount_paise - fee_paise,
            "narration": f"{rail}-SETTL-{utr}",
        })
        stmt_counter += 1

    # -------------------------------------------------------------
    # 5. REFUNDS (30 internal records, 30 matching bank debits)
    # - 15 Valid Linked Refunds
    # - 8 Missing Parent Reference (NULL)
    # - 7 Unresolved Parent Reference (parent not in ledger)
    # -------------------------------------------------------------
    # 5A. 15 Valid Linked Refunds
    for i in range(15):
        parent = clean_settled_txns[i]
        rail = parent["payment_rail"]
        refund_utr = f"REF_{parent['utr_number']}"
        refund_amount = min(parent["amount_paise"], random.randint(200, 2000) * 100)
        day = random.randint(15, 28)
        refund_time = datetime(2026, 10, day, 16, 0, 0)
        settle_date = (refund_time + timedelta(days=1)).strftime("%Y-%m-%d")
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        seq_counter += 1
        
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": refund_utr,
            "timestamp": refund_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": parent["customer_id"],
            "payment_rail": rail,
            "txn_type": "REFUND",
            "amount_paise": refund_amount,
            "amount_inr": paise_to_inr_str(refund_amount),
            "status": "SUCCESS",
            "parent_txn_id": parent["internal_txn_id"],
        })
        
        fee_paise = 50  # 50 paise refund fee
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": refund_utr,
            "settlement_date": settle_date,
            "posting_type": "DEBIT",
            "gross_amount_paise": refund_amount,
            "gross_amount_inr": paise_to_inr_str(refund_amount),
            "fee_paise": fee_paise,
            "net_amount_paise": refund_amount + fee_paise,
            "narration": f"{rail}-REFUND-{refund_utr}",
        })
        stmt_counter += 1

    # 5B. 8 Refunds with Missing Parent Reference (parent_txn_id is None)
    for i in range(8):
        rail = random.choice(PAYMENT_RAILS)
        refund_utr = f"REF_NOPARENT_{generate_utr(rail, seq_counter)}"
        seq_counter += 1
        refund_amount = random.randint(300, 1500) * 100
        day = random.randint(10, 26)
        refund_time = datetime(2026, 10, day, 12, 0, 0)
        settle_date = (refund_time + timedelta(days=1)).strftime("%Y-%m-%d")
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        seq_counter += 1
        
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": refund_utr,
            "timestamp": refund_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "REFUND",
            "amount_paise": refund_amount,
            "amount_inr": paise_to_inr_str(refund_amount),
            "status": "SUCCESS",
            "parent_txn_id": None,  # Intentionally missing
        })
        
        fee_paise = 50
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": refund_utr,
            "settlement_date": settle_date,
            "posting_type": "DEBIT",
            "gross_amount_paise": refund_amount,
            "gross_amount_inr": paise_to_inr_str(refund_amount),
            "fee_paise": fee_paise,
            "net_amount_paise": refund_amount + fee_paise,
            "narration": f"{rail}-REFUND-MISSINGPARENT-{refund_utr}",
        })
        stmt_counter += 1

    # 5C. 7 Refunds with Unresolved Parent Reference (parent_txn_id not in dataset)
    for i in range(7):
        rail = random.choice(PAYMENT_RAILS)
        refund_utr = f"REF_UNRES_{generate_utr(rail, seq_counter)}"
        seq_counter += 1
        refund_amount = random.randint(250, 1800) * 100
        day = random.randint(12, 28)
        refund_time = datetime(2026, 10, day, 15, 0, 0)
        settle_date = (refund_time + timedelta(days=1)).strftime("%Y-%m-%d")
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        seq_counter += 1
        
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": refund_utr,
            "timestamp": refund_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "REFUND",
            "amount_paise": refund_amount,
            "amount_inr": paise_to_inr_str(refund_amount),
            "status": "SUCCESS",
            "parent_txn_id": f"TXN_PRIOR_MONTH_{random.randint(9000, 9999)}",  # Absent from current ledger
        })
        
        fee_paise = 50
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": refund_utr,
            "settlement_date": settle_date,
            "posting_type": "DEBIT",
            "gross_amount_paise": refund_amount,
            "gross_amount_inr": paise_to_inr_str(refund_amount),
            "fee_paise": fee_paise,
            "net_amount_paise": refund_amount + fee_paise,
            "narration": f"{rail}-REFUND-UNRESOLVED-{refund_utr}",
        })
        stmt_counter += 1

    # -------------------------------------------------------------
    # 6. MONTH-END TIMING DELAYS (50 internal records)
    # Authorized Oct 29 - Oct 31
    # - 45 confirmed settled in Nov 01 - Nov 03 bank statement
    # - 5 overdue / unsettled (never settle)
    # -------------------------------------------------------------
    nov_stmt_counter = 1
    for i in range(50):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.choice([29, 30, 31])
        hour = random.randint(10, 23)
        txn_time = datetime(2026, 10, day, hour, 30, 0)
        amount_paise = random.randint(500, 10000) * 100
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })
        
        # First 45 settle in November bank statement
        if i < 45:
            nov_day = random.choice([1, 2, 3])
            nov_settle_date = f"2026-11-{nov_day:02d}"
            fee_paise = int(amount_paise * 0.005)
            bank_nov_records.append({
                "bank_stmt_id": f"STMT_NOV_{nov_stmt_counter:05d}",
                "bank_utr_number": utr,
                "settlement_date": nov_settle_date,
                "posting_type": "CREDIT",
                "gross_amount_paise": amount_paise,
                "gross_amount_inr": paise_to_inr_str(amount_paise),
                "fee_paise": fee_paise,
                "net_amount_paise": amount_paise - fee_paise,
                "narration": f"{rail}-SETTL-LATE-{utr}",
            })
            nov_stmt_counter += 1
        # The remaining 5 records do not settle in November (they become OVERDUE_UNSETTLED_BREAK)

    # -------------------------------------------------------------
    # 7. INTERNAL UNSETTLED BREAKS (30 records)
    # Authorized Oct 05 - Oct 25, past 3-day SLA, never settled in bank
    # -------------------------------------------------------------
    for i in range(30):
        rail = random.choice(PAYMENT_RAILS)
        utr = generate_utr(rail, seq_counter)
        seq_counter += 1
        
        day = random.randint(5, 25)
        txn_time = datetime(2026, 10, day, 10, 15, 0)
        amount_paise = random.randint(500, 6000) * 100
        
        txn_id = f"TXN_OCT_{seq_counter:05d}"
        internal_records.append({
            "internal_txn_id": txn_id,
            "utr_number": utr,
            "timestamp": txn_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "customer_id": f"CUST_IND_{random.randint(1000, 9999)}",
            "payment_rail": rail,
            "txn_type": "PAYMENT",
            "amount_paise": amount_paise,
            "amount_inr": paise_to_inr_str(amount_paise),
            "status": "SUCCESS",
            "parent_txn_id": None,
        })

    # -------------------------------------------------------------
    # 8. ADDITIONAL BANK-SIDE DISCREPANCIES IN OCTOBER (30 records)
    # - 15 Orphan Bank Debits (refund/chargeback debits with no internal record)
    # - 15 Unmatched Bank Credits (unidentified direct customer deposits)
    # -------------------------------------------------------------
    # 8A. 15 Orphan Bank Debits
    for i in range(15):
        rail = random.choice(PAYMENT_RAILS)
        orphan_utr = f"ORPH_DEBIT_{generate_utr(rail, seq_counter)}"
        seq_counter += 1
        
        debit_amount_paise = random.randint(200, 3000) * 100
        settle_date = f"2026-10-{random.randint(10, 28):02d}"
        fee_paise = 50
        
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": orphan_utr,
            "settlement_date": settle_date,
            "posting_type": "DEBIT",
            "gross_amount_paise": debit_amount_paise,
            "gross_amount_inr": paise_to_inr_str(debit_amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": debit_amount_paise + fee_paise,
            "narration": f"BANK-CHARGEBACK-ORPHAN-{orphan_utr}",
        })
        stmt_counter += 1

    # 8B. 15 Unmatched Bank Credits
    for i in range(15):
        rail = random.choice(["IMPS", "NEFT", "UPI"])
        surplus_utr = f"SURPLUS_CREDIT_{generate_utr(rail, seq_counter)}"
        seq_counter += 1
        
        credit_amount_paise = random.randint(1000, 20000) * 100
        settle_date = f"2026-10-{random.randint(5, 28):02d}"
        fee_paise = 0
        
        bank_oct_records.append({
            "bank_stmt_id": f"STMT_OCT_{stmt_counter:05d}",
            "bank_utr_number": surplus_utr,
            "settlement_date": settle_date,
            "posting_type": "CREDIT",
            "gross_amount_paise": credit_amount_paise,
            "gross_amount_inr": paise_to_inr_str(credit_amount_paise),
            "fee_paise": fee_paise,
            "net_amount_paise": credit_amount_paise,
            "narration": f"DIRECT-CUSTOMER-DEPOSIT-{surplus_utr}",
        })
        stmt_counter += 1

    # Convert to DataFrames
    df_internal = pd.DataFrame(internal_records)
    df_bank_oct = pd.DataFrame(bank_oct_records)
    df_bank_nov = pd.DataFrame(bank_nov_records)

    # Save CSVs
    df_internal.to_csv(INTERNAL_TRANSACTIONS_OCTOBER, index=False)
    df_bank_oct.to_csv(BANK_SETTLEMENTS_OCTOBER, index=False)
    df_bank_nov.to_csv(BANK_SETTLEMENTS_NOVEMBER, index=False)

    print(f"Generated internal_transactions_october.csv with {len(df_internal)} records.")
    print(f"Generated bank_settlements_october.csv with {len(df_bank_oct)} records.")
    print(f"Generated bank_settlements_november.csv with {len(df_bank_nov)} records.")
    
    return df_internal, df_bank_oct, df_bank_nov


if __name__ == "__main__":
    generate_synthetic_data()
