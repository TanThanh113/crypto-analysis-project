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
parser.add_argument(
    "--yes-i-understand-this-deletes-data",
    action="store_true",
    help="Required confirmation flag for destructive catalog deletion.",
)

# The --db and --table flags allow overwriting database/table names from the command line (default is taken from .env).
parser.add_argument("--db", type=str, default=os.environ.get("ICEBERG_DB", "raw_crypto_batch"))
parser.add_argument("--table", type=str, default=os.environ.get("ICEBERG_TABLE", "raw_market_data"))

args = parser.parse_args()


def get_env_with_legacy(primary, legacy):
    value = os.environ.get(primary)
    if value:
        return value

    legacy_value = os.environ.get(legacy)
    if legacy_value:
        print(f"[warning] {legacy} is deprecated; use {primary} instead.")
    return legacy_value


GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
GCS_BUCKET_NAME = get_env_with_legacy("GCS_BUCKET_NAME", "GCP_BUCKET_NAME")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")
ICEBERG_WAREHOUSE = os.environ.get(
    "ICEBERG_WAREHOUSE",
    f"bq://projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}"
)

def print_delete_plan():
    print("[danger] Iceberg catalog deletion requested.")
    print(f"[danger] Project: {GCP_PROJECT_ID}")
    print(f"[danger] GCS bucket: {GCS_BUCKET_NAME}")
    print(f"[danger] Location: {GCP_LOCATION}")
    print(f"[danger] Warehouse: {ICEBERG_WAREHOUSE}")
    print(f"[danger] Mode: {args.mode}")

    if args.mode == "table":
        print(f"[danger] Namespace: {args.db}")
        print(f"[danger] Table: {args.table}")
    elif args.mode == "namespace":
        print(f"[danger] Namespace: {args.db}")
        print("[danger] All tables in this namespace may be deleted.")
    else:
        print("[danger] All namespaces and all tables in the catalog may be deleted.")


def require_delete_confirmation() -> bool:
    print_delete_plan()

    if args.yes_i_understand_this_deletes_data:
        return True

    print(
        "[fail-safe] No data was deleted. Re-run with "
        "--yes-i-understand-this-deletes-data to confirm this destructive action."
    )
    return False


def init_catalog():
    print(f"Connecting to GCP BigLake... [Mode: {args.mode.upper()}]")

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())

    return load_catalog(
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
    if not require_delete_confirmation():
        return 1

    catalog = init_catalog()

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
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
