# 🐳 Docker Compose — Line-by-Line Explanation

## 📌 What is This Project About?

This is a **Banking Data Engineering Pipeline**. Here's the full data flow:

```
Fake Data Generator (Python/Faker)
        │
        ▼
   PostgreSQL (Banking DB)          ← stores customers, accounts, transactions
        │
        ▼
   Debezium Connect (CDC)           ← watches for every INSERT/UPDATE/DELETE in Postgres
        │
        ▼
   Apache Kafka (Message Broker)    ← streams those changes as events
        │
        ▼
   Kafka Consumer (Python)          ← reads events from Kafka
        │
        ▼
   AWS S3 (Data Lake)               ← stores data as Parquet files
        │
        ▼
   dbt + Snowflake (Transformations)← cleans and models the data
        │
   Orchestrated by Apache Airflow   ← schedules and monitors everything
```

---

## 📌 What Does Docker Compose Do?

Docker Compose lets you **run multiple services (containers) together** with a single command:
```bash
docker compose up
```
Instead of manually starting Kafka, Zookeeper, Postgres, Airflow etc. one by one, you define them all in one file and Docker handles the rest.

---

## 🔍 Line-by-Line Breakdown

---

### Line 1 — Version

```yaml
version: '3.8'
```

| Part | Meaning |
|------|---------|
| `version` | Tells Docker which compose file format version to use |
| `'3.8'` | A stable, modern version that supports features like health checks, `depends_on` conditions, etc. |

---

### Line 2 — Services (Parent Key)

```yaml
services:
```

Everything below this is a **container definition**. Each child (like `zookeeper`, `kafka`, `postgres`) becomes a separate Docker container when you run `docker compose up`.

---

---

## 🦁 SERVICE 1: Zookeeper (Lines 3–9)

```yaml
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
```

### What is Zookeeper?
Zookeeper is like a **manager/coordinator for Kafka**. Kafka uses Zookeeper to:
- Know which Kafka brokers are alive
- Elect a leader broker
- Store topic metadata (how many partitions, replicas, etc.)

> **Think of it like this:** Kafka is a restaurant, Zookeeper is the restaurant manager who keeps track of which waiters (brokers) are available and assigns tables (partitions).

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 3 | `zookeeper:` | **Name of this service** — Docker will create a container called `zookeeper` |
| 4 | `image: confluentinc/cp-zookeeper:7.4.0` | **Which image to use** — Downloads Confluent's Zookeeper image (version 7.4.0) from Docker Hub |
| 5 | `environment:` | **Environment variables** — Configuration passed into the container |
| 6 | `ZOOKEEPER_CLIENT_PORT: 2181` | **Port Zookeeper listens on** — Kafka will connect to Zookeeper on this port |
| 7 | `ZOOKEEPER_TICK_TIME: 2000` | **Heartbeat interval** — Zookeeper sends a heartbeat every 2000ms (2 seconds) to check if Kafka is alive |
| 8-9 | `ports: - "2181:2181"` | **Port mapping** — Maps port 2181 inside the container → port 2181 on your Windows machine |

---

---

## 📨 SERVICE 2: Kafka (Lines 11–28)

```yaml
  kafka:
    image: confluentinc/cp-kafka:7.4.1
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,PLAINTEXT_HOST://0.0.0.0:29092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://host.docker.internal:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
```

### What is Kafka?
Kafka is a **message broker / event streaming platform**. In your project:
- Debezium **produces** events (every database change) into Kafka **topics**
- Your Python consumer (`kafka_to_s3.py`) **reads** those events and uploads them to S3

> **Think of it like a post office**: Debezium drops letters (events) into mailboxes (topics), and your consumer picks them up.

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 11 | `kafka:` | Service name |
| 12 | `image: confluentinc/cp-kafka:7.4.1` | Uses Confluent's Kafka image, version 7.4.1 |
| 13 | `container_name: kafka` | Forces the container name to `kafka` (other services refer to it by this name) |
| 14-15 | `depends_on: - zookeeper` | **Start order** — Zookeeper MUST start before Kafka, because Kafka needs Zookeeper to be running |
| 16-18 | `ports: ...` | **Two port mappings** (explained below) |

### Port Mapping Explained:

