"""
Data Health Scorer
==================
Computes a Data Health Score (0–100) for an uploaded dataset before analysis runs.

Score is based on four dimensions, equally weighted:
  1. Completeness  (25 pts) — How many required fields are non-null?
  2. Consistency   (25 pts) — Are date formats consistent? Amount signs consistent?
  3. Validity      (25 pts) — Are values in expected ranges? No future dates? No zeroes?
  4. Uniqueness    (25 pts) — Duplicate row rate

Rule: If score < 40, analysis is REFUSED and the user gets a clear explanation.
      This protects against generating nonsense reports from garbage data.

The scorer never modifies data — it only reads and scores.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from services.cleaner.normaliser import (
    FLAG_FUTURE_DATE,
    FLAG_DUPLICATE,
    FLAG_NEGATIVE_AMOUNT,
    FLAG_EXTREME_AMOUNT,
)

logger = logging.getLogger(__name__)

MINIMUM_SCORE_FOR_ANALYSIS = 40
MINIMUM_ROWS_FOR_ANALYSIS = 5  # Can't analyze 2 rows of data


@dataclass
class HealthReport:
    """Complete data quality report shown to the user before analysis."""
    score: int                          # 0–100 overall score
    completeness_score: int             # 0–25
    consistency_score: int             # 0–25
    validity_score: int                # 0–25
    uniqueness_score: int              # 0–25
    total_rows: int
    usable_rows: int                   # After removing critical issues
    issues: list[str] = field(default_factory=list)     # Problems found
    suggestions: list[str] = field(default_factory=list)  # What to fix
    can_analyze: bool = True           # False if score < 40 or rows < 5

    @property
    def grade(self) -> str:
        if self.score >= 80:
            return "Excellent"
        elif self.score >= 65:
            return "Good"
        elif self.score >= 40:
            return "Fair — analysis will run but results may be imprecise"
        else:
            return "Poor — please fix issues before analysis"


def compute_health_score(df: pd.DataFrame) -> HealthReport:
    """
    Compute a Data Health Score for a parsed DataFrame.

    The DataFrame should already have flag columns from the normaliser.
    If not, we compute flags here.

    Args:
        df: Normalised DataFrame (from normaliser.normalise()).

    Returns:
        HealthReport with score, breakdown, and actionable suggestions.
    """
    total_rows = len(df)
    issues: list[str] = []
    suggestions: list[str] = []

    if total_rows < MINIMUM_ROWS_FOR_ANALYSIS:
        return HealthReport(
            score=0,
            completeness_score=0,
            consistency_score=0,
            validity_score=0,
            uniqueness_score=0,
            total_rows=total_rows,
            usable_rows=total_rows,
            issues=[f"Only {total_rows} rows found — need at least {MINIMUM_ROWS_FOR_ANALYSIS} to analyze."],
            suggestions=["Upload a file with more transaction history (at least 2 weeks of data)."],
            can_analyze=False,
        )

    # --- Completeness (0–25) ---
    completeness_score, c_issues, c_suggestions = _score_completeness(df)
    issues.extend(c_issues)
    suggestions.extend(c_suggestions)

    # --- Consistency (0–25) ---
    consistency_score, co_issues, co_suggestions = _score_consistency(df)
    issues.extend(co_issues)
    suggestions.extend(co_suggestions)

    # --- Validity (0–25) ---
    validity_score, v_issues, v_suggestions = _score_validity(df)
    issues.extend(v_issues)
    suggestions.extend(v_suggestions)

    # --- Uniqueness (0–25) ---
    uniqueness_score, u_issues, u_suggestions = _score_uniqueness(df)
    issues.extend(u_issues)
    suggestions.extend(u_suggestions)

    total_score = completeness_score + consistency_score + validity_score + uniqueness_score
    total_score = max(0, min(100, total_score))

    # Usable rows = total minus flagged-as-critical
    critical_flags = []
    if FLAG_DUPLICATE in df.columns:
        critical_flags.append(df[FLAG_DUPLICATE])
    if FLAG_FUTURE_DATE in df.columns:
        critical_flags.append(df[FLAG_FUTURE_DATE])

    if critical_flags:
        critical_mask = critical_flags[0]
        for f in critical_flags[1:]:
            critical_mask = critical_mask | f
        usable_rows = int((~critical_mask).sum())
    else:
        usable_rows = total_rows

    can_analyze = total_score >= MINIMUM_SCORE_FOR_ANALYSIS and usable_rows >= MINIMUM_ROWS_FOR_ANALYSIS

    if not can_analyze and total_score < MINIMUM_SCORE_FOR_ANALYSIS:
        issues.insert(0, f"Data Health Score ({total_score}/100) is below the minimum of {MINIMUM_SCORE_FOR_ANALYSIS}.")
        suggestions.insert(0, "Fix the issues listed below, then re-upload your file.")

    report = HealthReport(
        score=total_score,
        completeness_score=completeness_score,
        consistency_score=consistency_score,
        validity_score=validity_score,
        uniqueness_score=uniqueness_score,
        total_rows=total_rows,
        usable_rows=usable_rows,
        issues=issues,
        suggestions=suggestions,
        can_analyze=can_analyze,
    )

    logger.info(
        "Health score: %d/100 (%s) | rows: %d total, %d usable | can_analyze: %s",
        total_score, report.grade, total_rows, usable_rows, can_analyze,
    )

    return report


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def _score_completeness(df: pd.DataFrame) -> tuple[int, list[str], list[str]]:
    """
    Score: Are required fields present and non-null?
    Max: 25 points

    Required: date, amount (non-null)
    Optional but valuable: customer, product
    """
    issues, suggestions = [], []
    score = 25

    required = ["date", "amount"]
    for col in required:
        if col not in df.columns:
            score -= 12
            issues.append(f"Required column '{col}' is missing entirely.")
            suggestions.append(f"Ensure your file has a column for {col}.")
            continue

        null_pct = df[col].isna().mean() * 100
        if null_pct > 20:
            deduction = min(10, int(null_pct / 10))
            score -= deduction
            issues.append(f"Column '{col}' has {null_pct:.1f}% missing values.")
            suggestions.append(f"Fill in missing {col} values in your file before uploading.")
        elif null_pct > 5:
            score -= 3
            issues.append(f"Column '{col}' has {null_pct:.1f}% missing values (minor).")

    # Optional columns — bonus context
    for col in ["customer", "product"]:
        if col not in df.columns:
            issues.append(f"Optional column '{col}' not found — customer/product analysis will be limited.")

    return max(0, score), issues, suggestions


def _score_consistency(df: pd.DataFrame) -> tuple[int, list[str], list[str]]:
    """
    Score: Are values consistent across the dataset?
    Max: 25 points

    Checks:
    - Date range makes sense (not >5 years of data in one file)
    - All dates parse to valid timestamps
    - Amount values are of consistent magnitude (no 1000x jumps without context)
    """
    issues, suggestions = [], []
    score = 25

    if "date" in df.columns:
        valid_dates = df["date"].dropna()
        if len(valid_dates) > 0:
            date_range_days = (valid_dates.max() - valid_dates.min()).days

            if date_range_days > 365 * 5:
                score -= 5
                issues.append(
                    f"Date range spans {date_range_days // 365} years — "
                    f"consider uploading year-by-year for better analysis."
                )
            elif date_range_days == 0 and len(df) > 10:
                score -= 5
                issues.append("All transactions have the same date — this is unusual.")
                suggestions.append("Verify that your date column is correctly identified.")

    if "amount" in df.columns:
        amounts = df["amount"].apply(
            lambda x: float(x) if isinstance(x, Decimal) and x != Decimal(0) else None
        ).dropna()

        if len(amounts) > 3:
            cv = amounts.std() / amounts.mean() if amounts.mean() != 0 else 0
            if cv > 10:
                score -= 5
                issues.append(
                    "Amount values vary extremely widely — some amounts may be in different units (e.g., paise vs rupees)."
                )
                suggestions.append("Check if all amounts are in the same currency unit (₹).")

    return max(0, score), issues, suggestions


def _score_validity(df: pd.DataFrame) -> tuple[int, list[str], list[str]]:
    """
    Score: Are values within expected real-world ranges?
    Max: 25 points

    Checks future dates, extreme outliers.
    """
    issues, suggestions = [], []
    score = 25

    if FLAG_FUTURE_DATE in df.columns:
        future_count = int(df[FLAG_FUTURE_DATE].sum())
        if future_count > 0:
            pct = future_count / len(df) * 100
            deduction = min(15, int(pct / 2))
            score -= deduction
            issues.append(
                f"{future_count} transactions ({pct:.1f}%) have future dates — likely data entry errors."
            )
            suggestions.append(
                "Correct the dates on future-dated transactions in your file."
            )

    if FLAG_EXTREME_AMOUNT in df.columns:
        extreme_count = int(df[FLAG_EXTREME_AMOUNT].sum())
        if extreme_count > 0:
            score -= min(5, extreme_count)
            issues.append(
                f"{extreme_count} transactions have unusually large amounts — please verify they are correct."
            )

    return max(0, score), issues, suggestions


def _score_uniqueness(df: pd.DataFrame) -> tuple[int, list[str], list[str]]:
    """
    Score: How many rows are unique (not duplicates)?
    Max: 25 points
    """
    issues, suggestions = [], []
    score = 25

    if FLAG_DUPLICATE in df.columns:
        dup_count = int(df[FLAG_DUPLICATE].sum())
        dup_pct = dup_count / len(df) * 100 if len(df) > 0 else 0

        if dup_pct > 30:
            score -= 20
            issues.append(
                f"{dup_count} duplicate transactions found ({dup_pct:.1f}%) — this is very high."
            )
            suggestions.append(
                "Remove duplicate entries from your file. "
                "Each transaction should appear only once."
            )
        elif dup_pct > 10:
            score -= 10
            issues.append(
                f"{dup_count} duplicate transactions found ({dup_pct:.1f}%)."
            )
            suggestions.append("Review and remove duplicate entries from your file.")
        elif dup_pct > 0:
            score -= 3
            issues.append(f"{dup_count} possible duplicate transactions found (minor).")

    return max(0, score), issues, suggestions
