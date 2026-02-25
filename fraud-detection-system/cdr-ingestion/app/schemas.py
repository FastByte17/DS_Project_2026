"""Pydantic models for CDR data validation"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class CDRRecord(BaseModel):
    """Call Detail Record schema"""
    
    customer_id: str = Field(..., description="Unique customer identifier")
    full_name: str = Field(..., description="Customer full name")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score between 0-100")
    city: str = Field(..., description="Customer city")
    mobile_number: str = Field(..., description="Customer mobile number")
    sim_serial_number: str = Field(..., description="SIM card serial number")
    sim_status: str = Field(..., description="SIM status: active, inactive, suspended")
    imei: str = Field(..., description="Device IMEI number")
    fraud_flag: bool = Field(default=False, description="Whether transaction is flagged as fraudulent")
    fraud_type: Optional[str] = Field(None, description="Type of fraud if detected")
    transaction_id: str = Field(..., description="Unique transaction identifier")
    time_stamp: datetime = Field(..., description="Transaction timestamp")
    type: str = Field(..., description="Transaction type")
    amount_eur: float = Field(..., ge=0, description="Transaction amount in EUR")
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CUST-001234",
                "full_name": "John Doe",
                "risk_score": 25.5,
                "city": "Helsinki",
                "mobile_number": "+358123456789",
                "sim_serial_number": "SIM1234567890",
                "sim_status": "active",
                "imei": "356938035643809",
                "fraud_flag": False,
                "fraud_type": None,
                "transaction_id": "TXN-20260216-001234",
                "time_stamp": "2026-02-16T10:30:00Z",
                "type": "payment",
                "amount_eur": 150.00
            }
        }


class CDRIngestionResponse(BaseModel):
    """Response model for CDR ingestion"""
    
    status: str = Field(..., description="Status of ingestion: accepted, rejected, error")
    transaction_id: str = Field(..., description="Transaction ID of the processed record")
    message: str = Field(..., description="Details message")


class HealthResponse(BaseModel):
    """Health check response model"""
    
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status: healthy or degraded")
    version: str = Field(..., description="Service version")

