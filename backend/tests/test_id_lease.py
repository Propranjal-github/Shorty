from __future__ import annotations

from datetime import timedelta

from app.core.id_generator import MAX_MACHINE_ID
from app.core.time import utcnow
from app.models import MachineIdLease
from app.services.id_lease import lease_machine_id, release_machine_id


def test_lease_returns_valid_id(db) -> None:  # type: ignore[no-untyped-def]
    mid = lease_machine_id(db)
    assert 1 <= mid <= MAX_MACHINE_ID
    assert db.query(MachineIdLease).filter_by(machine_id=mid).first() is not None


def test_consecutive_leases_are_distinct(db) -> None:  # type: ignore[no-untyped-def]
    a = lease_machine_id(db)
    b = lease_machine_id(db)
    assert a != b


def test_release_frees_machine_id(db) -> None:  # type: ignore[no-untyped-def]
    mid = lease_machine_id(db)
    release_machine_id(db, mid)
    assert db.query(MachineIdLease).filter_by(machine_id=mid).first() is None


def test_expired_lease_is_reaped(db) -> None:  # type: ignore[no-untyped-def]
    mid = lease_machine_id(db)
    db.query(MachineIdLease).filter_by(machine_id=mid).update(
        {MachineIdLease.expires_at: utcnow() - timedelta(seconds=1)}
    )
    db.commit()
    # reaping happens inside the next lease call; should not raise
    new_mid = lease_machine_id(db)
    assert 1 <= new_mid <= MAX_MACHINE_ID
