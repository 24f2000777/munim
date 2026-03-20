"""
Test Fixtures and Shared Configuration
========================================
Provides synthetic Tally XML, Excel data, and DataFrames for testing.
All test data is synthetic — no real business data is ever used in tests.
"""

import textwrap
from decimal import Decimal
from io import BytesIO

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Synthetic Tally XML fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_tally_xml() -> bytes:
    """Minimal valid TallyPrime XML with 3 sales vouchers."""
    xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <ENVELOPE>
          <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
          </HEADER>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                  <VOUCHER REMOTEID="V001" VCHTYPE="Sales" ACTION="Create">
                    <DATE>20260101</DATE>
                    <VOUCHERNUMBER>S001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Sharma Traders</PARTYLEDGERNAME>
                    <AMOUNT>-15000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Parle-G Biscuit</LEDGERNAME>
                      <AMOUNT>-15000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                  <VOUCHER REMOTEID="V002" VCHTYPE="Sales" ACTION="Create">
                    <DATE>20260108</DATE>
                    <VOUCHERNUMBER>S002</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Gupta General Store</PARTYLEDGERNAME>
                    <AMOUNT>-8500</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Surf Excel</LEDGERNAME>
                      <AMOUNT>-8500</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                  <VOUCHER REMOTEID="V003" VCHTYPE="Sales" ACTION="Create">
                    <DATE>20260115</DATE>
                    <VOUCHERNUMBER>S003</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Walk-in</PARTYLEDGERNAME>
                    <AMOUNT>-2300</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Parle-G Biscuit</LEDGERNAME>
                      <AMOUNT>-2300</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
    """).encode("utf-8")
    return xml


@pytest.fixture
def tally_xml_with_hindi_names() -> bytes:
    """Tally XML with Devanagari (Hindi) product and customer names."""
    xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <ENVELOPE>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                  <VOUCHER VCHTYPE="Sales">
                    <DATE>20260110</DATE>
                    <VOUCHERNUMBER>H001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>रमेश किराना स्टोर</PARTYLEDGERNAME>
                    <AMOUNT>-12000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>आटा (10 किलो)</LEDGERNAME>
                      <AMOUNT>-12000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
    """).encode("utf-8")
    return xml


@pytest.fixture
def tally_xml_with_negative_amounts() -> bytes:
    """Tally XML with returns (amounts that stay negative after sign flip)."""
    xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <ENVELOPE>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                  <VOUCHER VCHTYPE="Sales">
                    <DATE>20260105</DATE>
                    <VOUCHERNUMBER>N001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Test Customer</PARTYLEDGERNAME>
                    <AMOUNT>-5000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Product A</LEDGERNAME>
                      <AMOUNT>-5000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                  <VOUCHER VCHTYPE="Sales">
                    <DATE>20260106</DATE>
                    <VOUCHERNUMBER>N002</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Test Customer</PARTYLEDGERNAME>
                    <AMOUNT>1000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Product A</LEDGERNAME>
                      <AMOUNT>1000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
    """).encode("utf-8")
    return xml


@pytest.fixture
def tally_xml_with_empty_customer() -> bytes:
    """Tally XML with null/empty PARTYLEDGERNAME → should become Walk-in Customer."""
    xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <ENVELOPE>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                  <VOUCHER VCHTYPE="Sales">
                    <DATE>20260110</DATE>
                    <VOUCHERNUMBER>W001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME></PARTYLEDGERNAME>
                    <AMOUNT>-3000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Mixed Items</LEDGERNAME>
                      <AMOUNT>-3000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
    """).encode("utf-8")
    return xml


@pytest.fixture
def tally_xml_with_custom_voucher_type() -> bytes:
    """Tally XML with non-standard VCHTYPE (e.g. 'Credit Sales')."""
    xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <ENVELOPE>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                  <VOUCHER VCHTYPE="Credit Sales">
                    <DATE>20260112</DATE>
                    <VOUCHERNUMBER>CS001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Wholesale Client</PARTYLEDGERNAME>
                    <AMOUNT>-45000</AMOUNT>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Bulk Rice 50kg</LEDGERNAME>
                      <AMOUNT>-45000</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                  <VOUCHER VCHTYPE="Purchase">
                    <DATE>20260113</DATE>
                    <VOUCHERNUMBER>P001</VOUCHERNUMBER>
                    <PARTYLEDGERNAME>Supplier ABC</PARTYLEDGERNAME>
                    <AMOUNT>30000</AMOUNT>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
    """).encode("utf-8")
    return xml


# ---------------------------------------------------------------------------
# Synthetic DataFrame fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_sales_df() -> pd.DataFrame:
    """
    Clean sales DataFrame with known values for analytics testing.
    Contains 8 weeks of data with controlled patterns.
    """
    from datetime import date, timedelta

    base_date = date(2026, 1, 5)  # Monday

    rows = []
    products = ["Parle-G", "Surf Excel", "Maggi Noodles", "Tata Salt", "Amul Butter"]
    customers = ["Sharma Traders", "Gupta Store", "Patel Kirana", "Singh General", "Walk-in Customer"]

    # Weeks 1–7: normal sales
    for week in range(7):
        for day_offset in range(6):
            tx_date = base_date + timedelta(weeks=week, days=day_offset)
            for i, (product, customer) in enumerate(zip(products, customers)):
                base_amount = Decimal(str((i + 1) * 2000 + week * 100))
                rows.append({
                    "date": pd.Timestamp(tx_date),
                    "customer": customer,
                    "product": product,
                    "amount": base_amount,
                    "voucher_id": f"V{week}{day_offset}{i}",
                    "vch_type": "Sales",
                    "company": "Test Company",
                })

    # Weeks 8–10: "Tata Salt" stops selling (>14 days gap for dead stock test)
    for week in range(7, 10):
        for day_offset in range(6):
            tx_date = base_date + timedelta(weeks=week, days=day_offset)
            for i, (product, customer) in enumerate(zip(products[:4], customers[:4])):
                if product == "Tata Salt":
                    continue  # Skip Tata Salt — creates >14 day gap
                rows.append({
                    "date": pd.Timestamp(tx_date),
                    "customer": customer,
                    "product": product,
                    "amount": Decimal(str((i + 1) * 2000)),
                    "voucher_id": f"V{week}{day_offset}{i}",
                    "vch_type": "Sales",
                    "company": "Test Company",
                })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["customer"] = df["customer"].astype("string")
    df["product"] = df["product"].astype("string")
    return df


@pytest.fixture
def df_with_churn_risk(clean_sales_df) -> pd.DataFrame:
    """DataFrame where 'Patel Kirana' hasn't ordered in 25 days."""
    df = clean_sales_df.copy()
    cutoff = df["date"].max() - pd.Timedelta(days=25)
    df = df[~((df["customer"] == "Patel Kirana") & (df["date"] > cutoff))]
    return df


@pytest.fixture
def df_with_revenue_drop(clean_sales_df) -> pd.DataFrame:
    """DataFrame where last week's revenue is 50% of the previous week."""
    df = clean_sales_df.copy()
    last_week_start = df["date"].max() - pd.Timedelta(days=6)
    # Remove half the transactions in the last week
    last_week_mask = df["date"] >= last_week_start
    last_week_df = df[last_week_mask]
    drop_indices = last_week_df.index[::2]  # Every other row
    df = df.drop(drop_indices)
    return df.reset_index(drop=True)
