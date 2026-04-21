"""Laboratory Published Language — integration events consumed by other contexts.

These are stable, versioned contracts.  The Clinical context subscribes to
``laboratory.order.results_available.v1`` to update the encounter read model.
The Billing context subscribes to generate a charge line for lab work.
"""

from __future__ import annotations

# Re-export the integration events that are part of the published language.
# Other contexts depend ONLY on these; internal domain events are not exported.
from laboratory.domain.events import (  # noqa: F401
    CriticalResultAlertV1,
    LabOrderCancelledV1,
    LabOrderReceivedV1,
    LabResultsAvailableV1,
    ResultRecordedV1,
    SampleCollectedV1,
)

__all__ = [
    "LabOrderReceivedV1",
    "SampleCollectedV1",
    "ResultRecordedV1",
    "LabResultsAvailableV1",
    "CriticalResultAlertV1",
    "LabOrderCancelledV1",
]
