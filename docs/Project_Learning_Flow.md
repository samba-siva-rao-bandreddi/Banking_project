# 🗺️ Banking Data Pipeline — Project Learning Flow

## 📌 What Does This Project Do? (One-Line Summary)

**Generates fake banking data → stores it in PostgreSQL → captures every change via CDC → streams it through Kafka → uploads to AWS S3 as Parquet files → transforms it in Snowflake using dbt → all orchestrated by Apache Airflow.**

---

## 🏗️ Complete Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YOUR WINDOWS MACHINE                            │
│                                                                        │
│   ┌──────────────┐                                                     │
│   │    .env      │ ← All passwords, keys, and config live here         │
│   └──────┬───────┘                                                     │
│          │ (read by every component)                                    │
│          │                                                              │
│   ┌──────▼──────────────────── DOCKER COMPOSE ──────────────────────┐  │
│   │                                                                  │  │
│   │  STEP 1: Generate Fake Data                                      │  │
│   │  ┌──────────────────┐      ┌─────────────────────┐              │  │
│   │  │  fake_generator   │─────▶│  PostgreSQL (5432)  │              │  │
│   │  │  (Python/Faker)   │      │  Banking Database    │              │  │
│   │  └──────────────────┘      │  • customers         │              │  │
│   │  Runs on YOUR machine       │  • accounts          │              │  │
│   │  (not in Docker)            │  • transactions      │              │  │
│   │                             └──────────┬──────────┘              │  │
│   │                                        │                         │  │
│   │  STEP 2: Capture Changes (CDC)         │ WAL (Write-Ahead Log)  │  │
│   │                                        ▼                         │  │
│   │                             ┌─────────────────────┐              │  │
│   │                             │  Debezium Connect    │              │  │
│   │                             │  (port 8083)         │              │  │
│   │                             │  Reads every change  │              │  │
│   │                             └──────────┬──────────┘              │  │
│   │                                        │                         │  │
│   │  STEP 3: Stream Events                 │ JSON events             │  │
│   │                                        ▼                         │  │
│   │             ┌──────────┐    ┌─────────────────────┐              │  │
│   │             │Zookeeper │◄───│  Apache Kafka        │              │  │
│   │             │(manager) │    │  (ports 9092/29092)  │              │  │
│   │             └──────────┘    │  Topics:             │              │  │
│   │                             │  • banking_server.   │              │  │
│   │                             │    public.customers  │              │  │
│   │                             │  • banking_server.   │              │  │
│   │                             │    public.accounts   │              │  │
│   │                             │  • banking_server.   │              │  │
│   │                             │    public.transactions│             │  │
│   │                             └──────────┬──────────┘              │  │
│   │                                        │                         │  │
│   │  STEP 4: Consume & Upload              │                         │  │
│   │                                        ▼                         │  │
│   │                             ┌─────────────────────┐              │  │
│   │                             │  kafka_to_s3.py      │              │  │
│   │                             │  (Python consumer)   │              │  │
│   │                             │  Reads Kafka events  │              │  │
│   │                             │  Writes .parquet     │              │  │
│   │                             └──────────┬──────────┘              │  │
│   │                                        │                         │  │
│   └────────────────────────────────────────┼────────────────────────┘  │
│                                            │                           │
└────────────────────────────────────────────┼───────────────────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │  AWS S3 (Cloud)      │
                                  │  Data Lake            │
                                  │  • customers/         │
                                  │  • accounts/          │
                                  │  • transactions/      │
                                  │  (Parquet files)      │
                                  └──────────┬──────────┘
                                             │
                    STEP 5: Transform         │
                                             ▼
                                  ┌─────────────────────┐
                                  │  Snowflake (Cloud)   │
                                  │  + dbt models        │
                                  │  (Clean & transform) │
                                  └──────────┬──────────┘
                                             │
                    STEP 6: Orchestrate       │
                                             ▼
                                  ┌─────────────────────┐
                                  │  Apache Airflow      │
                                  │  (port 8080)         │
                                  │  Schedules & monitors│
                                  │  the entire pipeline │
                                  └─────────────────────┘
```

---

## 📂 File Map — Every File and What It Does

```
project/
├── .env                          ← 🔑 ALL secrets and config (DB passwords, AWS keys)
│
└── Banking_project/
    ├── docker-compose.yml        ← 🐳 Defines all 8 Docker containers
    ├── docker-airflow.dockerfile ← 🏗️ Custom Airflow image (installs dbt)
    ├── requirements.txt          ← 📦 Python dependencies list
    │
    ├── postgres/
    │   └── schema.sql            ← 📋 Creates the 3 database tables
    │
    ├── data_generator/
    │   └── fake_generator.py     ← 🎲 Generates fake banking data → inserts into Postgres
    │
    ├── kafka/
    │   └── generate_and_post.py  ← 🔗 Registers Debezium connector via REST API
    │
    ├── AWS_S3/
    │   └── kafka_to_s3.py        ← ☁️ Kafka consumer → reads events → uploads Parquet to S3
    │
    ├── test_kafka.py             ← 🧪 Test script: check if Kafka topics have messages
    ├── test_s3.py                ← 🧪 Test script: check if S3 connection works
    │
    └── docs/
        ├── Docker_Compose_Explained.md  ← 📚 Line-by-line docker-compose explanation
        ├── AWS_S3_Setup_Guide.md        ← 📚 How to set up AWS S3
        └── Kafka_to_S3_Architecture.md  ← 📚 Architecture documentation
