"""The Patient aggregate.

Responsibilities (and *only* these):

* Hold the identity-of-record demographic state for one patient.
* Enforce the invariants that protect that state.
* Record a ``DomainEvent`` for every mutation, so the outbox can
  publish it atomically with the database commit (ADR 0009).

**Patient is not event-sourced** — see ADR 0003, which scopes ES to the
Clinical context only. Here the aggregate's row in ``patients`` is the
source of truth; events exist purely for integration with downstream
contexts. This keeps registration fast and queryable (everyone needs
``WHERE name ILIKE ...``) while still giving us a full, cross-service
audit trail on the bus.
"""

from __future__ import annotations

from datetime import datetime

from shared_kernel.domain.aggregate_root import AggregateRoot
from shared_kernel.domain.exceptions import InvariantViolation, PreconditionFailed
from shared_kernel.types.clock import Clock
from shared_kernel.types.contact import Email, PhoneNumber
from shared_kernel.types.identifiers import PatientId
from shared_kernel.types.national_id import ZimbabweanNationalId
from shared_kernel.types.person_name import PersonName

from patient_identity.domain.events import (
    ConsentGranted,
    ConsentGrantedPayload,
    ConsentRevoked,
    ConsentRevokedPayload,
    DemographicsUpdated,
    DemographicsUpdatedPayload,
    PatientRegistered,
    PatientRegisteredPayload,
)
from patient_identity.domain.value_objects import (
    Address,
    Consent,
    ConsentPurpose,
    DateOfBirth,
    NextOfKin,
    Sex,
)


