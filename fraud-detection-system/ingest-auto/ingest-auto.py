import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

DEFAULT_URL = "http://localhost:8080"
DEFAULT_BATCH_SIZE = 20
DEFAULT_DELAY = 0.0
DEFAULT_DATASET = os.path.join(
    os.path.dirname(__file__),
    "..",
    "cdr-ingestion",
    "app",
    "telecom_fraud_dataset.json",
)


def load_records(dataset_path: str) -> list[dict]:
    """flatten the dataset's customers + transaction_logs into individual CDR records."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for customer in data["customers"]:
        base = {
            "customer_id": customer["customer_id"],
            "full_name": customer["full_name"],
            "risk_score": round(customer["risk_score"] / 100.0, 4),  # normalize 0-100 → 0.0-1.0 for ml_service
            "city": customer["contact_info"]["city"],
            "mobile_number": customer["telecom_info"]["mobile_number"],
            "sim_serial_number": customer["telecom_info"]["sim_id_iccid"],
            "sim_status": customer["telecom_info"]["sim_status"].lower(),
            "imei": customer["device_info"]["imei"],
            "fraud_flag": customer["fraud_flags"]["flagged_for_fraud"],
            "fraud_type": customer["fraud_flags"]["fraud_type"],
        }
        for txn in customer.get("transaction_logs", []):
            record = {
                **base,
                "transaction_id": txn["transaction_id"],
                "time_stamp": txn["timestamp"],
                "type": txn["type"],
                "amount_eur": txn["amount_eur"],
            }
            records.append(record)

    return records


def post_json(url: str, payload: dict | list) -> tuple[int, dict]:
    """send a POST request with JSON body; return (status_code, response_dict)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def send_batches(records: list[dict], base_url: str, batch_size: int, delay: float):
    endpoint = f"{base_url.rstrip('/')}/ingest/batch"
    total = len(records)
    accepted = rejected = 0

    for start in range(0, total, batch_size):
        batch = records[start : start + batch_size]
        batch_num = start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"Batch {batch_num}/{total_batches} ({len(batch)} records)...", end=" ", flush=True)
        status, resp = post_json(endpoint, batch)

        if status == 202:
            a = resp.get("accepted", 0)
            r = resp.get("rejected", 0)
            accepted += a
            rejected += r
            print(f"accepted={a}, rejected={r}")
            if r > 0:
                for err in resp.get("errors", []):
                    print(f"  [REJECTED] txn={err.get('transaction_id', '?')} — {err.get('error', '')}")
        else:
            print(f"HTTP {status}: {resp}")

        if delay > 0 and start + batch_size < total:
            time.sleep(delay)

    print(f"\nDone. Total records: {total} | Accepted: {accepted} | Rejected: {rejected}")


def main():
    parser = argparse.ArgumentParser(description="auto-ingest CDR records into the cdr-ingestion service.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"base URL of the service (default: {DEFAULT_URL})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"records per batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"seconds to wait between batches (default: {DEFAULT_DELAY})")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="path to telecom_fraud_dataset.json")
    args = parser.parse_args()

    if not os.path.isfile(args.dataset):
        print(f"dataset not found: {args.dataset}", file=sys.stderr)
        sys.exit(1)

    print(f"loading dataset: {args.dataset}")
    records = load_records(args.dataset)
    print(f"loaded {len(records)} CDR records (flattened from customers + transaction logs)")

    print(f"target: {args.url}/ingest/batch | batch_size={args.batch_size} | delay={args.delay}s\n")
    send_batches(records, args.url, args.batch_size, args.delay)


if __name__ == "__main__":
    main()
