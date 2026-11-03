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

# Keywords indicating a biomedical, pharmacological, or genomic context
BIOMEDICAL_KEYWORDS = [
    "gene",
    "variant",
    "allele",
    "cyp",
    "hla",
    "vkorc1",
    "dpyd",
    "tpmt",
    "ugt1a1",
    "slco1b1",
    "clopidogrel",
    "warfarin",
    "fluorouracil",
    "irinotecan",
    "abacavir",
    "codeine",
    "tamoxifen",
    "simvastatin",
    "phenprocoumon",
    "acenocoumarol",
    "drug",
    "pharmacogenomic",
    "metabolism",
    "clearance",
    "efficacy",
    "toxicity",
    "interaction",
    "phenotype",
    "genotype",
    "rs",
    "guideline",
    "cpic",
    "fda",
    "pharmacokinetics",
    "pharmacodynamics",
    "inhibitor",
    "inducer",
    "substrate",
    "mutation",
    "polymorphism",
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

        # 4. Out-of-scope Non-Biomedical Check
        # Check if question contains biomedical keywords, identifier patterns, or entity symbols
        has_bio_keyword = any(kw in cleaned_lower for kw in BIOMEDICAL_KEYWORDS)
        has_identifier = bool(re.search(r"\b(rs\d+|cyp\w+|\*|\d+:\d+)\b", cleaned_lower))
        is_short_symbol = bool(re.match(r"^[A-Za-z0-9_*:-]{2,12}$", cleaned))

        # If query has no biomedical context and is not a potential entity symbol
        if not has_bio_keyword and not has_identifier and not is_short_symbol:
            return True, "out_of_scope", OUT_OF_SCOPE_REFUSAL_MESSAGE

        return False, None, None