| Port | Who Uses It | Purpose |
|------|-------------|---------|
| `9092:9092` | Other Docker containers (like Debezium) | **Internal communication** — containers talk to Kafka on port 9092 using the Docker network |
| `29092:29092` | Your Windows machine (Python scripts) | **External communication** — your `kafka_to_s3.py` script running on Windows connects via port 29092 |

### Environment Variables Explained:

| Variable | Value | What It Means |
|----------|-------|--------------|
| `KAFKA_BROKER_ID: 1` | `1` | Unique ID for this Kafka broker. Since we have only 1 broker, it's `1` |
| `KAFKA_ZOOKEEPER_CONNECT` | `zookeeper:2181` | Tells Kafka where Zookeeper is. `zookeeper` is the service name from line 3, `2181` is the port |
| `KAFKA_LISTENERS` | `PLAINTEXT://0.0.0.0:9092, PLAINTEXT_HOST://0.0.0.0:29092` | **What Kafka listens on** — Two listeners: one on port 9092 (for Docker containers), one on 29092 (for your Windows machine). `0.0.0.0` means "listen on all network interfaces" |
| `KAFKA_ADVERTISED_LISTENERS` | `PLAINTEXT://kafka:9092, PLAINTEXT_HOST://host.docker.internal:29092` | **What Kafka tells clients to connect to** — Docker containers are told to connect to `kafka:9092`. Your Windows machine is told to connect to `host.docker.internal:29092` (a special Docker DNS that points to your Windows host) |
| `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` | `PLAINTEXT:PLAINTEXT, PLAINTEXT_HOST:PLAINTEXT` | Both listeners use **no encryption** (PLAINTEXT). Fine for local development |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | `PLAINTEXT` | Brokers talk to each other using the `PLAINTEXT` listener (port 9092) |
| `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` | `1` | Consumer offset tracking topic has 1 copy. Set to `1` because we only have 1 broker |
| `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR` | `1` | Transaction log has 1 copy. Same reason as above |
| `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR` | `1` | Minimum "in-sync replicas" needed for transactions. `1` because single broker |

---

---

## 🔗 SERVICE 3: Debezium Connect (Lines 31–48)

```yaml
  connect:
    image: debezium/connect:2.2
    depends_on:
      - kafka
      - zookeeper
      - postgres
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: 'kafka:9092'
      GROUP_ID: '1'
      CONFIG_STORAGE_TOPIC: 'connect-configs'
      OFFSET_STORAGE_TOPIC: 'connect-offsets'
      STATUS_STORAGE_TOPIC: 'connect-status'
      KEY_CONVERTER_SCHEMAS_ENABLE: 'false'
      VALUE_CONVERTER_SCHEMAS_ENABLE: 'false'
      KEY_CONVERTER: 'org.apache.kafka.connect.json.JsonConverter'
      VALUE_CONVERTER: 'org.apache.kafka.connect.json.JsonConverter'
```

### What is Debezium Connect?
Debezium is a **Change Data Capture (CDC) tool**. It:
1. Connects to your PostgreSQL database
2. Reads the **WAL (Write-Ahead Log)** — Postgres's internal log of every change
3. Converts each INSERT/UPDATE/DELETE into a JSON event
4. Sends that event to a Kafka topic

> **Think of it like a security camera for your database** — it watches every change and reports it to Kafka.

Your script `kafka/generate_and_post.py` registers the Debezium connector via the REST API on port 8083.

### Line-by-Line:

