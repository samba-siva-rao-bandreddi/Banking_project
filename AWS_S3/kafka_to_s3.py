import boto3
from kafka import KafkaConsumer
import json
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------
# Load secrets from .env
# -----------------------------
root_dir = Path(__file__).parent.parent
dotenv_path = root_dir / '.env'
load_dotenv(dotenv_path)

# -----------------------------
# Kafka consumer settings
# -----------------------------
print(f"🔧 Connecting to Kafka at: {os.getenv('KAFKA_BOOTSTRAP', 'localhost:29092')}")
print(f"🔧 Consumer group: {os.getenv('KAFKA_GROUP', 'banking-s3-consumer-v2')}")

consumer = KafkaConsumer(
    'banking_server.public.customers',
    'banking_server.public.accounts',
    'banking_server.public.transactions',
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:29092"),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id=os.getenv("KAFKA_GROUP", "debezium-s3-sink-group"),
    value_deserializer=lambda x: json.loads(x.decode('utf-8')),
    consumer_timeout_ms=60000,  # Timeout after 60 seconds if no messages
    api_version=(2, 5, 0)
)

# -----------------------------
# AWS S3 Client
# -----------------------------
s3 = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

bucket = os.getenv("S3_BUCKET_NAME")

# -----------------------------
# Create bucket if not exists
# -----------------------------
try:
    s3.head_bucket(Bucket=bucket)
    print(f"✅ Bucket '{bucket}' exists")
except:
    region = os.getenv("AWS_REGION")
    
    s3.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={'LocationConstraint': region}
    )
    print(f"✅ Created bucket '{bucket}'")

# -----------------------------
# Consume and write function
# -----------------------------
def write_to_s3(table_name, records):
    if not records:
        return
    df = pd.DataFrame(records)
    date_str = datetime.now().strftime('%Y-%m-%d')
    file_path = f'{table_name}_{date_str}.parquet'
    df.to_parquet(file_path, engine='fastparquet', index=False)
    s3_key = f'{table_name}/date={date_str}/{table_name}_{datetime.now().strftime("%H%M%S%f")}.parquet'
    s3.upload_file(file_path, bucket, s3_key)
    os.remove(file_path)
    print(f'✅ Uploaded {len(records)} records to s3://{bucket}/{s3_key}')

# -----------------------------
# Batch consume
# -----------------------------
batch_size = 50
buffer = {
    'banking_server.public.customers': [],
    'banking_server.public.accounts': [],
    'banking_server.public.transactions': []
}

print("✅ Connected to Kafka. Listening for messages...")
for message in consumer:
    
    topic = message.topic
    event = message.value
    payload = event.get("payload", {})
    #print(payload)
    record = payload.get("after")  # Only take the actual row

    if record:
        buffer[topic].append(record)
        print(f"[{topic}] -> {record}")  # Debugging

    if len(buffer[topic]) >= batch_size:
        write_to_s3(topic.split('.')[-1], buffer[topic])
        buffer[topic] = []