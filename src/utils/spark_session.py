"""
spark_session.py

Centralized SparkSession factory. WHY: every module needing Spark should
pull from one configured entrypoint rather than each script calling
SparkSession.builder independently — this avoids config drift and makes
it trivial to swap local -> cluster settings in one place.
"""

from pyspark.sql import SparkSession


def get_spark_session(app_name: str, master: str = "local[*]",
                       shuffle_partitions: int = 8) -> SparkSession:
    """
    Builds (or retrieves, if already active) a SparkSession configured for
    this pipeline.

    Args:
        app_name: Name shown in the Spark UI / logs.
        master: Spark master URL. 'local[*]' uses all available cores —
                appropriate for a local/dev laptop workload of this size.
        shuffle_partitions: Overrides Spark's default of 200 shuffle
                partitions, which is tuned for large clusters. For an
                ~11K row dataset, 200 partitions would create massive
                task-scheduling overhead relative to actual data volume.

    Returns:
        Active SparkSession.
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master(master)
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")  # suppress noisy INFO logs; keep our own logger authoritative
    return spark