| Variable | Value | What It Means |
|----------|-------|--------------|
| `image: debezium/connect:2.2` | | Uses Debezium's Kafka Connect image, version 2.2 |
| `depends_on` | kafka, zookeeper, postgres | **All three must start first** — Debezium needs Kafka to send events to, Zookeeper for Kafka, and Postgres to watch |
| `ports: "8083:8083"` | | REST API port. Your `generate_and_post.py` sends a POST request to `http://localhost:8083/connectors` to register the connector |
| `BOOTSTRAP_SERVERS` | `kafka:9092` | Where Kafka is (Docker internal) |
| `GROUP_ID` | `1` | Consumer group ID for Kafka Connect |
| `CONFIG_STORAGE_TOPIC` | `connect-configs` | Kafka topic where connector **configuration** is stored |
| `OFFSET_STORAGE_TOPIC` | `connect-offsets` | Kafka topic where connector **progress** (which changes it has already processed) is stored |
| `STATUS_STORAGE_TOPIC` | `connect-status` | Kafka topic where connector **health status** is stored |
| `KEY_CONVERTER_SCHEMAS_ENABLE` | `false` | Don't include Avro/JSON schema in the message key (keeps messages smaller) |
| `VALUE_CONVERTER_SCHEMAS_ENABLE` | `false` | Don't include schema in the message value |
| `KEY_CONVERTER` | `JsonConverter` | Convert message keys to **JSON** format |
| `VALUE_CONVERTER` | `JsonConverter` | Convert message values to **JSON** format |

---

---

## 🐘 SERVICE 4: PostgreSQL — Banking Database (Lines 50–63)

```yaml
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - ./docker/postgres/data:/var/lib/postgresql/data
    command: >
      postgres -c wal_level=logical
              -c max_wal_senders=10
              -c max_replication_slots=10
```

### What is This?
This is your **main banking database**. It stores three tables:
- `customers` — customer info (name, email)
- `accounts` — bank accounts (type, balance, currency)
- `transactions` — deposits, withdrawals, transfers

Your `fake_generator.py` inserts fake data into this database.

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 51 | `image: postgres:15` | Uses official PostgreSQL version 15 |
| 53 | `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}` | Password comes from your `.env` file. The `${}` syntax tells Docker to read the value from the `.env` file |
| 54 | `POSTGRES_USER: ${POSTGRES_USER}` | Username from `.env` |
| 55 | `POSTGRES_DB: ${POSTGRES_DB}` | Database name from `.env` |
| 57 | `"5432:5432"` | Standard Postgres port. Your `fake_generator.py` connects here |
| 59 | `./docker/postgres/data:/var/lib/postgresql/data` | **Volume mount** — Saves database files to `./docker/postgres/data` on your Windows machine. This means **data survives even if you destroy and recreate the container** |

### The `command` Section (CRITICAL for CDC):

```yaml
command: >
  postgres -c wal_level=logical
          -c max_wal_senders=10
          -c max_replication_slots=10
```

| Flag | What It Does | Why It's Needed |
|------|-------------|-----------------|
| `wal_level=logical` | Sets the **Write-Ahead Log level** to `logical` | **Required for Debezium CDC**. By default, Postgres WAL is set to `replica` which doesn't include enough detail. `logical` means Postgres records the actual row data in the WAL, so Debezium can read every change |
| `max_wal_senders=10` | Allows up to 10 processes to read the WAL simultaneously | Debezium needs at least 1 WAL sender connection |
| `max_replication_slots=10` | Allows up to 10 replication slots | Debezium creates a replication slot (`banking_slot`) to bookmark its position in the WAL so it doesn't miss changes |

---

### Lines 65-66: Comment About S3

```yaml
  # NOTE: Using AWS S3 for storage instead of MinIO
  # Configure in .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
```

This is just a note — your project uses **real AWS S3** instead of MinIO (a local S3 clone). Your `kafka_to_s3.py` script handles the upload.

---

---

## ✈️ SERVICE 5: Airflow Init (Lines 69–84)

```yaml
  airflow-init:
    build:
      context: .
      dockerfile: docker-airflow.dockerfile
    container_name: airflow-init
    depends_on:
      - airflow-postgres
    environment:
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@airflow-postgres:5432/${AIRFLOW_DB_NAME}
    volumes:
      - ./docker/dags:/opt/airflow/dags
      - ./docker/logs:/opt/airflow/logs
      - ./docker/plugins:/opt/airflow/plugins
    entrypoint: /bin/bash
    command: -c "airflow db init && airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com || true"
```