```

---

## 🎓 Learning Flow — Where to Start and in What Order

### Phase 1: Configuration (Understand the Foundation)

#### Step 1 → `.env` file
📍 **File:** `project/.env`

**What to learn:** This is the configuration brain. Every other file reads from here.

```env
# Banking Database
POSTGRES_HOST=localhost          ← Where Postgres is running
POSTGRES_PORT=5432               ← Which port
POSTGRES_USER=postgres           ← Login username
POSTGRES_PASSWORD=raptee123      ← Login password
POSTGRES_DB=project              ← Database name

# Airflow Database (separate!)
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow
AIRFLOW_DB_NAME=airflow

# AWS S3 (cloud storage)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=your_region
S3_BUCKET_NAME=your_bucket
```

**Key concept:** Environment variables keep secrets OUT of your code. If you push to GitHub, `.env` is in `.gitignore` so your passwords don't leak.

---

### Phase 2: Database (Where Data Lives)

#### Step 2 → `postgres/schema.sql`
📍 **File:** `Banking_project/postgres/schema.sql`

**What to learn:** The 3 tables that store everything.

```
customers ──────┐
  • id           │
  • first_name   │ one customer has
  • last_name    │ many accounts
  • email        │
                 ▼
accounts ───────┐
  • id           │
  • customer_id  │ one account has
  • account_type │ many transactions
  • balance      │
  • currency     │
                 ▼
transactions
  • id
  • account_id
  • tnx_type (DEPOSIT/WITHDRAWAL/TRANSFER)
  • amount
  • related_acc_id (for transfers)
  • status
```

**Key concept:** Foreign keys link the tables. `accounts.customer_id → customers.id` and `transactions.account_id → accounts.id`. The `ON DELETE CASCADE` means if you delete a customer, all their accounts and transactions are also deleted.

---

### Phase 3: Data Generation (Creating Fake Data)

#### Step 3 → `data_generator/fake_generator.py`
📍 **File:** `Banking_project/data_generator/fake_generator.py`

**What to learn:** How fake data is created and inserted.

**What it does step by step:**
1. Connects to PostgreSQL using credentials from `.env`
2. Creates 10 fake customers (using the `Faker` library)
3. Creates 2 accounts per customer (SAVINGS or CHECKING)
4. Creates 50 random transactions (DEPOSIT, WITHDRAWAL, TRANSFER)
5. **Loops every 3 seconds** to keep generating data (this simulates real-world banking activity)

**Key concept:** This script runs on YOUR Windows machine (not inside Docker). It connects to Postgres via `localhost:5432`.

**How to run:**
```bash
python data_generator/fake_generator.py          # loops forever
python data_generator/fake_generator.py --once   # runs once and stops
```

---

### Phase 4: Infrastructure (Docker Containers)

#### Step 4 → `docker-compose.yml`
📍 **File:** `Banking_project/docker-compose.yml`
📚 **Detailed explanation:** `docs/Docker_Compose_Explained.md`

**What to learn:** This starts 8 containers:

| # | Container | Port | Purpose |
|---|-----------|------|---------|
| 1 | Zookeeper | 2181 | Manages Kafka |
| 2 | Kafka | 9092, 29092 | Message broker |
| 3 | Debezium Connect | 8083 | Watches Postgres for changes |
| 4 | PostgreSQL (Banking) | 5432 | Stores banking data |
| 5 | Airflow Init | — | One-time setup (exits after) |
| 6 | Airflow Webserver | 8080 | Pipeline UI |
| 7 | Airflow Scheduler | — | Runs scheduled tasks |
| 8 | Airflow Postgres | 5433 | Airflow's internal database |

**How to run:**
```bash
cd Banking_project
docker compose up -d      # start all containers in background
docker compose ps         # check which containers are running
docker compose logs kafka # see logs for a specific container
docker compose down       # stop everything
```

#### Step 4b → `docker-airflow.dockerfile`
📍 **File:** `Banking_project/docker-airflow.dockerfile`

**What to learn:** Only 3 lines — builds a custom Airflow image with dbt installed.

```dockerfile
FROM apache/airflow:2.9.3    # Start from official Airflow image
USER airflow                 # Switch to the airflow user
RUN pip install dbt-core dbt-snowflake   # Install dbt packages
```

---

### Phase 5: CDC — Change Data Capture (The Magic)

#### Step 5 → `kafka/generate_and_post.py`
📍 **File:** `Banking_project/kafka/generate_and_post.py`

**What to learn:** This is where CDC gets activated.

**What it does:**
1. Builds a JSON configuration for the Debezium Postgres connector
2. Sends a POST request to Debezium's REST API at `http://localhost:8083/connectors`
3. Debezium then starts watching these tables: `customers`, `accounts`, `transactions`

