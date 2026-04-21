"""Patient Identity — domain layer.

Pure Python. No SQLAlchemy, no FastAPI, no RabbitMQ. Every dependency
here must be a Pydantic model, a Python stdlib primitive, or something
imported from :mod:`shared_kernel.domain` / :mod:`shared_kernel.types`.

The import-graph fitness functions (``libs/shared_kernel/tests/fitness``)
will fail the CI build if anything in this package reaches into
``infrastructure`` or into another bounded context.
"""

from patient_identity.domain.events import (
    ConsentGranted,
    ConsentRevoked,
    DemographicsUpdated,
    PatientRegistered,
)
from patient_identity.domain.patient import Patient
from patient_identity.domain.repository import PatientRepository
from patient_identity.domain.value_objects import (
    Address,
    Consent,
    ConsentPurpose,
    DateOfBirth,
    NextOfKin,
    Sex,
)

__all__ = [
    "Address",
    "Consent",
    "ConsentGranted",
    "ConsentPurpose",
    "ConsentRevoked",
    "DateOfBirth",
    "DemographicsUpdated",
    "NextOfKin",
    "Patient",
    "PatientRegistered",
    "PatientRepository",
    "Sex",
]
