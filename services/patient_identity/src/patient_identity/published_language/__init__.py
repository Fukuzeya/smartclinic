"""Patient Identity — Published Language.

The schemas exported from this package are the **wire contract** for
every event this service emits. Downstream contexts (Scheduling,
Clinical, Billing, …) import ONLY from here — never from
``patient_identity.domain``. This boundary means:

* Internal domain model restructurings do not ripple out.
* The ``v1`` suffix is a compatibility promise: existing fields
  stay backward-compatible; new optional fields may be added;
  breaking changes introduce a ``v2`` alongside ``v1`` with a
  migration window (ADR 0008).

Consumers validate inbound events against these Pydantic models.
Unknown fields are silently ignored (``extra="allow"`` on receiving
side) to stay forward-compatible.
"""

from patient_identity.published_language.events_v1 import (
    PatientConsentGrantedV1,
    PatientConsentRevokedV1,
    PatientDemographicsUpdatedV1,
    PatientRegisteredV1,
)

__all__ = [
    "PatientConsentGrantedV1",
    "PatientConsentRevokedV1",
    "PatientDemographicsUpdatedV1",
    "PatientRegisteredV1",
]
