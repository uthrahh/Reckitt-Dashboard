"""
test_pipeline.py

End-to-end integration test for main.run_pipeline — verifies the full
ingestion -> validation -> cleaning -> feature engineering -> star schema
-> export flow runs successfully against a small real CSV file and
produces the expected curated output files.
"""

import os

import pandas as pd
import pytest
import yaml
from pyspark.sql import SparkSession

from config.schema_config import RAW_SCHEMA
from main import run_pipeline

_HEADER = ",".join(f.name for f in RAW_SCHEMA.fields)

_ROWS = [
    "1,Jan,2022,Retail,Cat A,Seg 1,Reckitt,Brand X,1111111111,100,ML,"
    "1000,50,North,State1,City1,S001,P001,SUP1,DC1,Modern Trade,B1,L1,5,"
    "WH1,In Stock,Completed,POS,2024-01-01T00:00:00",
    # dirty numeric placeholder — regression case for the SparkNumberFormatException fix
    "2,Feb,2022,Wholesale,Cat B,Seg 2,Reckitt,Brand Y,2222222222,200,GR,"
    "-,30,South,State2,City2,S002,P002,SUP2,DC2,General Trade,B2,L2,10,"
    "WH2,Low Stock,Pending,POS,2024-01-01T00:00:00",
    # exact duplicate of row 1 — regression case for dedup
    "1,Jan,2022,Retail,Cat A,Seg 1,Reckitt,Brand X,1111111111,100,ML,"
    "1000,50,North,State1,City1,S001,P001,SUP1,DC1,Modern Trade,B1,L1,5,"
    "WH1,In Stock,Completed,POS,2024-01-01T00:00:00",
]

_EXPECTED_TABLES = [
    "fact_sales", "dim_date", "dim_geography",
    "dim_store", "dim_product", "dim_supplier", "dim_warehouse",
]


@pytest.fixture(autouse=True)
def _prevent_pipeline_from_stopping_shared_spark_session(monkeypatch, spark):
    """
    main.run_pipeline() calls spark.stop() in its finally block as part of
    normal production behavior. But SparkSession.getOrCreate() returns the
    single active JVM SparkContext, so that stop() call would also tear
    down the session-scoped `spark` fixture shared by every other test
    module. Patching stop() to a no-op here lets run_pipeline() execute
    unmodified while keeping the shared test session alive for tests that
    run afterward, regardless of test execution order.
    """
    monkeypatch.setattr(SparkSession, "stop", lambda self: None)


def _write_test_config(tmp_path, raw_csv_path, curated_dir):
    config = {
        "app": {"name": "test_pipeline", "environment": "test"},
        "paths": {
            "raw_data": raw_csv_path,
            "staging_dir": str(tmp_path / "staging"),
            "curated_dir": curated_dir,
            "logs_dir": str(tmp_path / "logs"),
        },
        "spark": {
            "app_name": "test-pipeline",
            "shuffle_partitions": 2,
            "master": "local[2]",
        },
        "data_quality": {
            "max_allowed_null_pct": 5.0,
        },
        "cleaning": {
            "warehouse_id_fill_value": "UNKNOWN",
            "numeric_string_columns": ["Value Sales", "Units Sales"],
        },
    }
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(yaml.dump(config))
    return str(config_path)


def test_pipeline_runs_end_to_end_and_exports_curated_files(tmp_path):
    raw_csv = tmp_path / "raw_sales.csv"
    raw_csv.write_text(_HEADER + "\n" + "\n".join(_ROWS) + "\n")

    curated_dir = str(tmp_path / "curated")
    config_path = _write_test_config(tmp_path, str(raw_csv), curated_dir)

    exit_code = run_pipeline(config_path)

    assert exit_code == 0
    for table_name in _EXPECTED_TABLES:
        expected_file = os.path.join(curated_dir, f"{table_name}.csv")
        assert os.path.exists(expected_file), f"Missing expected output: {expected_file}"
        assert os.path.getsize(expected_file) > 0


def test_pipeline_fact_table_row_count_matches_deduplicated_input(tmp_path):
    raw_csv = tmp_path / "raw_sales.csv"
    raw_csv.write_text(_HEADER + "\n" + "\n".join(_ROWS) + "\n")

    curated_dir = str(tmp_path / "curated")
    config_path = _write_test_config(tmp_path, str(raw_csv), curated_dir)

    exit_code = run_pipeline(config_path)
    assert exit_code == 0

    # 3 raw rows, 1 exact duplicate -> 2 rows expected after cleaning.
    fact_csv = pd.read_csv(os.path.join(curated_dir, "fact_sales.csv"))
    assert len(fact_csv) == 2
