"""Global Configuration & Constants for Payment Reconciliation System."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# File Paths
INTERNAL_TRANSACTIONS_OCTOBER = DATA_DIR / "internal_transactions_october.csv"
BANK_SETTLEMENTS_OCTOBER = DATA_DIR / "bank_settlements_october.csv"
BANK_SETTLEMENTS_NOVEMBER = DATA_DIR / "bank_settlements_november.csv"
RECONCILED_REPORT_CSV = OUTPUT_DIR / "reconciliation_audit_report.csv"

# Financial Precision & Tolerances
# All calculations are in integer paise (1 INR = 100 paise)
ROUNDING_TOLERANCE_PAISE = 10  # Up to 10 paise (₹0.10) is categorized as rounding variance

# SLA & Timing Configurations
SLA_BUSINESS_DAYS = 3  # Standard 3 business days for settlement
OCTOBER_CUTOFF_DATE = "2026-10-31 23:59:59+05:30"
NOVEMBER_VERIFICATION_DATE = "2026-11-05 23:59:59+05:30"

# Indian Banking Holidays in October/November 2026 (YYYY-MM-DD)
# Oct 02: Mahatma Gandhi Jayanti
# Oct 20: Dussehra / Vijayadashami
BANK_HOLIDAYS = [
    "2026-10-02",
    "2026-10-20",
]

# Random Seed for Reproducible Synthetic Generation
RANDOM_SEED = 42

# Payment Rails
PAYMENT_RAILS = ["UPI", "IMPS", "NEFT", "CARD"]
