"""
test_validation.py

Tests for src.validation.data_quality — verifies duplicate row detection
and null-percentage threshold detection produce correct, structured results.
"""

from src.validation.data_quality import (
    check_duplicate_rows,
    check_null_counts,
    run_validation,
)


class TestCheckDuplicateRows:
    def test_detects_exact_duplicates(self, spark):
        df = spark.createDataFrame(
            [(1, "a"), (1, "a"), (2, "b")], schema=["id", "value"]
        )
        assert check_duplicate_rows(df) == 1

    def test_no_duplicates_returns_zero(self, spark):
        df = spark.createDataFrame([(1, "a"), (2, "b")], schema=["id", "value"])
        assert check_duplicate_rows(df) == 0


class TestCheckNullCounts:
    def test_counts_nulls_per_column(self, spark):
        df = spark.createDataFrame(
            [(1, None), (2, "b"), (None, "c")], schema=["id", "value"]
        )
        counts = check_null_counts(df)
        assert counts["id"] == 1
        assert counts["value"] == 1


class TestRunValidation:
    def test_flags_column_exceeding_threshold(self, spark):
        # 3 of 4 rows null in 'value' -> 75%, well above a 5% threshold.
        df = spark.createDataFrame(
            [(1, None), (2, None), (3, None), (4, "d")], schema=["id", "value"]
        )
        report = run_validation(df, max_allowed_null_pct=5.0)
        assert "value" in report.columns_exceeding_null_threshold
        assert report.has_critical_issues() is True
        assert report.passed is False

    def test_passes_when_under_threshold(self, spark):
        df = spark.createDataFrame([(1, "a"), (2, "b"), (3, "c")], schema=["id", "value"])
        report = run_validation(df, max_allowed_null_pct=5.0)
        assert report.columns_exceeding_null_threshold == []
        assert report.passed is True

    def test_reports_correct_row_count(self, spark):
        df = spark.createDataFrame([(1,), (2,), (3,)], schema=["id"])
        report = run_validation(df)
        assert report.total_rows == 3
