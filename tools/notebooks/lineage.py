"""Embedded Spark helpers for this disposable, synthetic full-refresh path only."""

from collections.abc import Callable
from datetime import UTC, datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

RUN_STARTED = datetime.now(UTC)
RUN_OUTPUTS = {}
SYNTHETIC_TABLES = {
    "02_bronze_ingest": {
        f"bronze.{name}" for name in (
            "dim_asset", "dim_customer", "dim_date", "dim_defect_type", "dim_line", "dim_plant",
            "dim_product", "dim_shift", "fact_anomaly_event", "fact_customer_order",
            "fact_maintenance_event", "fact_production_run", "fact_quality_inspection",
        )
    },
    "03_silver_transform": {
        f"silver.{name}" for name in (
            "fact_production_run", "fact_quality_inspection", "fact_maintenance_event",
            "fact_customer_order", "dim_date", "dim_shift", "dim_line", "dim_asset",
            "dim_defect_type", "dq_rejects",
        )
    },
    "04_silver_dims_catchup": {"silver.dim_product", "silver.dim_customer", "silver.dim_plant"},
    "05_gold_star_schema": {
        f"gold.{name}" for name in (
            "dim_date", "dim_plant", "dim_line", "dim_asset", "dim_shift", "dim_product",
            "dim_customer", "dim_defect_type", "fact_production_run", "fact_quality_inspection",
            "fact_maintenance_event", "fact_customer_order", "agg_plant_month",
        )
    },
}


def configure_lineage(spark_session: SparkSession, guard: Callable[[], None], run_batch_id: str,
                      notebook_name: str, source_revision: str):
    """Bind the explicit notebook context after its parameter and UUID guard cells."""
    global spark, require_sandbox, batch_id, NOTEBOOK_NAME, SOURCE_REVISION
    guard()
    if notebook_name not in SYNTHETIC_TABLES:
        raise ValueError("Unknown synthetic notebook")
    spark, require_sandbox, batch_id = spark_session, guard, run_batch_id
    NOTEBOOK_NAME, SOURCE_REVISION = notebook_name, source_revision


def add_bronze_lineage(df):
    return (df.withColumn("_source_file", F.col("_metadata.file_path"))
            .withColumn("_ingest_timestamp", F.current_timestamp())
            .withColumn("_source_system", F.lit("synthetic-manufacturing-csv"))
            .withColumn("_batch_id", F.lit(batch_id)))


def add_silver_lineage(df):
    business_columns = sorted(column for column in df.columns if not column.startswith("_"))
    return (df.withColumn("_processed_timestamp", F.current_timestamp())
            .withColumn("_record_hash", F.sha2(F.to_json(F.struct(*[
                F.col(column) for column in business_columns
            ]), options={"ignoreNullFields": "false"}), 256))
            .withColumn("_batch_id", F.lit(batch_id)))


def write_synthetic(df, table):
    require_sandbox()
    if table not in SYNTHETIC_TABLES[NOTEBOOK_NAME]:
        raise ValueError("Output is outside this notebook's fixed synthetic table allowlist")
    if table.startswith("gold."):
        df = df.withColumn("_built_timestamp", F.current_timestamp()).withColumn("_batch_id", F.lit(batch_id))
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    rows = spark.table(table).count()
    RUN_OUTPUTS[table] = rows
    return rows


def emit_run_metadata():
    require_sandbox()
    if set(RUN_OUTPUTS) != SYNTHETIC_TABLES[NOTEBOOK_NAME]:
        raise ValueError("Not all expected outputs were written; do not mark this notebook successful")
    spark.sql("CREATE SCHEMA IF NOT EXISTS workshop")
    rows_written = sum(RUN_OUTPUTS.values())
    rows_quarantined = RUN_OUTPUTS.get("silver.dq_rejects", 0)
    if NOTEBOOK_NAME.startswith("02_"):
        rows_read = rows_written
    else:
        source_layer = "silver" if NOTEBOOK_NAME.startswith("05_") else "bronze"
        inputs = [table.split(".", 1)[1] for table in RUN_OUTPUTS
                  if not table.endswith(".dq_rejects") and not table.endswith(".agg_plant_month")]
        rows_read = sum(spark.table(f"{source_layer}.{table}").count() for table in inputs)
    metadata = [(
        batch_id, NOTEBOOK_NAME, NOTEBOOK_NAME.split("_")[1], "synthetic_manufacturing",
        RUN_STARTED, datetime.now(UTC), rows_read, rows_written, rows_quarantined,
        "succeeded", 1, SOURCE_REVISION,
    )]
    audit = spark.createDataFrame(metadata, """
        batch_id string, notebook string, layer string, domain string,
        started_at timestamp, ended_at timestamp, rows_read long, rows_written long, rows_quarantined long,
        status string, dictionary_version int, source_git_sha string
    """)
    audit.write.mode("append").format("delta").saveAsTable("workshop._pipeline_runs")
    print(f"Recorded successful run {batch_id}; stop the Spark session when finished.")
