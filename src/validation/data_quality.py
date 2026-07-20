"""
data_quality.py

Reusable data quality validation functions. WHY SEPARATE FROM CLEANING:
validation should *observe and report*, cleaning should *fix*. Conflating
them makes it impossible to answer "how bad was the raw data?" after the
fact, which matters for data quality trend monitoring and stakeholder
trust in the pipeline.

Each check returns a structured result rather than raising immediately,
so main.py can decide whether to fail-fast or continue-with-warnings
based on business context (configurable via config.yaml thresholds).
"""

from dataclasses import dataclass, field
from typing import Dict, List

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DataQualityReport:
    """Structured result of a validation run — machine-readable and loggable."""
    total_rows: int
    null_pct_by_column: Dict[str, float] = field(default_factory=dict)
    null_count_by_column: Dict[str, int] = field(default_factory=dict)
    duplicate_row_count: int = 0
    columns_exceeding_null_threshold: List[str] = field(default_factory=list)

    def has_critical_issues(self) -> bool:
        return len(self.columns_exceeding_null_threshold) > 0

    @property
    def passed(self) -> bool:
        return not self.has_critical_issues()


def check_null_counts(df: DataFrame) -> Dict[str, int]:
    """
    Computes null count per column in a single pass (avoids the
    anti-pattern of looping .filter().count() per column, which would
    trigger N separate full-table scans).

    Args:
        df: Input DataFrame.

    Returns:
        Dict mapping column name -> raw null count.
    """
    if df.count() == 0:
        return {c: 0 for c in df.columns}

    agg_exprs = [
        F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c)
        for c in df.columns
    ]
    return df.agg(*agg_exprs).collect()[0].asDict()


def check_duplicate_rows(df: DataFrame) -> int:
    """Counts fully duplicate rows across all columns."""
    total = df.count()
    distinct = df.distinct().count()
    return total - distinct


def run_validation(df: DataFrame, max_allowed_null_pct: float = 5.0) -> DataQualityReport:
    """
    Executes the full validation suite and returns a structured report.

    Args:
        df: DataFrame to validate (typically post-ingestion, pre-cleaning).
        max_allowed_null_pct: Any column exceeding this is flagged as critical.

    Returns:
        DataQualityReport summarizing findings.
    """
    logger.info("Running data quality validation...")

    total_rows = df.count()
    null_counts = check_null_counts(df)
    null_pcts = (
        {col: round((count / total_rows) * 100, 2) for col, count in null_counts.items()}
        if total_rows > 0 else {col: 0.0 for col in null_counts}
    )
    dup_count = check_duplicate_rows(df)

    breaching_cols = [
        col for col, pct in null_pcts.items() if pct > max_allowed_null_pct
    ]

    report = DataQualityReport(
        total_rows=total_rows,
        null_pct_by_column=null_pcts,
        null_count_by_column=null_counts,
        duplicate_row_count=dup_count,
        columns_exceeding_null_threshold=breaching_cols,
    )

    logger.info(f"Validation complete: {total_rows:,} rows, {dup_count:,} duplicate rows.")
    if report.has_critical_issues():
        logger.warning(f"Columns exceeding {max_allowed_null_pct}% null threshold: {breaching_cols}")
    else:
        logger.info("No columns exceed the configured null threshold.")

    return report
