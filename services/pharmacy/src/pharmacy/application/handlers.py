"""Pharmacy command handlers.

The ``DispensePrescriptionHandler`` is the core of the Pharmacy context —
it orchestrates:

1. Load the ``Prescription`` aggregate.
2. Build a ``DispensableCandidate`` VO from stock + consent + RxNav data.
3. Run the composed specification chain.
4. If satisfied → call ``prescription.dispense()``.
   If violated → call ``prescription.reject(reasons=...)``.
5. Save aggregate, register with UoW, commit (outbox write included).

The specification chain is pure (no I/O); all I/O happens in this handler
before the spec is evaluated.  This keeps the domain completely testable
without mocking databases or HTTP clients.
"""

from __future__ import annotations

from shared_kernel.domain.specification import SpecificationViolation
from shared_kernel.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork

from pharmacy.acl.drug_interaction_port import DrugInteractionChecker, NullDrugInteractionChecker
from pharmacy.application.commands import (
    DispensePartialCommand,
    DispensePrescriptionCommand,
    RejectPrescriptionCommand,
)
from pharmacy.domain.specifications import (
    AllDrugsInStockSpecification,
    make_dispensable_specification,
    NoModerateDrugInteractionSpecification,
)
from pharmacy.domain.value_objects import DispensableCandidate
from pharmacy.infrastructure.repository import (
    SqlAlchemyPrescriptionRepository,
    SqlAlchemyStockRepository,
)


class DispensePrescriptionHandler:
    def __init__(
        self,
        uow_factory,
        interaction_checker: DrugInteractionChecker | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._checker = interaction_checker or NullDrugInteractionChecker()

    async def handle(self, cmd: DispensePrescriptionCommand) -> dict:
        """Dispense prescription after running the full specification chain.

        Returns a dict with ``outcome`` (``dispensed`` or ``rejected``) and
        ``reasons`` (list of violation strings, empty on success).
        """
        async with self._uow_factory() as uow:
            repo = SqlAlchemyPrescriptionRepository(uow.session)
            stock_repo = SqlAlchemyStockRepository(uow.session)

            prescription = await repo.get(cmd.prescription_id)
            drug_names = prescription.drug_names

            # Gather all inputs for the specification (no I/O inside specs)
            stock_levels = await stock_repo.get_for_drugs(drug_names)
            has_consent = await stock_repo.has_treatment_consent(prescription.patient_id)
            interactions = await self._checker.check_interactions(drug_names)

            candidate = DispensableCandidate(
                prescription_id=str(prescription.id),
                patient_id=prescription.patient_id,
                drug_names=drug_names,
                stock_levels=stock_levels,
                has_treatment_consent=has_consent,
                interactions=interactions,
            )

            spec = make_dispensable_specification()
            advisory_spec = NoModerateDrugInteractionSpecification()

            if spec.is_satisfied_by(candidate):
                prescription.dispense(dispensed_by=cmd.dispensed_by)
                await repo.save(prescription)
                uow.register(prescription)
                await uow.commit()
                # Collect advisory warnings even on success
                warnings = (
                    advisory_spec.reasons_for_failure(candidate)
                    if not advisory_spec.is_satisfied_by(candidate) else []
                )
                return {"outcome": "dispensed", "reasons": [], "warnings": warnings}
            else:
                reasons = spec.reasons_for_failure(candidate)
                # Identify specifically which drugs triggered an OOS failure so
                # the Saga Orchestrator can route a substitution-required compensation.
                oos_spec = AllDrugsInStockSpecification()
                out_of_stock_drugs = (
                    oos_spec.reasons_for_failure(candidate)
                    if not oos_spec.is_satisfied_by(candidate) else []
                )
                # Extract drug names from OOS reason strings for compact event payload
                oos_drug_names = [
                    name for name in candidate.drug_names
                    if any(name.upper() in r.upper() for r in out_of_stock_drugs)
                ]
                prescription.reject(
                    reasons=reasons,
                    rejected_by=cmd.dispensed_by,
                    out_of_stock_drugs=oos_drug_names,
                )
                await repo.save(prescription)
                uow.register(prescription)
                await uow.commit()
                return {
                    "outcome": "rejected",
                    "reasons": reasons,
                    "out_of_stock_drugs": oos_drug_names,
                    "warnings": [],
                }


class DispensePartialHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: DispensePartialCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyPrescriptionRepository(uow.session)
            prescription = await repo.get(cmd.prescription_id)
            prescription.dispense_partial(
                dispensed_line_names=cmd.dispensed_line_names,
                dispensed_by=cmd.dispensed_by,
            )
            await repo.save(prescription)
            uow.register(prescription)
            await uow.commit()


class RejectPrescriptionHandler:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, cmd: RejectPrescriptionCommand) -> None:
        async with self._uow_factory() as uow:
            repo = SqlAlchemyPrescriptionRepository(uow.session)
            prescription = await repo.get(cmd.prescription_id)
            prescription.reject(reasons=cmd.reasons, rejected_by=cmd.rejected_by)
            await repo.save(prescription)
            uow.register(prescription)
            await uow.commit()
