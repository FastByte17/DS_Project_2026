import json
import random
import uuid
from datetime import datetime, timedelta

NUM_CUSTOMERS = 100
TRANSACTIONS_PER_CUSTOMER = random.randint(5, 20)

cities = ["Helsinki", "Espoo", "Tampere", "Oulu", "Turku"]
device_models = ["iPhone 14", "Samsung S22", "Xiaomi 13", "OnePlus 11", "Pixel 8"]
fraud_types = [None, "SIM_SWAP", "IMEI_CLONE", "ROAMING_ABUSE"]

def random_date():
    return datetime.now() - timedelta(days=random.randint(0, 365))

def generate_imei():
    return str(random.randint(350000000000000, 359999999999999))

def generate_iccid():
    return "8943581" + str(random.randint(100000000000, 999999999999))

def generate_mobile():
    return "+3584" + str(random.randint(10000000, 99999999))

def generate_henkilotunnus():
    return str(random.randint(100000, 311299)) + "-" + str(random.randint(100, 999)) + random.choice("ABCDEF")

def generate_transactions(customer_id):
    transactions = []
    for _ in range(random.randint(5, 20)):
        txn_type = random.choice([
            "RECHARGE",
            "SIM_SWAP",
            "INTERNATIONAL_CALL",
            "DEVICE_CHANGE",
            "DATA_USAGE",
            "ROAMING_ACTIVATION"
        ])
        transactions.append({
            "transaction_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "type": txn_type,
            "amount_eur": round(random.uniform(5, 100), 2),
            "timestamp": random_date().isoformat()
        })
    return transactions

customers = []

for i in range(NUM_CUSTOMERS):
    customer_id = f"CUST-{i+1:04d}"
    fraud_flag = random.choice([True, False, False])  # more normal than fraud
    fraud_type = random.choice(fraud_types) if fraud_flag else None

    customer = {
        "customer_id": customer_id,
        "full_name": f"Customer_{i+1}",
        "henkilotunnus": generate_henkilotunnus(),
        "risk_score": random.randint(1, 100),
        "kyc_verified": random.choice([True, False]),
        "contact_info": {
            "email": f"user{i+1}@testmail.fi",
            "city": random.choice(cities)
        },
        "telecom_info": {
            "mobile_number": generate_mobile(),
            "sim_id_iccid": generate_iccid(),
            "stc_serial_number": "STC-" + str(random.randint(10000000, 99999999)),
            "sim_swap_count_last_12_months": random.randint(0, 5),
            "sim_status": random.choice(["Active", "Suspended"])
        },
        "device_info": {
            "imei": generate_imei(),
            "device_model": random.choice(device_models),
            "device_change_count": random.randint(0, 6)
        },
        "fraud_flags": {
            "flagged_for_fraud": fraud_flag,
            "fraud_type": fraud_type
        },
        "transaction_logs": generate_transactions(customer_id)
    }

    customers.append(customer)

with open("telecom_fraud_dataset.json", "w") as f:
    json.dump({"customers": customers}, f, indent=4)

print("✅ 100 Customers with transaction logs generated successfully!")