### What is This?
This is a **one-time setup container**. It:
1. Initializes the Airflow metadata database (`airflow db init`)
2. Creates an admin user (username: `admin`, password: `admin`)
3. **Then exits** — it does NOT keep running

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 70-72 | `build: context: . dockerfile: docker-airflow.dockerfile` | **Builds a custom image** instead of using a pre-built one. It uses `docker-airflow.dockerfile` which installs `dbt-core` and `dbt-snowflake` on top of the official Airflow image |
| 73 | `container_name: airflow-init` | Container is named `airflow-init` |
| 74-75 | `depends_on: - airflow-postgres` | Waits for Airflow's own Postgres database to start first |
| 77 | `AIRFLOW__CORE__LOAD_EXAMPLES=False` | Don't load Airflow's built-in example DAGs (keeps the UI clean) |
| 78 | `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=...` | **Database connection string** — Tells Airflow where to store its metadata. Format: `postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DBNAME` |
| 79-82 | `volumes: ...` | Mounts three folders from your machine into the container: **dags** (workflow definitions), **logs** (execution logs), **plugins** (custom Airflow plugins) |
| 83 | `entrypoint: /bin/bash` | Overrides the default entrypoint to run a bash command |
| 84 | `command: -c "airflow db init && ..."` | Runs two commands: (1) Initialize the database, (2) Create an admin user. The `|| true` at the end means "don't fail if the user already exists" |

---

---

## 🌐 SERVICE 6: Airflow Webserver (Lines 86–108)

```yaml
  airflow-webserver:
    build:
      context: .
      dockerfile: docker-airflow.dockerfile
    container_name: airflow-webserver
    restart: always
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      airflow-postgres:
        condition: service_started
    environment:
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=...
    volumes:
      - ./docker/dags:/opt/airflow/dags
      - ./docker/logs:/opt/airflow/logs
      - ./docker/plugins:/opt/airflow/plugins
      - ./banking_dbt:/opt/airflow/banking_dbt
      - ./banking_dbt/.dbt:/home/airflow/.dbt
    ports:
      - "8080:8080"
    command: webserver
```

### What is This?
This is the **Airflow Web UI** — you open `http://localhost:8080` in your browser to see, trigger, and monitor your data pipeline DAGs.

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 91 | `restart: always` | If this container crashes, Docker will **automatically restart it** |
| 92-96 | `depends_on: ...` | Two conditions: (1) `airflow-init` must have **completed successfully** (finished its setup), (2) `airflow-postgres` must have **started** |
| 104 | `./banking_dbt:/opt/airflow/banking_dbt` | Mounts your **dbt project** into the container so Airflow DAGs can run dbt commands |
| 105 | `./banking_dbt/.dbt:/home/airflow/.dbt` | Mounts the **dbt profiles.yml** (contains Snowflake connection credentials) |
| 107 | `"8080:8080"` | **Airflow UI is accessible at** `http://localhost:8080` |
| 108 | `command: webserver` | Starts the Airflow webserver process |

---

---

## ⏰ SERVICE 7: Airflow Scheduler (Lines 110–130)

```yaml
  airflow-scheduler:
    build:
      context: .
      dockerfile: docker-airflow.dockerfile
    container_name: airflow-scheduler
    restart: always
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      airflow-postgres:
        condition: service_started
    environment:
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=...
    volumes:
      - ./docker/dags:/opt/airflow/dags
      - ./docker/logs:/opt/airflow/logs
      - ./docker/plugins:/opt/airflow/plugins
      - ./banking_dbt:/opt/airflow/banking_dbt
      - ./banking_dbt/.dbt:/home/airflow/.dbt
    command: scheduler
```

### What is This?
The Scheduler is the **brain of Airflow**. It:
- Reads your DAG files from `./docker/dags`
- Determines which tasks need to run (based on schedule)
- Triggers task execution

> **Webserver vs Scheduler:** The webserver is just the UI (what you see). The scheduler is the engine that actually runs the DAGs. Both are needed.

### Key Differences from Webserver:
| | Webserver | Scheduler |
|---|-----------|-----------|
| `command` | `webserver` | `scheduler` |
| `ports` | `8080:8080` (has UI) | **No ports** (no UI, runs in the background) |
| Purpose | Show DAGs in browser | Actually execute DAGs on schedule |

---

---

## 🐘 SERVICE 8: Airflow PostgreSQL (Lines 134–145)

```yaml
  airflow-postgres:
    image: postgres:15
    container_name: airflow-postgres
    restart: always
    environment:
      POSTGRES_USER: ${AIRFLOW_DB_USER}
      POSTGRES_PASSWORD: ${AIRFLOW_DB_PASSWORD}
      POSTGRES_DB: ${AIRFLOW_DB_NAME}
    volumes:
      - airflow_postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
```

