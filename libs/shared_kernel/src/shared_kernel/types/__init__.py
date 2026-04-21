"""Pan-clinical value objects.

These types are **universally stable** across the clinic — a ``PatientId``
or a ``Money`` amount means the same thing to every context. Context-specific
value objects (``ICD10Code``, ``Dosage``, ``VitalReading``) live in the
owning context's own domain package, not here.
"""

from shared_kernel.types.clock import Clock, FrozenClock, SystemClock
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import (
    AppointmentId,
    BillId,
    DispensingId,
    DoctorId,
    EncounterId,
    Identifier,
    LabOrderId,
    PatientId,
    PrescriptionId,
    new_uuid7,
)
from shared_kernel.types.money import Currency, Money
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

__all__ = [
    "AppointmentId",
    "BillId",
    "Clock",
    "Currency",
    "DispensingId",
    "DoctorId",
    "Email",
    "EncounterId",
    "FrozenClock",
    "Identifier",
    "LabOrderId",
    "Money",
    "PatientId",
    "PersonName",
    "PhoneNumber",
    "PrescriptionId",
    "SystemClock",
    "ZimbabweanNationalId",
    "new_uuid7",
]