class Patient(AggregateRoot[PatientId]):
    """The registered-patient aggregate root.

    State is held as plain attributes (not Pydantic fields) so the
    aggregate is freely mutable from within its own methods while
    staying opaque from the outside — no direct attribute-writes are
    supported; every change funnels through a named behaviour method.
    """

    __slots__ = (
        "_name",
        "_national_id",
        "_date_of_birth",
        "_sex",
        "_email",
        "_phone",
        "_address",
        "_next_of_kin",
        "_consents",
        "_registered_at",
        "_registered_by",
    )

    def __init__(
        self,
        *,
        id: PatientId,
        version: int,
        name: PersonName,
        national_id: ZimbabweanNationalId,
        date_of_birth: DateOfBirth,
        sex: Sex,
        email: Email | None,
        phone: PhoneNumber | None,
        address: Address | None,
        next_of_kin: NextOfKin | None,
        consents: tuple[Consent, ...],
        registered_at: datetime,
        registered_by: str,
    ) -> None:
        super().__init__(id=id, version=version)
        self._name = name
        self._national_id = national_id
        self._date_of_birth = date_of_birth
        self._sex = sex
        self._email = email
        self._phone = phone
        self._address = address
        self._next_of_kin = next_of_kin
        self._consents = consents
        self._registered_at = registered_at
        self._registered_by = registered_by

    # -- Factory ----------------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        patient_id: PatientId | None = None,
        name: PersonName,
        national_id: ZimbabweanNationalId,
        date_of_birth: DateOfBirth,
        sex: Sex,
        email: Email | None = None,
        phone: PhoneNumber | None = None,
        address: Address | None = None,
        next_of_kin: NextOfKin | None = None,
        registered_by: str,
        clock: Clock,
    ) -> Patient:
        """Register a new patient.

        The invariant that distinguishes a *register* call from an
        *update* is that we record the registration event and assign
        the initial version (1). Callers that need to re-hydrate a
        stored aggregate use :meth:`rehydrate` instead.
        """
        if not registered_by.strip():
            raise InvariantViolation("registered_by must be a non-empty actor id")
        cls._require_at_least_one_contact(email, phone)

        new_id = patient_id or PatientId.new()
        now = clock.now()
        patient = cls(
            id=new_id,
            version=0,
            name=name,
            national_id=national_id,
            date_of_birth=date_of_birth,
            sex=sex,
            email=email,
            phone=phone,
            address=address,
            next_of_kin=next_of_kin,
            consents=(),
            registered_at=now,
            registered_by=registered_by,
        )
        patient._record(
            PatientRegistered.build(
                aggregate_id=str(new_id.value),
                aggregate_version=patient._next_version(),
                data=PatientRegisteredPayload(
                    patient_id=str(new_id.value),
                    name=name,
                    date_of_birth=datetime.combine(
                        date_of_birth.value, datetime.min.time()
                    ).replace(tzinfo=now.tzinfo),
                    sex=sex,
                    email=email,
                    phone=phone,
                    registered_by=registered_by,
                ),
            )
        )
        return patient

    @classmethod
    def rehydrate(
        cls,
        *,
        id: PatientId,
        version: int,
        name: PersonName,
        national_id: ZimbabweanNationalId,
        date_of_birth: DateOfBirth,
        sex: Sex,
        email: Email | None,
        phone: PhoneNumber | None,
        address: Address | None,
        next_of_kin: NextOfKin | None,
        consents: tuple[Consent, ...],
        registered_at: datetime,
        registered_by: str,
    ) -> Patient:
        """Rebuild a Patient from persistent storage without emitting events."""
        if version < 1:
            raise InvariantViolation("rehydrated aggregate must have version >= 1")
        return cls(
            id=id,
            version=version,
            name=name,
            national_id=national_id,
            date_of_birth=date_of_birth,
            sex=sex,
            email=email,
            phone=phone,
            address=address,
            next_of_kin=next_of_kin,
            consents=consents,
            registered_at=registered_at,
            registered_by=registered_by,
        )

    # -- Behaviours -------------------------------------------------------

    def update_demographics(
        self,
        *,
        name: PersonName | None = None,
        email: Email | None = None,
        phone: PhoneNumber | None = None,
        address: Address | None = None,
        next_of_kin: NextOfKin | None = None,
        clear_email: bool = False,
        clear_phone: bool = False,
        updated_by: str,
    ) -> None:
        """Mutate demographic fields.

        Parameters left as ``None`` are **not changed** — this is an
        explicit PATCH, not a PUT. To *clear* an optional contact,
        pass ``clear_email=True`` / ``clear_phone=True`` alongside.
        """
        if not updated_by.strip():
            raise InvariantViolation("updated_by must be a non-empty actor id")

        new_name = name or self._name
        new_email = None if clear_email else (email if email is not None else self._email)
        new_phone = None if clear_phone else (phone if phone is not None else self._phone)
        new_address = address if address is not None else self._address
        new_nok = next_of_kin if next_of_kin is not None else self._next_of_kin

        # Invariant: we must preserve at least one contact channel.
        self._require_at_least_one_contact(new_email, new_phone)

        # No-op guard: skip the event if nothing actually changed.
        if (
            new_name == self._name
            and new_email == self._email
            and new_phone == self._phone
            and new_address == self._address
            and new_nok == self._next_of_kin
        ):
            return

        self._name = new_name
        self._email = new_email
        self._phone = new_phone
        self._address = new_address
        self._next_of_kin = new_nok
        self._record(
            DemographicsUpdated.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=DemographicsUpdatedPayload(
                    patient_id=str(self.id.value),
                    name=self._name,
                    email=self._email,
                    phone=self._phone,
                    address=self._address,
                    updated_by=updated_by,
                ),
            )
        )

    def grant_consent(
        self,
        *,
        purpose: ConsentPurpose,
        granted_by: str,
        clock: Clock,
    ) -> None:
        """Grant (or re-grant, after revocation) consent for ``purpose``.

        Granting an already-active consent is a no-op — the domain does
        not emit an event for a state change that did not happen.
        """
        if not granted_by.strip():
            raise InvariantViolation("granted_by must be a non-empty actor id")

        existing = self._find_consent(purpose)
        if existing is not None and existing.is_active:
            return  # idempotent: already granted

        now = clock.now()
        new_consent = Consent(
            purpose=purpose,
            granted_at=now,
            granted_by=granted_by,
        )
        # Replace any prior (revoked) consent for this purpose; otherwise append.
        self._consents = tuple(
            c for c in self._consents if c.purpose != purpose
        ) + (new_consent,)
        self._record(
            ConsentGranted.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=ConsentGrantedPayload(
                    patient_id=str(self.id.value),
                    purpose=purpose,
                    granted_at=now,
                    granted_by=granted_by,
                ),
            )
        )

    def revoke_consent(
        self,
        *,
        purpose: ConsentPurpose,
        revoked_by: str,
        clock: Clock,
    ) -> None:
        """Revoke an active consent for ``purpose``.

        Revoking a non-existent or already-revoked consent raises
        :class:`PreconditionFailed` — the Right-to-be-Forgotten path is
        visible and auditable, never silent.
        """
        if not revoked_by.strip():
            raise InvariantViolation("revoked_by must be a non-empty actor id")

        existing = self._find_consent(purpose)
        if existing is None or not existing.is_active:
            raise PreconditionFailed(
                f"no active consent to revoke for purpose '{purpose.value}'"
            )

        now = clock.now()
        revoked = existing.revoke(at=now, by=revoked_by)
        self._consents = tuple(
            c if c.purpose != purpose else revoked for c in self._consents
        )
        self._record(
            ConsentRevoked.build(
                aggregate_id=str(self.id.value),
                aggregate_version=self._next_version(),
                data=ConsentRevokedPayload(
                    patient_id=str(self.id.value),
                    purpose=purpose,
                    revoked_at=now,
                    revoked_by=revoked_by,
                ),
            )
        )

    # -- Read-only accessors ----------------------------------------------

    @property
    def name(self) -> PersonName:
        return self._name

    @property
    def national_id(self) -> ZimbabweanNationalId:
        return self._national_id

    @property
    def date_of_birth(self) -> DateOfBirth:
        return self._date_of_birth

    @property
    def sex(self) -> Sex:
        return self._sex

    @property
    def email(self) -> Email | None:
        return self._email

    @property
    def phone(self) -> PhoneNumber | None:
        return self._phone

    @property
    def address(self) -> Address | None:
        return self._address

    @property
    def next_of_kin(self) -> NextOfKin | None:
        return self._next_of_kin

    @property
    def consents(self) -> tuple[Consent, ...]:
        return self._consents

    @property
    def registered_at(self) -> datetime:
        return self._registered_at

    @property
    def registered_by(self) -> str:
        return self._registered_by

    def has_active_consent(self, purpose: ConsentPurpose) -> bool:
        c = self._find_consent(purpose)
        return c is not None and c.is_active

    # -- Internals --------------------------------------------------------

    def _next_version(self) -> int:
        """The ``aggregate_version`` to stamp on the next pending event.

        Accounts for events already queued in this transaction — the UoW
        bumps ``_version`` once per drained event on commit, so we
        pre-compute the value each event will have post-commit.
        """
        return self._version + len(self._pending_events) + 1

    def _find_consent(self, purpose: ConsentPurpose) -> Consent | None:
        for c in self._consents:
            if c.purpose == purpose:
                return c
        return None

    @staticmethod
    def _require_at_least_one_contact(
        email: Email | None, phone: PhoneNumber | None
    ) -> None:
        if email is None and phone is None:
            raise InvariantViolation(
                "patient must have at least one contact channel (email or phone)"
            )
