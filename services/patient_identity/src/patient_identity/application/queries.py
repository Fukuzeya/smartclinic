"""Read-side queries for the Patient Identity context.

Patient Identity is not event-sourced, so queries target the ORM table
directly via the repository. In a heavier CQRS split we would have a
separate read-model projection table — for this context the write-side
table is adequate given the low read cardinality and the lack of
aggregation requirements.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from shared_kernel.application.query import Query


class GetPatient(Query):
    """Fetch one patient by their opaque ``PatientId``."""

    patient_id: uuid.UUID


class FindPatientByNationalId(Query):
    """Lookup a patient by their Zimbabwean national ID.

    Returns ``None`` if no match, not ``NotFound``, because callers use
    this for duplicate-detection at registration time.
    """

    national_id: str = Field(min_length=11, max_length=16)


class SearchPatients(Query):
    """Free-text name search across the patient register.

    Returns a paginated list ordered by family name. ILIKE on the
    ``family_name`` column; a GIN + ``pg_trgm`` index on ``family_name``
    should be added in the migration for production-volume datasets.
    """

    name_fragment: str = Field(
        default="",
        max_length=100,
        description=(
            "Case-insensitive substring match against family name. "
            "Empty string returns all patients (paginated)."
        ),
    )
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
