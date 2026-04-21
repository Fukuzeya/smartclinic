"""SmartClinic — Scheduling bounded context.

Owns Appointment lifecycle from booking through check-in or cancellation.
The ``scheduling.appointment.checked_in.v1`` event is the trigger that
causes Clinical to open an Encounter.
"""

__version__ = "0.1.0"
