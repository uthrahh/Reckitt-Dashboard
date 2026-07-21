"""
conftest.py

Shared pytest fixtures for the test suite. A single session-scoped
SparkSession is reused across all tests — creating a new SparkSession per
test is slow and unnecessary for unit-level tests against small
in-memory DataFrames.
"""

import os
import sys

import pytest
from pyspark.sql import SparkSession

# Ensure the project root (parent of tests/) is on sys.path so
# `import config.schema_config` / `import src...` resolve regardless of
# the directory pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    """Session-scoped local SparkSession for the test suite."""
    session = (
        SparkSession.builder
        .appName("reckitt-fmcg-analytics-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", 2)
        .config("spark.ui.showConsoleProgress", False)
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
