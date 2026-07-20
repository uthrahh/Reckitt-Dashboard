"""
main.py

Pipeline orchestrator / entrypoint. Wires together ingestion -> validation
-> cleaning -> feature engineering -> star schema modeling -> curated
write-out, with a production-style formatted execution log at every stage.

WHY A SEPARATE ORCHESTRATOR (vs logic inline here):
main.py contains ZERO transformation logic — it only sequences calls to
tested modules, times each stage, and reports results. This keeps the
orchestration layer thin and makes each stage swappable (e.g. replacing
the CSV source with a JDBC source only touches data_loader.py, nothing
else).

USAGE:
    python main.py
    python main.py --config config/config.yaml
"""

import argparse
import os
import sys
import time

import yaml

from src.ingestion.data_loader import load_raw_sales_data
from src.validation.data_quality import run_validation
from src.transformation.cleaning import run_cleaning_pipeline
from src.transformation.feature_engineering import run_feature_engineering
from src.modeling.star_schema_builder import build_star_schema
from src.utils.spark_session import get_spark_session
from src.utils.logger import get_logger
from src.utils.report import print_section, print_kv, print_subsection, print_close, format_bytes

logger = get_logger(__name__)


def load_config(config_path: str) -> dict:
    """Loads the YAML pipeline configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def write_curated_tables(tables: dict, curated_dir: str) -> dict:
    """
    Persists every fact/dim table to the curated zone as a single flat
    CSV file per table (curated/fact_sales.csv, curated/dim_date.csv, ...).

    NOTE: Uses pandas' `.to_csv()` rather than Spark's native
    `.write.csv()` / `.write.parquet()`. Both of those route through
    Hadoop's NativeIO layer, which requires winutils.exe on Windows and
    throws UnsatisfiedLinkError without it. Each curated DataFrame is
    collected to the driver via `.toPandas()` and written with
    pandas — no Hadoop dependency. Safe here because every curated table
    (fact + dims) is small enough to fit in driver memory; it would not
    be the right approach at true big-data volume, where the Spark-native
    writer (with winutils configured) is the correct choice.

    Returns:
        Dict of {table_name: {"rows": int, "size_bytes": int, "path": str}}
        for the export log section.
    """
    os.makedirs(curated_dir, exist_ok=True)
    export_stats = {}

    for name, df in tables.items():
        out_path = os.path.join(curated_dir, f"{name}.csv")
        pdf = df.toPandas()
        pdf.to_csv(out_path, index=False, header=True)

        export_stats[name] = {
            "rows": len(pdf),
            "size_bytes": os.path.getsize(out_path),
            "path": os.path.abspath(out_path),
        }
        logger.info(f"Wrote {name} -> {out_path}")

    return export_stats


def run_pipeline(config_path: str) -> int:
    """
    Executes the full ETL pipeline end-to-end with a formatted,
    stage-by-stage production log.

    Returns:
        Process exit code (0 = success, 1 = failure).
    """
    config = load_config(config_path)
    spark = get_spark_session(
        app_name=config["spark"]["app_name"],
        master=config["spark"]["master"],
        shuffle_partitions=config["spark"]["shuffle_partitions"],
    )

    stage_timings = {}
    pipeline_start = time.perf_counter()

    try:
        # ============================================================
        # INGESTION
        # ============================================================
        stage_start = time.perf_counter()
        raw_df = load_raw_sales_data(spark, config["paths"]["raw_data"])
        rows_loaded = raw_df.count()
        stage_timings["Ingestion"] = time.perf_counter() - stage_start

        print_section("INGESTION")
        print_kv("File Loaded", config["paths"]["raw_data"])
        print_kv("Rows Loaded", f"{rows_loaded:,}")
        print_kv("Columns", len(raw_df.columns))
        print_kv("Time", f"{stage_timings['Ingestion']:.2f} sec")
        print_close()

        # ============================================================
        # VALIDATION
        # ============================================================
        stage_start = time.perf_counter()
        report = run_validation(
            raw_df, max_allowed_null_pct=config["data_quality"]["max_allowed_null_pct"]
        )
        stage_timings["Validation"] = time.perf_counter() - stage_start

        print_section("DATA VALIDATION")
        print_kv("Rows Checked", f"{report.total_rows:,}")
        print_kv("Duplicate Rows", f"{report.duplicate_row_count:,}")
        print_subsection("Missing Values Per Column")
        for col, count in report.null_count_by_column.items():
            if count > 0:
                pct = report.null_pct_by_column.get(col, 0.0)
                print(f"  {col} : {count:,} ({pct}%)")
        print_kv(
            "\nColumns Exceeding Null Threshold",
            report.columns_exceeding_null_threshold or "None",
        )
        print_kv("Validation Passed", "Yes" if report.passed else "No (warnings only, proceeding)")
        print_kv("Time", f"{stage_timings['Validation']:.2f} sec")
        print_close()

        if report.has_critical_issues():
            logger.warning(
                "Proceeding despite null-threshold warnings — WAREHOUSE_ID nulls "
                "are a known, handled case (see cleaning.py)."
            )

        # ============================================================
        # CLEANING
        # ============================================================
        stage_start = time.perf_counter()
        clean_df, clean_metrics = run_cleaning_pipeline(
            raw_df, warehouse_fill_value=config["cleaning"]["warehouse_id_fill_value"]
        )
        clean_df.cache()  # reused across feature engineering + multiple dim builds below
        stage_timings["Cleaning"] = time.perf_counter() - stage_start

        print_section("DATA CLEANING")
        print_kv("Duplicate Rows Removed", f"{clean_metrics['duplicates_removed']:,}")
        print_kv("Rows Before", f"{clean_metrics['rows_before']:,}")
        print_kv("Rows After", f"{clean_metrics['rows_after']:,}")
        print_subsection("Invalid Numeric Values")
        for col, count in clean_metrics["invalid_numeric"].items():
            print(f"  {col} : {count:,}")
        print_subsection("Null Values Filled")
        for col, count in clean_metrics["nulls_filled"].items():
            print(f"  {col} : {count:,}")
        print_kv("\nRows Dropped", f"{clean_metrics['rows_dropped']:,}")
        print_kv("Cleaning Completed", "Yes")
        print_kv("Time", f"{stage_timings['Cleaning']:.2f} sec")
        print_close()

        # ============================================================
        # FEATURE ENGINEERING
        # ============================================================
        stage_start = time.perf_counter()
        enriched_df, features_added = run_feature_engineering(clean_df)
        stage_timings["Feature Engineering"] = time.perf_counter() - stage_start

        print_section("FEATURE ENGINEERING")
        print_subsection("Columns Added")
        for feature in features_added:
            print(f"  {feature['name']}")
            print(f"    Formula: {feature['formula']}")
        print_kv("\nTotal New Columns", len(features_added))
        print_kv("Feature Engineering Completed", "Yes")
        print_kv("Time", f"{stage_timings['Feature Engineering']:.2f} sec")
        print_close()

        # ============================================================
        # STAR SCHEMA (includes dimension-uniqueness validation, which
        # prints its own "CHECKING DIMENSION UNIQUENESS" block and raises
        # before any join if a dimension has duplicate natural keys)
        # ============================================================
        stage_start = time.perf_counter()
        curated_tables = build_star_schema(enriched_df)
        stage_timings["Star Schema"] = time.perf_counter() - stage_start

        dim_names = [n for n in curated_tables if n != "fact_sales"]

        print_section("STAR SCHEMA")
        print_subsection("Dimension Tables")
        for name in dim_names:
            print(f"  {name}")
            print(f"    Rows : {curated_tables[name].count():,}")
        print_subsection("Fact Table")
        print(f"  fact_sales")
        print(f"    Rows : {curated_tables['fact_sales'].count():,}")
        print_subsection("Relationships")
        print("  fact_sales")
        for name in dim_names:
            print(f"    -> {name}")
        print_kv("\nStar Schema Completed", "Yes")
        print_kv("Time", f"{stage_timings['Star Schema']:.2f} sec")
        print_close()

        # ============================================================
        # EXPORT
        # ============================================================
        stage_start = time.perf_counter()
        curated_dir = config["paths"]["curated_dir"]
        export_stats = write_curated_tables(curated_tables, curated_dir)
        stage_timings["Export"] = time.perf_counter() - stage_start

        print_section("EXPORT")
        for name, stats in export_stats.items():
            print(f"  {name}.csv")
            print(f"    Rows Written : {stats['rows']:,}")
            print(f"    File Size    : {format_bytes(stats['size_bytes'])}")
            print(f"    Location     : {stats['path']}")
        print_kv("\nFiles Exported", len(export_stats))
        print_kv("Output Folder", os.path.abspath(curated_dir))
        print_kv("Export Completed", "Yes")
        print_kv("Time", f"{stage_timings['Export']:.2f} sec")
        print_close()

        clean_df.unpersist()

        # ============================================================
        # EXECUTION TIMING SUMMARY
        # ============================================================
        total_time = time.perf_counter() - pipeline_start
        print_section("EXECUTION TIMING")
        for stage, elapsed in stage_timings.items():
            print(f"  {stage:.<30} {elapsed:.2f} sec")
        print(f"  {'Total Pipeline Time':.<30} {total_time:.2f} sec")
        print_close()

        # ============================================================
        # DATA QUALITY REPORT
        # ============================================================
        total_invalid_numeric = sum(clean_metrics["invalid_numeric"].values())
        total_nulls_filled = sum(clean_metrics["nulls_filled"].values())

        print_section("DATA QUALITY REPORT")
        print_kv("Rows Loaded", f"{rows_loaded:,}")
        print_kv("Rows After Cleaning", f"{clean_metrics['rows_after']:,}")
        print_kv("Duplicates Removed", f"{clean_metrics['duplicates_removed']:,}")
        print_kv("Rows Dropped", f"{clean_metrics['rows_dropped']:,}")
        print_kv("Null Values Filled", f"{total_nulls_filled:,}")
        print_kv("Invalid Numeric Values Corrected", f"{total_invalid_numeric:,}")
        print_kv("Dimension Tables Created", len(dim_names))
        print_kv("Fact Tables Created", 1)
        print_kv("Files Exported", len(export_stats))
        print_kv("Pipeline Status", "SUCCESS")
        print_close()

        logger.info("Pipeline completed successfully.")
        return 0

    except Exception:
        logger.exception("Pipeline failed with an unhandled exception.")
        return 1

    finally:
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reckitt FMCG Sales ETL Pipeline")
    parser.add_argument(
        "--config", default="config/config.yaml", help="Path to pipeline config YAML"
    )
    args = parser.parse_args()

    exit_code = run_pipeline(args.config)
    sys.exit(exit_code)
