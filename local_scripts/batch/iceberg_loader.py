# -*- coding: utf-8 -*-

import os
import uuid
import glob
import logging
import sys
import pyarrow.parquet as pq
from pyiceberg.catalog import load_catalog
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.exceptions import NamespaceAlreadyExistsError

import google.auth
from google.auth.transport.requests import Request

from pyiceberg.transforms import DayTransform, IdentityTransform
from dotenv import load_dotenv
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField,
    StringType,
    LongType,
    DoubleType,
    TimestamptzType,
    TimestampType,
    BooleanType,
    DecimalType
)
import pyarrow as pa
import pyarrow.compute as pc

load_dotenv()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


def get_gcs_bucket_name():
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if bucket_name:
        return bucket_name

    legacy_bucket_name = os.environ.get("GCP_BUCKET_NAME")
    if legacy_bucket_name:
        logging.warning("GCP_BUCKET_NAME is deprecated; use GCS_BUCKET_NAME instead.")
    return legacy_bucket_name


# =========================================================
# CONFIG 
# =========================================================
# Config GCS (No default value)
GCS_BUCKET_NAME = get_gcs_bucket_name()
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data")

ICEBERG_WAREHOUSE = os.environ.get(
    "ICEBERG_WAREHOUSE",
    f"bq://projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}"
)

# Config Iceberg
CATALOG_NAME = os.environ.get("ICEBERG_CATALOG", "gcs_catalog") # Name of the Iceberg Catalog
NAMESPACE = os.environ.get("ICEBERG_DB", "raw_crypto_batch") # Namespace of the Iceberg Table (same folder)
TABLE_NAME = os.environ.get("ICEBERG_TABLE", "raw_market_data") # Name of the Iceberg Table

BIGLAKE_METASTORE_URI = os.environ.get("BIGLAKE_METASTORE_URI", "https://biglake.googleapis.com/iceberg/v1/restcatalog")

# Allows customization of the Parquet file name to search for (for reuse in other threads).
FILE_PATTERN = os.environ.get("FILE_PATTERN", "raw_data*.parquet")
# Customize the column used for partitioning (Default: 'date')
PARTITION_COL = os.environ.get("ICEBERG_PARTITION_COL", "date")

# Full table identifier(path to the folder data)
FULL_TABLE_IDENTIFIER = f"{NAMESPACE}.{TABLE_NAME}"

# Check if the GCS_BUCKET_NAME is set
if not GCS_BUCKET_NAME:
    logging.error("❌ GCS_BUCKET_NAME is missing from the environment variable.")
    sys.exit(1)

# =========================================================
# ICEBERG FUNCTIONS
# =========================================================
# Convert Arrow schema to Iceberg schema
# Note: - Apache Arrow is a framework used for processing data in RAM.
#       - Iceberg is a columnar storage format that is designed to be fast and easy to use.
def arrow_to_iceberg_schema(arrow_schema):
    # Save the column names after converting from arrow to iceberg
    fields = []

    # Take each column out and number each column(start from 1)
    # Note: Because Iceberg's columns need IDs called field_id.
    for idx, field in enumerate(arrow_schema, start=1):
        pa_type = field.type

        if pa.types.is_string(pa_type): # String -> StringType
            iceberg_type = StringType()

        elif pa.types.is_integer(pa_type): # Integer -> LongType
            iceberg_type = LongType()

        elif pa.types.is_floating(pa_type): # Float -> DoubleType
            iceberg_type = DoubleType()

        elif pa.types.is_timestamp(pa_type): # Timestamp -> TimestamptzType(Time includes time zone)
            iceberg_type = TimestamptzType()

        elif pa.types.is_boolean(pa_type): # Boolean -> BooleanType
            iceberg_type = BooleanType()
        elif pa.types.is_decimal(pa_type): # Decimal -> DecimalType(38,18)(Maximum 38 digits, including 18 digits after the decimal point).
            iceberg_type = DecimalType(38, 18)

        else:
            logging.warning(f"Unsupported type {pa_type}, fallback to string")
            iceberg_type = StringType() # Fallback to StringType

        fields.append(
            NestedField(
                field_id=idx,
                name=field.name,
                field_type=iceberg_type,
                required=False # This column can be left blank - Null
            )
        )

    return Schema(*fields) # Return the schema