**After this script runs, the CDC flow is:**
```
Any INSERT/UPDATE/DELETE in Postgres
        ↓
Debezium reads the WAL log
        ↓
Converts to JSON event
        ↓
Publishes to Kafka topics:
  • banking_server.public.customers
  • banking_server.public.accounts
  • banking_server.public.transactions
```

**Key concept:** `snapshot.mode: initial` means Debezium first captures ALL existing data in the tables, then continues capturing new changes.

**How to run:**
```bash
python kafka/generate_and_post.py
# Output: ✅ Connector created successfully!
```

---

### Phase 6: Consuming Data (Kafka → S3)

#### Step 6 → `AWS_S3/kafka_to_s3.py`
📍 **File:** `Banking_project/AWS_S3/kafka_to_s3.py`

**What to learn:** This is the final piece — reading events from Kafka and storing them in S3.

**What it does step by step:**
1. Connects to Kafka at `localhost:29092` (external port for Windows)
2. Subscribes to all 3 topics
3. For each event:
   - Extracts the `payload.after` field (the actual row data)
   - Buffers records in memory
4. When buffer reaches 50 records:
   - Converts to Pandas DataFrame
   - Saves as `.parquet` file
   - Uploads to S3: `s3://bucket/table_name/date=YYYY-MM-DD/file.parquet`
   - Deletes the local parquet file

**S3 folder structure:**
```
s3://banking-data-lake-samba/
├── customers/
│   └── date=2026-02-10/
│       └── customers_143022123456.parquet
├── accounts/
│   └── date=2026-02-10/
│       └── accounts_143025654321.parquet
└── transactions/
    └── date=2026-02-10/
        └── transactions_143028987654.parquet
```

**Key concept:** Parquet is a columnar file format that is much faster and smaller than CSV/JSON. Data lakes use Parquet because tools like Snowflake, Spark, and Athena can read it very efficiently.

**How to run:**
```bash
python AWS_S3/kafka_to_s3.py
# Output: ✅ Connected to Kafka. Listening for messages...
# Output: [banking_server.public.customers] -> {id: 1, first_name: "John", ...}
```

---

### Phase 7: Testing (Verify Each Piece Works)

#### Step 7a → `test_kafka.py`
📍 **File:** `Banking_project/test_kafka.py`

**Purpose:** Check if Kafka is working — lists topics, counts messages, reads sample events.

```bash
python test_kafka.py
# Output: ✅ Topic 'banking_server.public.customers' exists!
# Output: Total messages: 150
```

#### Step 7b → `test_s3.py`
📍 **File:** `Banking_project/test_s3.py`

**Purpose:** Check if AWS S3 connection works — lists buckets, uploads a test file.

```bash
python test_s3.py
# Output: Connected to AWS S3
# Output: ✅ Test file uploaded to s3://your-bucket/test/hello.txt
```

---

## 🚀 Complete Startup Order (How to Run the Whole Pipeline)

```
 STEP    WHAT TO DO                           WHERE                    COMMAND
──────────────────────────────────────────────────────────────────────────────
  1     Start all Docker containers          Terminal 1               docker compose up -d
  2     Wait ~30 seconds for containers to be ready
  3     Create database tables               pgAdmin/psql             Run schema.sql
  4     Register Debezium connector          Terminal 2               python kafka/generate_and_post.py
  5     (Optional) Test Kafka                Terminal 2               python test_kafka.py
  6     (Optional) Test S3                   Terminal 2               python test_s3.py
  7     Start fake data generator            Terminal 3               python data_generator/fake_generator.py
  8     Start Kafka → S3 consumer            Terminal 4               python AWS_S3/kafka_to_s3.py
  9     Open Airflow UI                      Browser                  http://localhost:8080
                                                                      (admin / admin)
```

After step 8, your pipeline is fully running:
- `fake_generator.py` inserts data into Postgres every 3 seconds
- Debezium captures every INSERT and sends it to Kafka
- `kafka_to_s3.py` reads from Kafka and uploads Parquet files to S3
- Airflow orchestrates/schedules dbt transformations on Snowflake

---

## 📊 Technologies Used — Summary

| Technology | Role | Analogy |
|-----------|------|---------|
| **Python + Faker** | Generate fake data | The factory that makes products |
| **PostgreSQL** | Store banking data | The warehouse |
| **Debezium** | Capture every DB change | Security camera on the warehouse |
| **Apache Kafka** | Stream events | The conveyor belt |
| **Zookeeper** | Manage Kafka | The factory manager |
| **AWS S3** | Store data as files | The archive/cold storage |
| **Parquet** | File format | The box used for packaging |
| **dbt** | Transform data | The quality inspector |
| **Snowflake** | Cloud data warehouse | The final showroom |
| **Apache Airflow** | Orchestrate everything | The shift supervisor |
| **Docker Compose** | Run all services | The power switch for the factory |
