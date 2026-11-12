"""
Input guard module: intercepts and refuses personal medical advice, dosing queries,
and non-biomedical queries with deterministic safe messages and zero LLM calls.
"""

import re
from typing import Optional, Tuple

PERSONAL_ADVICE_PATTERNS = [
    r"\b(i am|i have|i feel|my doctor|my patient|my symptoms|prescribed to me|for me)\b",
    r"\b(should i take|can i take|may i take|am i able to take)\b",
    r"\b(what should i do|what medicine should i take|give me advice|treat my|cure my)\b",
    r"\b(i took|i ingested|i missed a dose|emergency|overdose)\b",
]

DOSING_PATTERNS = [
    r"\b(how many mg|what dose|what dosage|how much should i take|dose should i take)\b",
    r"\b(initial dose|starting dose|how many pills|how often should i take|dosing schedule)\b",
    r"\b(adjust my dose|increase my dose|decrease my dose|prescribe)\b",
    r"\b\d+\s*(mg|milligram|mcg|microgram|ml)\b.*(should i|to take)",
]

PROMPT_INJECTION_PATTERNS = [
    r"\b(ignore (all )?previous instructions|disregard (all )?instructions|system prompt)\b",
    r"\b(you are now|dan mode|jailbreak|developer mode|override rules)\b",
    r"(\bprint the key\b|\breveal your instructions\b|\bbypass constraints\b)",
]

# Clearly non-biomedical domain patterns refused as out-of-scope (Section B4).
# Unknown medicine/brand names (e.g. "dolo 650", "flexon", "paracetamol") do NOT
# match these patterns and proceed to retrieval / unrecognized_entity gate.
OUT_OF_SCOPE_PATTERNS = [
    (
        r"\b(capital of|prime minister|president of|tourist attractions?|"
        r"travel guide|geography|continent|population of)\b"
    ),
    (
        r"\b(python|javascript|typescript|html|css|sql|compiler|git commit|"
        r"pip|npm|programming|coding|software)\b"
    ),
    r"\binstall\b.*\bpackage\b",
    (
        r"\b(weather|forecast|recipe|cooking|football|basketball|soccer|"
        r"cricket|movie|movies|music|stock market)\b"
    ),
]

ADVICE_REFUSAL_MESSAGE = (
    "I cannot provide personal medical advice or clinical dosing recommendations. "
    "Please consult a qualified healthcare provider, clinical geneticist, or pharmacist "
    "for personalized treatment guidance."
)

DOSING_REFUSAL_MESSAGE = (
    "I cannot provide specific dosing instructions or dosage adjustments. "
    "Dosing must be determined by a licensed physician or pharmacist based on complete "
    "patient clinical history and therapeutic monitoring."
)

SYMPTOM_PATTERNS = [
    (
        r"\b(chest pain|shortness of breath|difficulty breathing|severe pain|"
        r"bleeding|hemorrhage|stroke|heart attack|allergic reaction|anaphylaxis|"
        r"fainting|unconscious|seizure)\b"
    ),
    r"\b(symptom|symptoms|dizziness|vomiting|fever|swelling|palpitations)\b",
]

EMERGENCY_ADVISORY = (
    " If this is happening now, contact local emergency services or "
    "seek urgent medical care immediately."
)

OUT_OF_SCOPE_REFUSAL_MESSAGE = (
    "This system is restricted strictly to biomedical and pharmacogenomic questions "
    "regarding drug-gene interactions, variant annotations, and CPIC guidelines. "
    "Your query does not appear to involve biomedical or pharmacogenomic topics."
)

INJECTION_REFUSAL_MESSAGE = (
    "Input violation detected: instructions attempting to override system behavior or access "
    "system internals are strictly prohibited."
)


class InputGuard:
    """Evaluates user questions and rejects unsafe or out-of-scope requests."""

    @classmethod
    def evaluate(cls, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate question safety and scope.
        Returns:
            (is_refused, refusal_category, refusal_message)
        """
        cleaned = question.strip()
        cleaned_lower = cleaned.lower()

        if not cleaned:
            return True, "empty_query", "Query cannot be empty."

        # 1. Prompt Injection Check
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, cleaned_lower):
                return True, "prompt_injection", INJECTION_REFUSAL_MESSAGE

        # Check for symptom description
        has_symptoms = any(re.search(pat, cleaned_lower) for pat in SYMPTOM_PATTERNS)

        # 2. Dosing Questions Check
        for pat in DOSING_PATTERNS:
            if re.search(pat, cleaned_lower):
                msg = DOSING_REFUSAL_MESSAGE + (EMERGENCY_ADVISORY if has_symptoms else "")
                return True, "dosing", msg

        # 3. Personal Medical Advice Check
        for pat in PERSONAL_ADVICE_PATTERNS:
            if re.search(pat, cleaned_lower):
                msg = ADVICE_REFUSAL_MESSAGE + (EMERGENCY_ADVISORY if has_symptoms else "")
                return True, "personal_advice", msg

        # 4. Out-of-scope Clearly Non-Biomedical Check
        for pat in OUT_OF_SCOPE_PATTERNS:
            if re.search(pat, cleaned_lower):
                return True, "out_of_scope", OUT_OF_SCOPE_REFUSAL_MESSAGE

        return False, None, None