# Rearrange the columns of the Arrow data table so that they are in the correct order 
# and have the required number of columns as specified in the Iceberg table structure.
def align_table_schema(arrow_table, iceberg_schema):
    arrays = [] # Initialize a list to hold the column data.
    names = [] # Initialize the list to name the columns.

    # Iterate through each column according to the Iceberg table standard.
    for field in iceberg_schema.fields:
        col_name = field.name # Use Iceberg's current column name.
        names.append(col_name)

        # If the column name exists in the Arrow data table, add it to the list.
        if col_name in arrow_table.column_names:
            column = arrow_table[col_name]

            if pa.types.is_timestamp(column.type) and column.type.unit == 'ns':
                logging.info(f"🔄 Casting {col_name} from nanoseconds to microseconds to comply with Iceberg.")
                column = pc.cast(column, pa.timestamp('us', tz=column.type.tz), safe=False)

            arrays.append(column)
        else:
            # If this column is not present in the arrow, it will return a NULL list.
            arrays.append(pa.nulls(len(arrow_table)))

    # Combine all sorted (or recently Null-aligned) data columns into a single table.
    return pa.Table.from_arrays(arrays, names=names)

def init_catalog():
    """Establish a connection to GCP BigLake Metastore Catalog"""
    logging.info(f"🔗 Connect to GCP Lakehouse REST Catalog...")
    
    # 1. Automatically retrieve the standard token from the JSON file.
    # Note: Because PyIceberg's default token retrieval method is very poor, we will use a JSON file to retrieve the token.
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    gcp_token = credentials.token
    
    logging.info(f"🏢 Iceberg warehouse: {ICEBERG_WAREHOUSE}")

    # 2. Connect to the Catalog
    # Note: Here we will choose Google's BigLake Metastore as our catalog.
    catalog = load_catalog(
        CATALOG_NAME,
        **{
            # The connection mode will use REST (which means sending a URL and it will return the API data).
            "type": "rest",
            "uri": BIGLAKE_METASTORE_URI, 
            
            #IMPORTANT: The warehouse URL MUST be the original bucket URL.
            # Do not add "/iceberg_warehouse" at the end, as this is due to Google's API.
            # Use this URL to map to the catalog you created in Step 1!
            "warehouse": ICEBERG_WAREHOUSE,
            
            "token": gcp_token, # Send the token we just obtained.
            "header.x-goog-user-project": GCP_PROJECT_ID,
            "header.X-Iceberg-Access-Delegation": "",
            "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
            "gcs.project-id": GCP_PROJECT_ID
        }
    )
    return catalog
def get_or_create_table(catalog, sample_parquet_file):
    """Check and automatically generate tables based on the Schema of the Parquet file."""
    try:
        # Check if the Namespace exists
        try:
            if (NAMESPACE,) not in catalog.list_namespaces():
                namespace_properties = {
                    "location": f"gs://{GCS_BUCKET_NAME}/{NAMESPACE}",
                    "gcp-region": GCP_LOCATION,
                }
                catalog.create_namespace(NAMESPACE, properties=namespace_properties)
                logging.info(
                    f"📁 Created new federated Namespace: {NAMESPACE} "
                    f"at gs://{GCS_BUCKET_NAME}/{NAMESPACE}"
                )
        except NamespaceAlreadyExistsError:
            # If another thread is running in parallel, skip this step.
            logging.info(f"📁 Namespace {NAMESPACE} was just created by another parallel thread. Moving on!")
        except Exception as e:
            # Catching additional cases where BigLake returns a generic REST 409 error.
            if "ALREADY_EXISTS" in str(e) or "409" in str(e):
                logging.info(f"📁 Namespace {NAMESPACE} already exists (Caught 409 conflict).")
            else:
                raise

        # Try to load the table
        try:
            table = catalog.load_table(FULL_TABLE_IDENTIFIER)
            logging.info(f"✅ Table {FULL_TABLE_IDENTIFIER} already exists.")
            return table
        
        # If it doesn't exist, create it based on the Parquet file
        except Exception:
            logging.info(f"🏗️ Table {FULL_TABLE_IDENTIFIER} does not exist. Creating table {FULL_TABLE_IDENTIFIER} from sample Parquet file...")
            
            # 1. Read the Schema from the Parquet file
            sample_table = pq.read_table(sample_parquet_file)
            dynamic_schema = arrow_to_iceberg_schema(sample_table.schema)
            
            # 2. Build the Partition Spec
            try:
                # Find the partition column ID provided by the user/Kestra.
                partition_field = dynamic_schema.find_field(PARTITION_COL)
                partition_field_id = partition_field.field_id

                # Iceberg's grouping conditions
                if isinstance(partition_field.field_type, (TimestamptzType, TimestampType)):
                    transform = DayTransform()
                    part_name = f"{PARTITION_COL}_day"
                else:
                    transform = IdentityTransform()
                    part_name = f"{PARTITION_COL}_part"
                
                # Create the Partition Spec
                partition_spec = PartitionSpec(
                    PartitionField(source_id=partition_field_id, field_id=1000, transform=transform, name=part_name)
                )
                logging.info(f"✂️ Partitioning has been configured by column: '{PARTITION_COL}'")
            except ValueError:
                # If the date column is not found, create an unpartitioned table.
                logging.warning(f"⚠️ Column '{PARTITION_COL}' not found in the data. This will create a table without partitions.")
                partition_spec = PartitionSpec()

            # 3. Instruct Iceberg to create a table on GCS.
            table = catalog.create_table(
                identifier=FULL_TABLE_IDENTIFIER,
                schema=dynamic_schema,
                partition_spec=partition_spec
            )
            logging.info(f"🎉 Table created successfully!")
            return table

    except Exception as e:
        logging.error(f"❌ Error creating table: {e}")
        raise

