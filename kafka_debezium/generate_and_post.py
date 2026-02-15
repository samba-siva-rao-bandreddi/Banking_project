import os
import json
import requests
from dotenv import load_dotenv
from pathlib import Path

root_dir = Path(__file__).parent.parent

load_dotenv(root_dir / ".env")

connector_config = {
    "name": "postgres-connector",
    "config": {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "database.hostname": os.getenv("POSTGRES_INTERNAL_HOST"),
        "database.port": os.getenv("POSTGRES_INTERNAL_PORT"),
        "database.user": os.getenv("POSTGRES_USER"),
        "database.password": os.getenv("POSTGRES_PASSWORD"),
        "database.dbname": os.getenv("POSTGRES_DB"),
        "topic.prefix": "banking_server",
        "table.include.list": "public.customers,public.accounts,public.transactions",
        "plugin.name": "pgoutput",
        "slot.name": "banking_slot",
        "publication.autocreate.mode": "filtered",
        "tombstones.on.delete": "false",
        "decimal.handling.mode": "double",
        "snapshot.mode": "initial",
    },
}
url = "http://localhost:8083/connectors"
headers = {"Content-Type": "application/json"}

response = requests.post(url, headers=headers, data=json.dumps(connector_config))


if response.status_code == 201:
    print("connector created successfully")

elif response.status_code == 409:
    print("connector already exists")
elif response.status_code == 400:
    print("bad request - Something is wrong with the connector_config")
elif response.status_code == 500:
    print("internal server error - Kafka or Postgres is not running")
else:
    print(f"failed to create connector: {response.status_code}: {response.text}")
