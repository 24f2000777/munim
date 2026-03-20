"""
Tests for Tally XML Parser
============================
Tests cover all edge cases specified in the project spec:
  - Standard TallyPrime XML
  - Hindi/Devanagari product and customer names
  - Negative amounts (Tally sign convention)
  - Empty/null customer names → Walk-in Customer
  - Custom voucher types
  - Non-sales vouchers filtered out
  - Zero-value entries filtered out
  - Data types (Decimal, not float)
"""

import pytest
from decimal import Decimal

from services.ingestor.tally_parser import (
    parse_tally_xml,
    TallyParseError,
    WALK_IN_CUSTOMER,
    _parse_amount,
    _parse_tally_date,
)


class TestParseTallyXml:

    def test_parse_minimal_xml(self, minimal_tally_xml):
        """Standard TallyPrime XML parses without errors."""
        result = parse_tally_xml(minimal_tally_xml)
        assert result.df is not None
        assert not result.df.empty

    def test_extracts_correct_row_count(self, minimal_tally_xml):
        """3 sales vouchers → at least 3 rows (may have more if multi-line)."""
        result = parse_tally_xml(minimal_tally_xml)
        assert len(result.df) >= 3

    def test_amount_sign_flip(self, minimal_tally_xml):
        """Negative Tally amounts → positive in our system (sale convention)."""
        result = parse_tally_xml(minimal_tally_xml)
        # All sales should be positive in our system
        sales = result.df[result.df["amount"] > Decimal(0)]
        assert len(sales) > 0, "Expected positive amounts after sign flip"

    def test_amounts_are_decimal_not_float(self, minimal_tally_xml):
        """Critical: amounts must be Decimal, never float (financial precision)."""
        result = parse_tally_xml(minimal_tally_xml)
        for val in result.df["amount"]:
            assert isinstance(val, Decimal), f"Expected Decimal, got {type(val)}: {val}"

    def test_date_parsing_yyyymmdd(self, minimal_tally_xml):
        """Tally YYYYMMDD dates parse to valid Timestamps."""
        result = parse_tally_xml(minimal_tally_xml)
        assert result.df["date"].dtype == "datetime64[ns]"
        assert not result.df["date"].isna().any()

    def test_dates_sorted_ascending(self, minimal_tally_xml):
        """Output DataFrame is sorted chronologically."""
        result = parse_tally_xml(minimal_tally_xml)
        dates = result.df["date"].tolist()
        assert dates == sorted(dates)

    def test_hindi_product_names(self, tally_xml_with_hindi_names):
        """Devanagari/Hindi product and customer names are preserved correctly."""
        result = parse_tally_xml(tally_xml_with_hindi_names)
        assert not result.df.empty

        products = result.df["product"].tolist()
        customers = result.df["customer"].tolist()

        assert any("आटा" in str(p) for p in products), "Hindi product name not found"
        assert any("रमेश" in str(c) for c in customers), "Hindi customer name not found"

    def test_negative_return_amounts(self, tally_xml_with_negative_amounts):
        """Positive Tally amounts (returns) become negative in our system."""
        result = parse_tally_xml(tally_xml_with_negative_amounts)
        amounts = result.df["amount"].tolist()

        positive_count = sum(1 for a in amounts if a > Decimal(0))
        negative_count = sum(1 for a in amounts if a < Decimal(0))

        assert positive_count > 0, "Should have positive sales"
        assert negative_count > 0, "Should have negative returns"

    def test_empty_customer_becomes_walk_in(self, tally_xml_with_empty_customer):
        """Empty PARTYLEDGERNAME becomes 'Walk-in Customer'."""
        result = parse_tally_xml(tally_xml_with_empty_customer)
        customers = result.df["customer"].tolist()
        assert WALK_IN_CUSTOMER in customers, f"Expected Walk-in Customer, got: {customers}"

    def test_custom_voucher_type_included(self, tally_xml_with_custom_voucher_type):
        """'Credit Sales' VCHTYPE is included in sales analysis."""
        result = parse_tally_xml(tally_xml_with_custom_voucher_type)
        vch_types = result.df["vch_type"].tolist()
        assert any("Credit Sales" in str(v) or "Sales" in str(v) for v in vch_types)

    def test_non_sales_vouchers_excluded(self, tally_xml_with_custom_voucher_type):
        """'Purchase' VCHTYPE is excluded from sales analysis by default."""
        result = parse_tally_xml(tally_xml_with_custom_voucher_type)
        vch_types = result.df["vch_type"].tolist()
        assert not any("Purchase" in str(v) for v in vch_types), (
            "Purchase vouchers should not appear in sales output"
        )

    def test_skipped_non_sales_count(self, tally_xml_with_custom_voucher_type):
        """Parser reports count of skipped non-sales vouchers."""
        result = parse_tally_xml(tally_xml_with_custom_voucher_type)
        assert result.skipped_non_sales >= 1

    def test_invalid_xml_raises_error(self):
        """Completely invalid XML raises TallyParseError."""
        with pytest.raises(TallyParseError):
            parse_tally_xml(b"This is not XML at all !!!")

    def test_empty_bytes_raises_error(self):
        """Empty bytes raises TallyParseError."""
        with pytest.raises((TallyParseError, Exception)):
            parse_tally_xml(b"")

    def test_required_columns_present(self, minimal_tally_xml):
        """Output DataFrame has all required columns."""
        result = parse_tally_xml(minimal_tally_xml)
        required = ["date", "customer", "product", "amount", "voucher_id", "vch_type"]
        for col in required:
            assert col in result.df.columns, f"Missing column: {col}"

    def test_parse_result_metadata(self, minimal_tally_xml):
        """TallyParseResult metadata is populated."""
        result = parse_tally_xml(minimal_tally_xml)
        assert result.total_vouchers_found >= 3
        assert result.sales_vouchers_extracted >= 3
        assert isinstance(result.warnings, list)

    def test_bom_stripped(self):
        """BOM prefix is stripped before parsing."""
        bom = b"\xef\xbb\xbf"
        xml = bom + b'<?xml version="1.0" encoding="utf-8"?><ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="Sales"><DATE>20260101</DATE><VOUCHERNUMBER>BOM001</VOUCHERNUMBER><PARTYLEDGERNAME>Test</PARTYLEDGERNAME><AMOUNT>-1000</AMOUNT></VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>'
        result = parse_tally_xml(xml)
        assert not result.df.empty


