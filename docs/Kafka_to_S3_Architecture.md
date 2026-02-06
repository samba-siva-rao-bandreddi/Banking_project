# Banking CDC Pipeline - Complete Architecture Guide

> **Project Goal**: Capture real-time changes from PostgreSQL database and stream them to AWS S3 as Parquet files for analytics.

---

## Table of Contents
1. [High-Level Architecture](#high-level-architecture)
2. [Component Deep Dive](#component-deep-dive)
3. [How Components Connect](#how-components-connect)
4. [Configuration Explained](#configuration-explained)
5. [Kafka Topics Explained](#kafka-topics-explained)
6. [Data Flow Step-by-Step](#data-flow-step-by-step)
7. [File-by-File Explanation](#file-by-file-explanation)
8. [Execution Guide](#execution-guide)

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              BANKING CDC PIPELINE                                     │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│   │   Python    │    │  PostgreSQL │    │  Debezium   │    │   Apache    │          │
│   │  Generator  │───▶│  Database   │───▶│  Connect    │───▶│   Kafka     │          │
│   │             │    │             │    │             │    │             │          │
│   │ Generates   │    │ Stores Data │    │ Reads WAL   │    │ Streams     │          │
│   │ Fake Data   │    │ + WAL Logs  │    │ Changes     │    │ Messages    │          │
│   └─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘          │
│                                                                    │                  │
│                                                                    ▼                  │
│                                                           ┌─────────────┐            │
│                       ┌─────────────┐                     │   Python    │            │
│                       │   AWS S3    │◀────────────────────│  Consumer   │            │
│                       │             │                     │             │            │
│                       │ Stores      │                     │ Reads Kafka │            │
│                       │ Parquet     │                     │ Writes S3   │            │
│                       └─────────────┘                     └─────────────┘            │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. PostgreSQL Database (Port 5432)

**What it does**: Stores all banking data in tables.

**Tables Created**:
```
┌─────────────────────────────────────────────────────────────────┐
│                         CUSTOMERS                                │
├─────────────────────────────────────────────────────────────────┤
│ id (PRIMARY KEY) │ first_name │ last_name │ email (UNIQUE)      │
│ 1                │ John       │ Doe       │ john@email.com       │
│ 2                │ Jane       │ Smith     │ jane@email.com       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          ACCOUNTS                                │
├─────────────────────────────────────────────────────────────────┤
│ id │ customer_id │ account_type │ balance  │ currency           │
│ 1  │ 1           │ SAVINGS      │ 500.00   │ USD                │
│ 2  │ 1           │ CHECKING     │ 250.00   │ USD                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        TRANSACTIONS                              │
├─────────────────────────────────────────────────────────────────┤
│ id │ account_id │ txn_type   │ amount │ related_acc_id │ status │
│ 1  │ 1          │ DEPOSIT    │ 100.00 │ NULL           │ DONE   │
│ 2  │ 1          │ TRANSFER   │ 50.00  │ 2              │ DONE   │
└─────────────────────────────────────────────────────────────────┘
```

**Special Configuration** (Why this is important):
```yaml
command: postgres -c wal_level=logical
                  -c max_wal_senders=10
                  -c max_replication_slots=10
```

| Config | What It Means |
|--------|---------------|
| `wal_level=logical` | Enables PostgreSQL to record WHAT data changed (not just that something changed) |
| `max_wal_senders=10` | Allows up to 10 processes to read the WAL log simultaneously |
| `max_replication_slots=10` | Reserves 10 slots for tracking who is reading WAL (Debezium uses one slot) |

> **WAL (Write-Ahead Log)**: PostgreSQL writes every INSERT/UPDATE/DELETE to a log file BEFORE actually changing the data. Debezium reads this log to know what changed.

---

### 2. Zookeeper (Port 2181)

**What it does**: Manages and coordinates Kafka brokers.

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZOOKEEPER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Responsibilities:                                              │
│   ✓ Keeps track of which Kafka brokers are alive                │
│   ✓ Elects a leader broker if one fails                         │
│   ✓ Stores metadata about topics and partitions                 │
│   ✓ Manages configuration for Kafka cluster                     │
│                                                                  │
│   Configuration:                                                 │
│   • ZOOKEEPER_CLIENT_PORT: 2181  ← Kafka connects here          │
│   • ZOOKEEPER_TICK_TIME: 2000    ← Heartbeat interval (2 sec)   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3. Apache Kafka (Ports 9092, 29092)

**What it does**: Acts as a message queue/streaming platform. Stores and delivers messages.

```
┌─────────────────────────────────────────────────────────────────┐
│                          KAFKA BROKER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   TWO LISTENERS (Two ways to connect):                          │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ PLAINTEXT (Port 9092)                                    │   │
│   │ • For: Docker containers to talk to Kafka               │   │
│   │ • Example: Debezium Connect → kafka:9092                │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ PLAINTEXT_HOST (Port 29092)                              │   │
│   │ • For: Your Python scripts on Windows to talk to Kafka  │   │
│   │ • Example: kafka_to_s3.py → localhost:29092             │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Configuration Explained**:
```yaml
KAFKA_BROKER_ID: 1
# Unique ID for this Kafka broker (if you have multiple brokers, each gets a different ID)

KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
# Tells Kafka where to find Zookeeper (using Docker service name "zookeeper")

KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,PLAINTEXT_HOST://0.0.0.0:29092
# Kafka listens on these ports
# 0.0.0.0 means "accept connections from anywhere"

KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://host.docker.internal:29092
# These are the addresses Kafka tells clients to use:
# • Docker containers should use: kafka:9092
# • Windows host should use: host.docker.internal:29092 (maps to localhost on Windows)

KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
# Internal topic __consumer_offsets has 1 copy (since we have only 1 broker)
```

---

### 4. Debezium Connect (Port 8083)

**What it does**: Reads PostgreSQL WAL log and publishes changes to Kafka topics.

```
┌─────────────────────────────────────────────────────────────────┐
│                       DEBEZIUM CONNECT                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   How it works:                                                  │
│                                                                  │
│   1. Connects to PostgreSQL                                      │
│   2. Creates a "replication slot" named "banking_slot"          │
│   3. Reads WAL log entries                                       │
│   4. Converts each change to a JSON message                      │
│   5. Publishes to Kafka topic                                    │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  PostgreSQL Change:                                      │   │
│   │  INSERT INTO customers VALUES (1, 'John', 'Doe', ...)   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Debezium transforms to JSON:                            │   │
│   │  {                                                       │   │
│   │    "before": null,                                       │   │
│   │    "after": {                                            │   │
│   │      "id": 1,                                            │   │
│   │      "first_name": "John",                               │   │
│   │      "last_name": "Doe"                                  │   │
│   │    },                                                    │   │
│   │    "op": "c"  ← c=create, u=update, d=delete            │   │
│   │  }                                                       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Publishes to Kafka topic:                               │   │
│   │  banking_server.public.customers                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Debezium Internal Topics** (Created automatically):
```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          DEBEZIUM INTERNAL TOPICS                               │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  connect-configs                                                                │
│  ├── Stores: Connector configurations                                           │
│  └── Example: postgres-connector settings like database.hostname, tables, etc. │
│                                                                                 │
│  connect-offsets                                                                │
│  ├── Stores: Last read position in PostgreSQL WAL                              │
│  └── Purpose: If Debezium restarts, it knows where to continue reading from    │
│                                                                                 │
│  connect-status                                                                 │
│  ├── Stores: Health status of connectors                                        │
│  └── Purpose: Track if connectors are RUNNING, PAUSED, or FAILED               │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### 5. AWS S3 (Simple Storage Service)

**What it does**: Cloud object storage for Parquet files.

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS S3                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   What it is:                                                    │
│   • Cloud-based object storage by Amazon                        │
│   • Highly durable (99.999999999% durability)                   │
│   • Pay-per-use pricing                                          │
│                                                                  │
│   How we use it:                                                 │
│   • Store Parquet files from Kafka consumer                     │
│   • Partitioned by date for efficient querying                  │
│   • Can be queried by Athena, Snowflake, etc.                   │
│                                                                  │
│   Bucket Structure:                                              │
│   s3://banking-data-lake/                                        │
│   ├── customers/date=2026-01-26/*.parquet                       │
│   ├── accounts/date=2026-01-26/*.parquet                        │
│   └── transactions/date=2026-01-26/*.parquet                    │
│                                                                  │
│   Connection (boto3):                                            │
│   • Uses AWS_ACCESS_KEY_ID                                       │
│   • Uses AWS_SECRET_ACCESS_KEY                                   │
│   • Uses AWS_REGION                                              │
│   • No endpoint_url needed (unlike MinIO)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## How Components Connect

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              CONNECTION MAP                                           │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                                   DOCKER NETWORK: banking-mds-net            │   │
│   │                                                                              │   │
│   │   ┌──────────┐         ┌──────────┐         ┌──────────┐                    │   │
│   │   │ Postgres │◀───────▶│ Debezium │◀───────▶│  Kafka   │                    │   │
│   │   │ :5432    │   TCP   │ :8083    │   TCP   │  :9092   │                    │   │
│   │   └──────────┘         └──────────┘         └────┬─────┘                    │   │
│   │                                                   │                          │   │
│   │                                                   │ kafka:9092               │   │
│   │                                                   ▼                          │   │
│   │                                             ┌──────────┐                    │   │
│   │                                             │Zookeeper │                    │   │
│   │                                             │  :2181   │                    │   │
│   │                                             └──────────┘                    │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                             │
│                                        │ Port 29092 exposed to Windows               │
│                                        ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                              WINDOWS HOST (Your PC)                          │   │
│   │                                                                              │   │
│   │   ┌────────────────┐                           ┌────────────────┐           │   │
│   │   │ fake_generator │──▶ localhost:5432 ───────▶│   Postgres     │           │   │
│   │   │     .py        │   (Python to Postgres)    │   (Docker)     │           │   │
│   │   └────────────────┘                           └────────────────┘           │   │
│   │                                                                              │   │
│   │   ┌────────────────┐                           ┌────────────────┐           │   │
│   │   │ kafka_to_s3.py │──▶ localhost:29092 ──────▶│    Kafka       │           │   │
│   │   │                │   (Python to Kafka)       │   (Docker)     │           │   │
│   │   └────────────────┘                           └────────────────┘           │   │
│   │          │                                                                   │   │
│   │          ▼                                                                   │   │
│   │   ┌────────────────┐                                                        │   │
│   │   │    AWS S3      │ ◀── Parquet files via boto3                            │   │
│   │   │   (Cloud)      │                                                        │   │
│   │   └────────────────┘                                                        │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Explained

### docker-compose.yml - Service by Service

```yaml
# SERVICE 1: ZOOKEEPER
zookeeper:
  image: confluentinc/cp-zookeeper:7.4.0    # Official Confluent Zookeeper image
  environment:
    ZOOKEEPER_CLIENT_PORT: 2181              # Port where Zookeeper listens
    ZOOKEEPER_TICK_TIME: 2000                # Heartbeat interval in milliseconds
  ports:
    - "2181:2181"                            # Expose port 2181 to host
```

```yaml
# SERVICE 2: KAFKA
kafka:
  image: confluentinc/cp-kafka:7.4.1
  depends_on:
    - zookeeper                              # Start Zookeeper first!
  ports:
    - "9092:9092"                            # Internal (Docker-to-Docker)
    - "29092:29092"                          # External (Windows-to-Docker)
  environment:
    KAFKA_BROKER_ID: 1                       # Unique broker ID
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181  # How to find Zookeeper

    # LISTENERS: What Kafka accepts connections on
    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,PLAINTEXT_HOST://0.0.0.0:29092
    #               └─ Docker internal ─┘     └─ Windows host ──────────┘

    # ADVERTISED: What Kafka tells clients to connect to
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://host.docker.internal:29092
    #                           └─ Docker uses this ─┘  └─ Windows uses this ────────────────┘

    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
    # Maps listener names to security protocols (both use PLAINTEXT = no encryption)

    KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
    # Brokers talk to each other using PLAINTEXT listener

    # REPLICATION: How many copies of data to keep
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1            # __consumer_offsets topic
    KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1    # Transaction log
    KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1               # Minimum in-sync replicas
    # All set to 1 because we have only 1 broker
```

```yaml
# SERVICE 3: DEBEZIUM CONNECT
connect:
  image: debezium/connect:2.2
  depends_on:
    - kafka
    - zookeeper
    - postgres
  ports:
    - "8083:8083"                            # REST API port
  environment:
    BOOTSTRAP_SERVERS: 'kafka:9092'          # Connect to Kafka (Docker internal)
    GROUP_ID: '1'                            # Connect worker group ID

    # WHERE DEBEZIUM STORES ITS STATE (as Kafka topics)
    CONFIG_STORAGE_TOPIC: 'connect-configs'  # Connector configurations
    OFFSET_STORAGE_TOPIC: 'connect-offsets'  # Read positions in PostgreSQL WAL
    STATUS_STORAGE_TOPIC: 'connect-status'   # Connector health status

    # MESSAGE FORMAT (JSON without schema)
    KEY_CONVERTER: 'org.apache.kafka.connect.json.JsonConverter'
    VALUE_CONVERTER: 'org.apache.kafka.connect.json.JsonConverter'
    KEY_CONVERTER_SCHEMAS_ENABLE: 'false'    # Don't include schema in key
    VALUE_CONVERTER_SCHEMAS_ENABLE: 'false'  # Don't include schema in value
```

---

### Debezium Connector Configuration (generate_and_post.py)

```python
connector_config = {
    "name": "postgres-connector",            # Name for this connector
    "config": {
        # CONNECTOR TYPE
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        # Tells Debezium to use PostgreSQL connector (not MySQL, MongoDB, etc.)

        # DATABASE CONNECTION
        "database.hostname": os.getenv("POSTGRES_HOST"),   # localhost or docker service name
        "database.port": os.getenv("POSTGRES_PORT"),       # 5432
        "database.user": os.getenv("POSTGRES_USER"),       # postgres
        "database.password": os.getenv("POSTGRES_PASSWORD"), # ****
        "database.dbname": os.getenv("POSTGRES_DB"),       # banking

        # TOPIC NAMING
        "topic.prefix": "banking_server",
        # All topics will start with this prefix
        # Format: {prefix}.{schema}.{table}
        # Example: banking_server.public.customers

        # WHICH TABLES TO CAPTURE
        "table.include.list": "public.customers,public.accounts,public.transactions",
        # Only capture changes from these 3 tables

        # PostgreSQL SPECIFIC
        "plugin.name": "pgoutput",
        # WAL decoder plugin (pgoutput is built into PostgreSQL 10+)

        "slot.name": "banking_slot",
        # Replication slot name - PostgreSQL reserves a spot for Debezium to read WAL

        "publication.autocreate.mode": "filtered",
        # Automatically create a publication for the filtered tables

        # DATA HANDLING
        "tombstones.on.delete": "false",
        # Don't create extra "tombstone" messages for deletes

        "decimal.handling.mode": "double",
        # Convert DECIMAL/NUMERIC to double (easier to handle in Python)
    }
}
```

---

## Kafka Topics Explained

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              ALL KAFKA TOPICS                                         │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│   ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│   ║                          DATA TOPICS (Your Data)                               ║  │
│   ╠═══════════════════════════════════════════════════════════════════════════════╣  │
│   ║                                                                                ║  │
│   ║   banking_server.public.customers                                              ║  │
│   ║   ├── Contains: All INSERT/UPDATE/DELETE on customers table                   ║  │
│   ║   └── Message example:                                                         ║  │
│   ║       {                                                                        ║  │
│   ║         "payload": {                                                           ║  │
│   ║           "before": null,                                                      ║  │
│   ║           "after": {"id": 1, "first_name": "John", "last_name": "Doe", ...}   ║  │
│   ║         }                                                                      ║  │
│   ║       }                                                                        ║  │
│   ║                                                                                ║  │
│   ║   banking_server.public.accounts                                               ║  │
│   ║   ├── Contains: All changes to accounts table                                  ║  │
│   ║   └── Message example:                                                         ║  │
│   ║       {                                                                        ║  │
│   ║         "payload": {                                                           ║  │
│   ║           "after": {"id": 1, "customer_id": 1, "balance": 500.00, ...}        ║  │
│   ║         }                                                                      ║  │
│   ║       }                                                                        ║  │
│   ║                                                                                ║  │
│   ║   banking_server.public.transactions                                           ║  │
│   ║   ├── Contains: All changes to transactions table                              ║  │
│   ║   └── Message example:                                                         ║  │
│   ║       {                                                                        ║  │
│   ║         "payload": {                                                           ║  │
│   ║           "after": {"id": 1, "account_id": 1, "txn_type": "DEPOSIT", ...}     ║  │
│   ║         }                                                                      ║  │
│   ║       }                                                                        ║  │
│   ║                                                                                ║  │
│   ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│                                                                                       │
│   ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│   ║                     DEBEZIUM INTERNAL TOPICS                                   ║  │
│   ╠═══════════════════════════════════════════════════════════════════════════════╣  │
│   ║                                                                                ║  │
│   ║   connect-configs                                                              ║  │
│   ║   └── Stores connector configurations (postgres-connector settings)           ║  │
│   ║                                                                                ║  │
│   ║   connect-offsets                                                              ║  │
│   ║   └── Stores WAL read position (so Debezium can resume after restart)        ║  │
│   ║                                                                                ║  │
│   ║   connect-status                                                               ║  │
│   ║   └── Stores connector status (RUNNING, PAUSED, FAILED)                       ║  │
│   ║                                                                                ║  │
│   ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│                                                                                       │
│   ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│   ║                      KAFKA INTERNAL TOPICS                                     ║  │
│   ╠═══════════════════════════════════════════════════════════════════════════════╣  │
│   ║                                                                                ║  │
│   ║   __consumer_offsets                                                           ║  │
│   ║   └── Tracks which messages each consumer group has read                       ║  │
│   ║       Example: Consumer "banking-s3-consumer" read up to offset 150           ║  │
│   ║                                                                                ║  │
│   ║   __transaction_state                                                          ║  │
│   ║   └── Tracks transaction states for exactly-once processing                   ║  │
│   ║                                                                                ║  │
│   ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Step-by-Step

### Step 1: Generate Fake Data

```
fake_generator.py
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│   cur.execute("INSERT INTO customers (first_name, ...) ...")    │
│                                                                  │
│   What happens:                                                  │
│   1. Python sends INSERT to PostgreSQL                          │
│   2. PostgreSQL writes to WAL: "INSERT id=1, name=John..."      │
│   3. PostgreSQL writes to actual table                          │
│   4. Returns success to Python                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Step 2: Debezium Captures Change

```
┌─────────────────────────────────────────────────────────────────┐
│   Debezium (running continuously):                               │
│                                                                  │
│   1. Reads WAL log via replication slot "banking_slot"          │
│   2. Sees: INSERT into customers, id=1, name=John               │
│   3. Creates JSON message:                                       │
│      {                                                           │
│        "schema": {...},                                          │
│        "payload": {                                              │
│          "before": null,        ← Old row (null for INSERT)     │
│          "after": {             ← New row data                   │
│            "id": 1,                                              │
│            "first_name": "John",                                 │
│            "last_name": "Doe",                                   │
│            "email": "john@email.com"                             │
│          },                                                      │
│          "source": {...},       ← Metadata about the change     │
│          "op": "c",             ← Operation: c=create            │
│          "ts_ms": 1706234567890 ← Timestamp                      │
│        }                                                         │
│      }                                                           │
│   4. Publishes to topic: banking_server.public.customers        │
└─────────────────────────────────────────────────────────────────┘
```

### Step 3: Consumer Reads from Kafka

```
kafka_to_s3.py
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│   consumer = KafkaConsumer(                                      │
│       'banking_server.public.customers',                         │
│       'banking_server.public.accounts',                          │
│       'banking_server.public.transactions',                      │
│       bootstrap_servers='localhost:29092',                       │
│       group_id='banking-s3-consumer'                            │
│   )                                                              │
│                                                                  │
│   for message in consumer:                                       │
│       # message.value contains the JSON from Debezium            │
│       # Extract: payload → after (the actual row data)          │
│       record = message.value["payload"]["after"]                 │
│       buffer[topic].append(record)                               │
│                                                                  │
│       # When buffer reaches 50 records, write to S3              │
│       if len(buffer[topic]) >= 50:                               │
│           write_to_s3(...)                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Step 4: Write to AWS S3

```
┌─────────────────────────────────────────────────────────────────┐
│   write_to_s3(table_name, records):                              │
│                                                                  │
│   1. Convert records to Pandas DataFrame                         │
│   2. Save as Parquet file locally (temporary)                    │
│   3. Upload to AWS S3:                                           │
│      s3://banking-data-lake/                                     │
│          └── customers/                                          │
│              └── date=2026-01-26/                                │
│                  └── customers_143025123456.parquet              │
│   4. Delete local temporary file                                 │
│                                                                  │
│   Uses boto3 client with:                                        │
│   • AWS_ACCESS_KEY_ID                                            │
│   • AWS_SECRET_ACCESS_KEY                                        │
│   • AWS_REGION                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## File-by-File Explanation

### 📁 Project Structure

```
banking_project/
├── .env                          # All environment variables
├── docker-compose.yml            # Docker services configuration
├── requirements.txt              # Python dependencies
│
├── data_generator/
│   └── fake_generator.py         # Generates fake banking data
│
├── kafka/
│   └── generate_and_post.py      # Registers Debezium connector
│
├── AWS_S3/
│   └── kafka_to_s3.py            # Consumes Kafka, writes to S3
│
└── postgres/
    └── init.sql                  # Database schema (tables)
```

### 📄 .env (Environment Variables)

```env
# PostgreSQL - Where fake_generator.py connects
POSTGRES_USER=postgres
POSTGRES_PASSWORD=samba1004
POSTGRES_DB=banking
POSTGRES_PORT=5432
POSTGRES_HOST=localhost

# Kafka - Where kafka_to_s3.py connects
KAFKA_BOOTSTRAP=localhost:29092
KAFKA_GROUP=banking-s3-consumer

# AWS S3 - Where parquet files go (REQUIRED)
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-1
S3_BUCKET_NAME=banking-data-lake
```

> **How to get AWS credentials:**
> 1. Go to AWS Console → IAM → Users → Your User → Security Credentials
> 2. Create Access Key → Download CSV
> 3. Copy values to .env file

---

## Execution Guide

### Complete Startup Sequence

```
STEP 1: Start Docker Services
─────────────────────────────
> docker-compose up -d

What starts:
✓ Zookeeper     (port 2181)
✓ Kafka         (ports 9092, 29092)
✓ PostgreSQL    (port 5432)
✓ Debezium      (port 8083)


STEP 2: Wait for Services to be Ready (~30 seconds)
───────────────────────────────────────────────────
> curl http://localhost:8083/connectors
Should return: []


STEP 3: Create Database Tables
──────────────────────────────
> psql -h localhost -U postgres -d banking -f postgres/init.sql


STEP 4: Register Debezium Connector
───────────────────────────────────
> python kafka/generate_and_post.py
Should print: ✅ Connector created successfully!


STEP 5: Verify Connector is Running
───────────────────────────────────
> curl http://localhost:8083/connectors/postgres-connector/status
Should show: "state": "RUNNING"


STEP 6: Start Data Generator
────────────────────────────
> python data_generator/fake_generator.py
Generates data every 3 seconds


STEP 7: Start Kafka-to-S3 Consumer
──────────────────────────────────
> python AWS_S3/kafka_to_s3.py
Reads from Kafka, writes to S3
```

### Useful Debug Commands

```bash
# List all Kafka topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# Read messages from a topic
docker exec -it kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic banking_server.public.customers \
    --from-beginning

# Check Debezium connector status
curl http://localhost:8083/connectors/postgres-connector/status | jq

# List S3 bucket contents (AWS CLI)
aws s3 ls s3://banking-data-lake/ --recursive
```

---

## Summary Table

| Component | Port | Connection String | Purpose |
|-----------|------|-------------------|---------|
| PostgreSQL | 5432 | `localhost:5432` | Stores banking data |
| Zookeeper | 2181 | `zookeeper:2181` | Kafka coordination |
| Kafka | 29092 | `localhost:29092` | Message streaming |
| Debezium | 8083 | `http://localhost:8083` | CDC from PostgreSQL |
| AWS S3 | 443 | `s3.amazonaws.com` | Cloud storage for Parquet files |

---

## Quick Reference

```
PostgreSQL (Banking Data)
        │
        │ WAL (Write-Ahead Log)
        ▼
Debezium Connect ──────▶ Reads WAL changes
        │
        │ Publishes JSON messages
        ▼
Kafka Topics:
├── banking_server.public.customers
├── banking_server.public.accounts
└── banking_server.public.transactions
        │
        │ Consumes messages
        ▼
Python Consumer (kafka_to_s3.py)
        │
        │ Converts to Parquet
        ▼
AWS S3 Bucket
└── table_name/date=YYYY-MM-DD/*.parquet
```
