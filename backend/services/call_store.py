"""
In-memory call store.
In production, replace with a proper database (PostgreSQL, Redis, etc.)
This module exposes a simple async interface so swapping backends is painless.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, List

from models.schemas import CallRecord, CallStatus, ScenarioType


class CallStore:
    """Thread-safe in-memory store for call records."""

    def __init__(self):
        self._store: Dict[str, CallRecord] = {}

    def create(
        self,
        phone_number: str,
        scenario_type: ScenarioType,
        customer_name: str,
        custom_params: dict,
    ) -> CallRecord:
        call_id = str(uuid.uuid4())
        record = CallRecord(
            call_id=call_id,
            phone_number=phone_number,
            scenario_type=scenario_type,
            customer_name=customer_name,
            status=CallStatus.INITIATED,
            started_at=datetime.utcnow(),
            custom_params=custom_params,
        )
        self._store[call_id] = record
        return record

    def get(self, call_id: str) -> Optional[CallRecord]:
        return self._store.get(call_id)

    def get_by_vapi_id(self, vapi_call_id: str) -> Optional[CallRecord]:
        for record in self._store.values():
            if record.vapi_call_id == vapi_call_id:
                return record
        return None

    def update(self, call_id: str, **kwargs) -> Optional[CallRecord]:
        record = self._store.get(call_id)
        if not record:
            return None
        updated = record.model_copy(update=kwargs)
        self._store[call_id] = updated
        return updated

    def list_all(self) -> List[CallRecord]:
        return sorted(
            self._store.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )


# Singleton store
call_store = CallStore()