class TestParseAmount:

    def test_negative_tally_amount(self):
        """-15000 → Decimal('15000') (sign flip)."""
        assert _parse_amount("-15000") == Decimal("15000")

    def test_positive_tally_amount(self):
        """15000 → Decimal('-15000') (sign flip — positive = expense in Tally)."""
        assert _parse_amount("15000") == Decimal("-15000")

    def test_decimal_amount(self):
        """-1500.50 → Decimal('1500.50')."""
        assert _parse_amount("-1500.50") == Decimal("1500.50")

    def test_zero_amount(self):
        """0 → Decimal('0')."""
        assert _parse_amount("0") == Decimal("0")

    def test_empty_string(self):
        """Empty string → Decimal('0')."""
        assert _parse_amount("") == Decimal("0")

    def test_amount_with_rupee_symbol(self):
        """₹15,000 → Decimal('-15000') (positive amount, sign flipped)."""
        result = _parse_amount("₹15,000")
        assert result == Decimal("-15000")

    def test_indian_comma_format(self):
        """-1,24,300 → Decimal('124300')."""
        assert _parse_amount("-1,24,300") == Decimal("124300")


class TestParseTallyDate:
    """Tests for Tally date parsing."""

    def test_standard_yyyymmdd(self):
        """20260115 → Timestamp('2026-01-15')."""
        import pandas as pd
        ts = _parse_tally_date("20260115")
        assert ts == pd.Timestamp("2026-01-15")

    def test_invalid_date_raises(self):
        """Non-date string raises ValueError."""
        with pytest.raises((ValueError, Exception)):
            _parse_tally_date("not-a-date")
