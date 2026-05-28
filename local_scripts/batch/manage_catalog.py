# -*- coding: utf-8 -*-

import argparse
import google.auth
from google.auth.transport.requests import Request
from pyiceberg.catalog import load_catalog
import os
from dotenv import load_dotenv

load_dotenv()
parser = argparse.ArgumentParser(description="Iceberg Catalog Management and Cleaning Tool")

parser.add_argument(
    "--mode", 
    type=str, 
    choices=["table", "namespace", "all"], 
    default="table",
    help="Mode: 'table' (delete 1 table), 'namespace' (delete 1 database), 'all' (delete all data)"
)

# The --db and --table flags allow overwriting database/table names from the command line (default is taken from .env).
parser.add_argument("--db", type=str, default=os.environ.get("ICEBERG_DB", "raw_crypto_batch"))
parser.add_argument("--table", type=str, default=os.environ.get("ICEBERG_TABLE", "raw_market_data"))

args = parser.parse_args()
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
GCP_BUCKET_NAME = os.environ.get("GCP_BUCKET_NAME")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")
ICEBERG_WAREHOUSE = os.environ.get(
    "ICEBERG_WAREHOUSE",
    f"bq://projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}"
)

print(f"⚔️ Connecting to GCP BigLake... [Mode: {args.mode.upper()}]")

# Get Token
credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
credentials.refresh(Request())

# Create Catalog
catalog = load_catalog(
    "gcs_catalog",
    **{
        "type": "rest",
        "uri": "https://biglake.googleapis.com/iceberg/v1/restcatalog",
        "warehouse": ICEBERG_WAREHOUSE,
        "token": credentials.token,
        "header.x-goog-user-project": GCP_PROJECT_ID,
    }
)

def delete_single_table(cat, ns, tbl):
    identifier = f"{ns}.{tbl}"
    try:
        cat.drop_table(identifier)
        print(f"   ✅ Table deleted: {identifier}")
    except Exception as e:
        print(f"   ⚠️ Skipping (Table may have already been deleted): {identifier}")

def delete_single_namespace(cat, ns):
    print(f"\n🔍  Deleting namespace: '{ns}'...") 
    try:
        tables = cat.list_tables(ns)
        for table in tables:
            delete_single_table(cat, table[0], table[1])
        
        cat.drop_namespace(ns)
        print(f"\n💥 Namespace deleted: '{ns}'")
    except Exception as e:
        print(f"⚠️ Error deleting namespace: {ns}: {e}")

def main():
    try:
        if args.mode == "table":
            print(f"🎯 Purpose: Delete the table '{args.db}.{args.table}'")
            delete_single_table(catalog, args.db, args.table)

        elif args.mode == "namespace":
            print(f"🎯 Purpose: Delete the namespace '{args.db}' and all tables within.")
            delete_single_namespace(catalog, args.db)

        elif args.mode == "all":
            print(f"🎯 Purpose: Delete all data in the catalog.")
            namespaces = catalog.list_namespaces()
            if not namespaces:
                print("   🤷 Catalog is empty!")
            else:
                for ns in namespaces:
                    delete_single_namespace(catalog, ns[0])
            print("\n🎉 SYSTEM CLEANED UP!")

    except Exception as e:
        print(f"⚠️ System error: {e}")

if __name__ == "__main__":
    main()