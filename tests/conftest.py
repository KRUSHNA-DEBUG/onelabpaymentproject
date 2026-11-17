"""Pytest Shared Fixtures and Mock Builders."""

import pytest
import pandas as pd
from src.config import (
    INTERNAL_TRANSACTIONS_OCTOBER,
    BANK_SETTLEMENTS_OCTOBER,
    BANK_SETTLEMENTS_NOVEMBER,
)


@pytest.fixture
def generated_datasets():
    """Load the full generated synthetic datasets."""
    df_int = pd.read_csv(INTERNAL_TRANSACTIONS_OCTOBER)
    df_oct = pd.read_csv(BANK_SETTLEMENTS_OCTOBER)
    df_nov = pd.read_csv(BANK_SETTLEMENTS_NOVEMBER)
    return df_int, df_oct, df_nov
