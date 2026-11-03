"""
Citation verifier module: enforces that every generated claim cites at least one
source ID that genuinely exists in the retrieved evidence bundle.
Invented or hallucinated citations are stripped and ungrounded claims removed.
"""

from typing import List, Set, Tuple

from app.generation.contracts import Claim, EvidenceBundle


class CitationVerifier:
    """Verifies claim source citations against the evidence bundle."""

    @classmethod
    def verify(
        cls,
        claims: List[Claim],
        bundle: EvidenceBundle,
    ) -> Tuple[List[Claim], int]:
        """
        Verify every claim cites at least one valid source ID present in the bundle.
        Removes any claim that lacks valid evidence grounding.

        Returns:
            (verified_claims, removed_count)
        """
        valid_source_ids: Set[str] = {
            item.source_id.strip() for item in bundle.items if item.source_id
        }

        verified_claims: List[Claim] = []
        removed_count = 0

        for claim in claims:
            # Check source IDs cited by this claim
            cited = [sid.strip() for sid in claim.source_ids if sid and sid.strip()]
            valid_cited = [sid for sid in cited if sid in valid_source_ids]

            if not valid_cited:
                # No valid source ID in bundle -> claim removed
                removed_count += 1
                continue

            verified_claims.append(
                Claim(
                    text=claim.text.strip(),
                    source_ids=valid_cited,
                )
            )

        return verified_claims, removed_count
