"""AI Clinical Copilot — provider port (abstract interface + mock implementation).

Architecture: the copilot lives behind a Port (hexagonal architecture).
The domain and application layers depend only on ``ClinicalCopilotPort``; the
concrete adapter (Anthropic or Mock) is injected at startup from config.

This keeps the domain free of HTTP / LLM SDK imports and allows the provider
to be swapped by changing one environment variable (ADR 0013).

Two capabilities are exposed:
* ``draft_soap_note``  — generate a structured SOAP skeleton from vitals +
  presenting complaint so the doctor edits rather than writes from scratch.
* ``explain_drug_safety`` — convert machine-readable Specification failure
  reasons into a clinician-readable safety narrative.

All suggestions are non-authoritative: they are logged separately from
clinical facts and must be explicitly accepted or discarded by a licensed
clinician.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


# ---------------------------------------------------------------------------
# Value objects returned by the port

@dataclass(frozen=True)
class AISuggestion:
    """An AI-generated clinical suggestion.

    Carries the generated text plus provenance metadata so the audit table
    can record exactly which model produced it and when.
    """

    text: str
    model_id: str
    generated_at: datetime
    disclaimer: str = (
        "AI-generated suggestion — non-authoritative.  "
        "Must be reviewed and explicitly accepted by a licensed clinician."
    )


# ---------------------------------------------------------------------------
# Port (abstract interface)

class ClinicalCopilotPort(ABC):
    """Abstract provider port for the AI clinical copilot.

    Any concrete adapter (Anthropic, OpenAI, local Ollama, mock) must
    implement both methods.  The domain layer never imports a concrete class.
    """

    @abstractmethod
    async def draft_soap_note(
        self,
        *,
        presenting_complaint: str,
        vitals: dict,
        existing_diagnoses: list[str] | None = None,
    ) -> AISuggestion:
        """Generate a draft SOAP note skeleton.

        Args:
            presenting_complaint: Patient's chief complaint (subjective source).
            vitals: Dict of vital-sign measurements already recorded.
            existing_diagnoses: ICD-10 descriptions if diagnoses are on file.
        Returns:
            AISuggestion with a structured SOAP draft the doctor can edit.
        """

    @abstractmethod
    async def explain_drug_safety(
        self,
        *,
        drug_names: list[str],
        spec_failure_reasons: list[str],
    ) -> AISuggestion:
        """Convert spec failure reasons into a clinician-readable narrative.

        Args:
            drug_names: Drugs on the prescription.
            spec_failure_reasons: Machine strings from Specification.reasons_for_failure().
        Returns:
            AISuggestion with a narrative explanation safe for clinical display.
        """


# ---------------------------------------------------------------------------
# Mock adapter (always available — used when ANTHROPIC_API_KEY is absent)

class MockClinicalCopilot(ClinicalCopilotPort):
    """Deterministic stub used in development, tests, and demo environments.

    Returns plausible but clearly-labelled placeholder text so the UI can be
    demonstrated without a live AI key.
    """

    MODEL_ID = "mock-copilot-v1"

    async def draft_soap_note(
        self,
        *,
        presenting_complaint: str,
        vitals: dict,
        existing_diagnoses: list[str] | None = None,
    ) -> AISuggestion:
        temp = vitals.get("temperature_celsius")
        pulse = vitals.get("pulse_bpm")
        spo2 = vitals.get("oxygen_saturation_pct")
        bp_s = vitals.get("systolic_bp_mmhg")
        bp_d = vitals.get("diastolic_bp_mmhg")

        vitals_summary = ", ".join(filter(None, [
            f"T {temp}°C" if temp else None,
            f"HR {pulse} bpm" if pulse else None,
            f"BP {bp_s}/{bp_d} mmHg" if bp_s else None,
            f"SpO₂ {spo2}%" if spo2 else None,
        ])) or "not yet recorded"

        dx_line = ""
        if existing_diagnoses:
            dx_line = f"\nA: Consistent with: {'; '.join(existing_diagnoses)}."

        text = (
            f"S: Patient reports: {presenting_complaint}\n"
            f"O: Vitals — {vitals_summary}. "
            "General examination unremarkable. No acute distress.\n"
            f"A: Findings consistent with presenting complaint.{dx_line} "
            "Differential includes [clinician to expand].\n"
            "P: [Clinician to complete] — consider appropriate investigations, "
            "treatment, and follow-up interval."
        )
        return AISuggestion(text=text, model_id=self.MODEL_ID,
                            generated_at=datetime.now(UTC))

    async def explain_drug_safety(
        self,
        *,
        drug_names: list[str],
        spec_failure_reasons: list[str],
    ) -> AISuggestion:
        drugs = ", ".join(drug_names) if drug_names else "the prescribed drugs"
        reasons_block = "\n".join(f"• {r}" for r in spec_failure_reasons) if spec_failure_reasons else "• No specific reasons provided"
        text = (
            f"Dispensing of {drugs} was blocked by the clinical safety specification chain:\n\n"
            f"{reasons_block}\n\n"
            "Please review the prescription against current patient allergies, "
            "contraindications, and current stock levels before re-issuing.  "
            "If a substitution is required, amend the prescription and the saga "
            "will automatically resume the patient visit workflow."
        )
        return AISuggestion(text=text, model_id=self.MODEL_ID,
                            generated_at=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Anthropic adapter (loaded only when ANTHROPIC_API_KEY is set)

class AnthropicClinicalCopilot(ClinicalCopilotPort):
    """Production adapter backed by Anthropic Claude.

    Loaded at runtime when ``ANTHROPIC_API_KEY`` is present.  The domain
    never imports this class directly — it receives a ``ClinicalCopilotPort``
    reference via dependency injection (ADR 0013).

    Requires: ``anthropic`` package (optional dependency).
    """

    MODEL_ID = os.getenv("ANTHROPIC_COPILOT_MODEL", "claude-haiku-4-5-20251001")
    MAX_TOKENS = 512

    def __init__(self) -> None:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for AnthropicClinicalCopilot. "
                "Install it with: uv add anthropic"
            ) from exc
        self._client = anthropic.AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )

    async def draft_soap_note(
        self,
        *,
        presenting_complaint: str,
        vitals: dict,
        existing_diagnoses: list[str] | None = None,
    ) -> AISuggestion:
        import anthropic  # type: ignore[import]

        vitals_lines = "\n".join(
            f"  {k.replace('_', ' ')}: {v}"
            for k, v in vitals.items()
            if v is not None
        )
        dx_block = ""
        if existing_diagnoses:
            dx_block = "\nRecorded diagnoses:\n" + "\n".join(
                f"  - {d}" for d in existing_diagnoses
            )

        prompt = (
            "You are a clinical documentation assistant for a Zimbabwean private clinic.\n"
            "Generate a concise, professional SOAP note skeleton the doctor will edit — "
            "do NOT invent clinical findings not present in the provided data.\n\n"
            f"Presenting complaint: {presenting_complaint}\n"
            f"Vitals:\n{vitals_lines or '  (none recorded)'}"
            f"{dx_block}\n\n"
            "Output exactly four labelled paragraphs: S:, O:, A:, P: — no other text."
        )

        response = await self._client.messages.create(
            model=self.MODEL_ID,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return AISuggestion(text=text, model_id=self.MODEL_ID,
                            generated_at=datetime.now(UTC))

    async def explain_drug_safety(
        self,
        *,
        drug_names: list[str],
        spec_failure_reasons: list[str],
    ) -> AISuggestion:
        drugs = ", ".join(drug_names) or "prescribed drugs"
        reasons = "\n".join(f"- {r}" for r in spec_failure_reasons)

        prompt = (
            "You are a clinical safety assistant.  The following drug dispensing "
            "was blocked by an automated specification check.  Explain the safety "
            "concern in plain clinical language a non-pharmacist doctor can act on.\n\n"
            f"Drugs: {drugs}\n"
            f"Specification violations:\n{reasons}\n\n"
            "Keep the explanation under 100 words.  Be precise, not alarmist.  "
            "Suggest one concrete clinical action.  No disclaimers about not being a doctor."
        )

        response = await self._client.messages.create(
            model=self.MODEL_ID,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return AISuggestion(text=text, model_id=self.MODEL_ID,
                            generated_at=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Factory — resolves the correct adapter from environment

def build_copilot() -> ClinicalCopilotPort:
    """Return the best available copilot adapter.

    Priority:
    1. ``ANTHROPIC_API_KEY`` present → AnthropicClinicalCopilot
    2. Fallback → MockClinicalCopilot

    The clinical service calls this once at startup and stores the instance on
    ``app.state.copilot``.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return AnthropicClinicalCopilot()
        except Exception:
            pass  # fall through to mock if import fails
    return MockClinicalCopilot()