# =========================================================
# MAIN
# =========================================================
def main():
    logging.info(f"🚀 Starting Iceberg Loader for {FULL_TABLE_IDENTIFIER}")

    # 1. Scan for Parquet files based on the pattern passed in.
    # This function uses the glob library to search for all Parquet data files.
    # Note: "recursive=True" This allows it to delve deep into all the subdirectories inside so that no files are missed.
    search_pattern = os.path.join(OUTPUT_DIR,"**",FILE_PATTERN)
    parquet_files = glob.glob(search_pattern, recursive=True)
    
    if not parquet_files:
        logging.warning(f"⚠️ No Parquet files with the pattern '{FILE_PATTERN}' in {OUTPUT_DIR} were found. Ignore.")
        return

    # 2. Connect to Iceberg Catalog & Get Table (Transfer the first file as a sample)
    #  Note: Use the first file in the parquet file as a template to create the schema.
    catalog = init_catalog()
    table = get_or_create_table(catalog, sample_parquet_file=parquet_files[0])
    iceberg_schema = table.schema()

    # 3. Read each file and upload it to GCS via Iceberg.
    for file_path in parquet_files:
        logging.info(f"📦 Processing file {file_path}...")
        try:
            parquet_file = pq.ParquetFile(file_path)
            aligned_batches = []

            for batch in parquet_file.iter_batches(batch_size=100000):
                arrow_table_chunk = pa.Table.from_batches([batch])
                aligned_chunk = align_table_schema(arrow_table_chunk, iceberg_schema)
                
                for aligned_batch in aligned_chunk.to_batches():
                    aligned_batches.append(aligned_batch)
                
                # Giải phóng bộ nhớ RAM trung gian ngay lập tức
                del arrow_table_chunk
                del aligned_chunk

            if aligned_batches:
                final_table = pa.Table.from_batches(aligned_batches)
                
                logging.info(f"📤 Appending {final_table.num_rows} rows to Iceberg table...")
                table.append(final_table)
                
                del final_table
                del aligned_batches

            logging.info(f"✅ Successfully uploaded {file_path} as one single snapshot.")

            processed_dir = os.path.join(OUTPUT_DIR, "_processed")
            os.makedirs(processed_dir, exist_ok=True)
            processed_path = os.path.join(processed_dir, f"{uuid.uuid4()}_{os.path.basename(file_path)}")

            os.rename(file_path, processed_path)
            logging.info(f"✅ Cleaned up file: {file_path}")

        except Exception as e:
            logging.error(f"❌ Error while processing file {file_path}: {e}")

    logging.info("🎉 Iceberg Loader process complete!")

if __name__ == "__main__":
    main()