### What is This?
This is a **separate PostgreSQL database** used **only by Airflow** to store its internal metadata (DAG runs, task statuses, user accounts, etc.). 

> ⚠️ **This is NOT the banking database.** This is Airflow's own internal database.

### Line-by-Line:

| Line | Code | What It Does |
|------|------|-------------|
| 135 | `image: postgres:15` | Same Postgres 15 image as the banking DB |
| 137 | `restart: always` | Auto-restart on crash |
| 139-141 | `POSTGRES_USER/PASSWORD/DB` | Credentials from `.env` file (separate variables: `AIRFLOW_DB_USER`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_DB_NAME`) |
| 143 | `airflow_postgres_data:/var/lib/postgresql/data` | **Named volume** (not a local folder path). Docker manages this volume. Data persists across container restarts |
| 145 | `"5433:5432"` | Maps to port **5433** on your machine (NOT 5432!) to **avoid conflict** with the banking Postgres which uses 5432 |

### Why Two Postgres Instances?

| | Banking Postgres | Airflow Postgres |
|---|-----------------|-----------------|
| **Purpose** | Store customers, accounts, transactions | Store Airflow metadata (DAG runs, task status) |
| **Host Port** | `5432` | `5433` |
| **Credentials** | `POSTGRES_USER/PASSWORD/DB` | `AIRFLOW_DB_USER/PASSWORD/NAME` |
| **Volume** | Local folder (`./docker/postgres/data`) | Named volume (`airflow_postgres_data`) |
| **CDC enabled?** | ✅ Yes (`wal_level=logical`) | ❌ No (not needed) |

---

---

## 📦 Lines 147–149: Volumes

```yaml
volumes:
  airflow_postgres_data:
  postgres_data:
```

These declare **named volumes** — Docker-managed storage spaces that persist data even when containers are deleted.

| Volume | Used By | Purpose |
|--------|---------|---------|
| `airflow_postgres_data` | `airflow-postgres` service | Stores Airflow metadata database files |
| `postgres_data` | Declared but **not currently used** in any service (the banking postgres uses a local folder bind mount instead) |

---

## 🌐 Lines 150–152: Networks

```yaml
networks:
  default:
    name: banking-mds-net
```

This creates a **custom Docker network** named `banking-mds-net`. 

### What does this mean?
- All 7 services (Zookeeper, Kafka, Connect, Postgres, Airflow-init, Airflow-webserver, Airflow-scheduler, Airflow-postgres) are placed on **the same network**
- They can **talk to each other by service name** (e.g., Kafka connects to `zookeeper:2181`, Debezium connects to `kafka:9092`)
- Without this, each service would be isolated and couldn't communicate

---

---

## 🗺️ Complete Architecture Map

```
YOUR WINDOWS MACHINE
│
├── Port 2181  →  Zookeeper (manages Kafka)
├── Port 9092  →  Kafka (internal, Docker-to-Docker)
├── Port 29092 →  Kafka (external, your Python scripts connect here)
├── Port 8083  →  Debezium Connect REST API
├── Port 5432  →  PostgreSQL (Banking data — customers, accounts, transactions)
├── Port 5433  →  PostgreSQL (Airflow metadata)
└── Port 8080  →  Airflow Web UI (http://localhost:8080)
```

## 🔄 Container Startup Order

```
1. zookeeper          ← starts first (no dependencies)
2. airflow-postgres   ← starts first (no dependencies)
3. postgres           ← starts first (no dependencies)
4. kafka              ← waits for zookeeper
5. airflow-init       ← waits for airflow-postgres
6. connect            ← waits for kafka + zookeeper + postgres
7. airflow-webserver  ← waits for airflow-init to COMPLETE
8. airflow-scheduler  ← waits for airflow-init to COMPLETE
```

## 📝 `.env` Variables Needed

Your `.env` file needs these variables for everything to work:

```env
# Banking Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db_name

# Airflow Database
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow
AIRFLOW_DB_NAME=airflow

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=your_region
S3_BUCKET_NAME=your_bucket
```
