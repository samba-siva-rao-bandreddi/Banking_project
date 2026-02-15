import os
import shutil
from dotenv import load_dotenv
import boto3
from airflow import DAG
from datetime import datetime, timedelta
from airflow.operators.python import PythonOperator
import snowflake.connector
from pathlib import Path

load_dotenv()

TABLES = ["customers", "accounts", "transactions"]
default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DB = os.getenv("SNOWFLAKE_DB")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")


AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

DOWNLOAD_BASE_DIR = "/tmp/s3_downloads"


def download_from_s3(**kwargs):
    """
    Downloads parquet files from AWS S3 for each table.

    S3 structure (created by kafka_to_s3.py):
        {table}/date={YYYY-MM-DD}/{table}_{timestamp}.parquet

    Downloads to: /tmp/s3_downloads/{run_id}/{table}/
    Pushes downloaded file paths via XCom for the next task.
    """
    # --- Use unique directory per DAG run to avoid conflicts ---
    run_id = kwargs["run_id"].replace(":", "_")
    DOWNLOAD_DIR = os.path.join(DOWNLOAD_BASE_DIR, run_id)

    # --- Connect to S3 ---
    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    # --- Clean previous downloads for THIS run ---
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)

    downloaded_files = {}

    for table in TABLES:
        # S3 prefix: customers/ (all dates)
        prefix = f"{table}/"
        print(f"📂 Listing S3 objects: s3://{S3_BUCKET}/{prefix}")

        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

        if "Contents" not in response:
            print(f"⚠️ No files found for table '{table}'")
            downloaded_files[table] = []
            continue

        # --- Create local directory ---
        local_dir = os.path.join(DOWNLOAD_DIR, table)
        os.makedirs(local_dir, exist_ok=True)

        table_files = []
        for obj in response["Contents"]:
            s3_key = obj["Key"]

            # Skip folder entries (no actual file)
            if s3_key.endswith("/"):
                continue

            filename = os.path.basename(s3_key)
            if not filename:
                continue

            local_path = os.path.join(local_dir, filename)

            print(f"⬇️ Downloading s3://{S3_BUCKET}/{s3_key} -> {local_path}")
            s3.download_file(S3_BUCKET, s3_key, local_path)
            table_files.append(local_path)

        downloaded_files[table] = table_files
        print(f"✅ Downloaded {len(table_files)} file(s) for '{table}'")

    # --- Push file paths and download dir to XCom for the next task ---
    kwargs["ti"].xcom_push(key="downloaded_files", value=downloaded_files)
    kwargs["ti"].xcom_push(key="download_dir", value=DOWNLOAD_DIR)
    print(
        f"✅ All downloads complete. Summary: { {t: len(f) for t, f in downloaded_files.items()} }"
    )
    return downloaded_files


def upload_to_snowflake(**kwargs):
    local_files = kwargs["ti"].xcom_pull(
        task_ids="download_from_s3", key="downloaded_files"
    )
    if not local_files:
        print("No files found in S3.")
        return

    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DB,
        schema=SNOWFLAKE_SCHEMA,
    )
    cur = conn.cursor()

    for table, files in local_files.items():
        if not files:
            print(f"No files for {table}, skipping.")
            continue

        for f in files:
            cur.execute(f"PUT file://{f} @%{table}")
            print(f"Uploaded {f} -> @{table} stage")

        copy_sql = f"""
        COPY INTO {table}
        FROM @%{table}
        FILE_FORMAT=(TYPE=PARQUET)
        ON_ERROR='CONTINUE'
        """
        cur.execute(copy_sql)
        print(f"Data loaded into {table}")

    cur.close()
    conn.close()

    # --- Cleanup: remove the temp download directory for this run ---
    download_dir = kwargs["ti"].xcom_pull(
        task_ids="download_from_s3", key="download_dir"
    )
    if download_dir and os.path.exists(download_dir):
        shutil.rmtree(download_dir)
        print(f"🧹 Cleaned up {download_dir}")


with DAG(
    dag_id="s3_to_snowflake",
    start_date=datetime(2026, 2, 12),
    schedule_interval="*/1 * * * *",
    default_args=default_args,
    catchup=False,
) as dag:

    task1 = PythonOperator(
        task_id="download_from_s3",
        python_callable=download_from_s3,
        provide_context=True,
    )

    task2 = PythonOperator(
        task_id="upload_to_snowflake",
        python_callable=upload_to_snowflake,
        provide_context=True,
    )

    task1 >> task2
