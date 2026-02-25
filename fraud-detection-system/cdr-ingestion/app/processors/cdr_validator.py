"""CDR validation logic"""
import re
from typing import Dict, Tuple

PHONE_PATTERN = r'^\+?[1-9]\d{1,14}$'
IMEI_PATTERN = r'^\d{15}$'
VALID_SIM_STATUSES = {"active", "inactive", "suspended", "blocked"}


def validate_customer_id(customer_id: str) -> tuple[bool, str]:
    """Validate customer ID"""
    if not customer_id or not isinstance(customer_id, str):
        return False, "Customer ID must be a non-empty string"
    if len(customer_id) < 5 or len(customer_id) > 50:
        return False, "Customer ID must be between 5 and 50 characters"
    return True, ""


def validate_phone_number(phone: str) -> tuple[bool, str]:
    """Validate phone number format (E.164 standard)"""
    if not phone or not isinstance(phone, str):
        return False, "Phone number must be a non-empty string"
    return (True, "") if re.match(PHONE_PATTERN, phone) else (False, f"Invalid phone format: {phone}")


def validate_imei(imei: str) -> tuple[bool, str]:
    """Validate IMEI number"""
    if not imei or not isinstance(imei, str):
        return False, "IMEI must be a non-empty string"
    if not re.match(IMEI_PATTERN, imei):
        return False, f"Invalid IMEI format: {imei}. Must be 15 digits"
    return True, ""


def validate_risk_score(risk_score: float) -> tuple[bool, str]:
    """Validate risk score"""
    if not isinstance(risk_score, (int, float)):
        return False, "Risk score must be a number"
    if risk_score < 0 or risk_score > 100:
        return False, "Risk score must be between 0 and 100"
    return True, ""


def validate_amount(amount: float) -> tuple[bool, str]:
    """Validate transaction amount"""
    if not isinstance(amount, (int, float)):
        return False, "Amount must be a number"
    if amount < 0:
        return False, "Amount cannot be negative"
    return True, ""


def validate_sim_status(sim_status: str) -> tuple[bool, str]:
    """Validate SIM status"""
    if sim_status not in VALID_SIM_STATUSES:
        return False, f"Invalid SIM status: {sim_status}"
    return True, ""


def validate_transaction_id(transaction_id: str) -> tuple[bool, str]:
    """Validate transaction ID"""
    if not transaction_id or not isinstance(transaction_id, str):
        return False, "Transaction ID must be a non-empty string"
    if len(transaction_id) < 5 or len(transaction_id) > 100:
        return False, "Transaction ID must be between 5 and 100 characters"
    return True, ""


def validate_cdr(cdr: Dict) -> Tuple[bool, str]:
    """Comprehensive CDR record validation"""
    validators = [
        (validate_customer_id(cdr.get("customer_id", "")), "Customer ID"),
        (validate_phone_number(cdr.get("mobile_number", "")), "Mobile number"),
        (validate_imei(cdr.get("imei", "")), "IMEI"),
        (validate_risk_score(cdr.get("risk_score", -1)), "Risk score"),
        (validate_amount(cdr.get("amount_eur", -1)), "Amount"),
        (validate_sim_status(cdr.get("sim_status", "")), "SIM status"),
        (validate_transaction_id(cdr.get("transaction_id", "")), "Transaction ID"),
    ]
    
    for (is_valid, msg), field in validators:
        if not is_valid:
            return False, f"{field} validation failed: {msg}"
    
    if "time_stamp" not in cdr:
        return False, "Time stamp is required"
    
    if not cdr.get("full_name"):
        return False, "Full name is required"
    
    if not cdr.get("city"):
        return False, "City is required"
    
    if not cdr.get("sim_serial_number"):
        return False, "SIM serial number is required"
    
    if not cdr.get("type"):
        return False, "Transaction type is required"
    
    return True, "CDR record is valid"
