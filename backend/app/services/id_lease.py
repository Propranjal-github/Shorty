from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.id_generator import MAX_MACHINE_ID
from app.core.time import utcnow
from app.models import MachineIdLease

LEASE_TTL_SECONDS = 600


def lease_machine_id(db: Session, *, ttl_seconds: int = LEASE_TTL_SECONDS) -> int:
    """Atomically claim a unique snowflake machine_id from the database.

    Expired leases are reaped first, then random candidate ids are INSERTed
    until one succeeds (the unique PK rejects collisions). Raises only if
    every id is currently held.
    """
    cutoff = utcnow() - timedelta(seconds=ttl_seconds)
    db.query(MachineIdLease).filter(MachineIdLease.expires_at < cutoff).delete()
    db.commit()

    expires_at = utcnow() + timedelta(seconds=ttl_seconds)
    start = random.randint(1, MAX_MACHINE_ID)
    for offset in range(MAX_MACHINE_ID):
        candidate = ((start + offset - 1) % MAX_MACHINE_ID) + 1
        db.add(MachineIdLease(machine_id=candidate, expires_at=expires_at))
        try:
            db.commit()
            return candidate
        except IntegrityError:
            db.rollback()
    raise RuntimeError("no free machine_id; too many live instances")


def renew_machine_id(db: Session, machine_id: int, *, ttl_seconds: int = LEASE_TTL_SECONDS) -> None:
    """Extend the expiry of a held lease. One UPDATE, ~0 cost."""
    new_expiry = utcnow() + timedelta(seconds=ttl_seconds)
    db.query(MachineIdLease).filter(MachineIdLease.machine_id == machine_id).update(
        {MachineIdLease.expires_at: new_expiry}
    )
    db.commit()


def release_machine_id(db: Session, machine_id: int) -> None:
    """Release a leased machine_id (best-effort on graceful shutdown)."""
    db.query(MachineIdLease).filter(MachineIdLease.machine_id == machine_id).delete()
    db.commit()
