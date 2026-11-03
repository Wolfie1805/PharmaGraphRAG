"""
Biomedical tokenizer preserving rsIDs, star alleles, and HLA names as single tokens.
"""

import re
from typing import List

# Regex matching biomedical identifiers before falling back to words
BIOMEDICAL_TOKEN_REGEX = re.compile(
    r"""
    HLA-[A-Za-z0-9]+(?:\*|\:)[0-9A-Za-z:]+   # HLA names e.g. HLA-B*57:01, HLA-A*31:01
    | [A-Za-z0-9]{2,}\*[0-9A-Za-z]+          # Star alleles e.g. CYP2C19*2, CYP2C9*3
    | rs\d+                                  # rsIDs e.g. rs12345
    | [A-Za-z0-9]+(?:-[A-Za-z0-9]+)+         # Hyphenated words e.g. anti-inflammatory
    | [A-Za-z0-9]+                           # Standard alphanumeric words
    """,
    re.VERBOSE | re.IGNORECASE,
)


def tokenize_biomedical(text: str) -> List[str]:
    """
    Tokenize text into lowercase terms while preserving biomedical identifiers:
    - rsIDs (e.g. rs12345)
    - Star alleles (e.g. CYP2C19*2)
    - HLA names (e.g. HLA-B*57:01)
    """
    if not text:
        return []
    tokens = BIOMEDICAL_TOKEN_REGEX.findall(text)
    return [token.lower() for token in tokens]
