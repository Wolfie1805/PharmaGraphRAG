"""PubMed / NCBI E-utilities Raw Data Acquisition Connector.

Strictly follows Phase 1 rules:
- Queries built from validated config
- Respects rate limits (2 req/s default without key, 8 req/s with key)
- Sends tool and email parameters on every request
- Redacts api_key from logs, stored URLs, and manifests
- efetch XML saved byte-for-byte as received (raw batches)
- Full PMID-to-query provenance tracking
- Full PMID reconciliation (requested vs actual XML PMIDs, reports any missing)
- Resumable: skips valid existing batch files
- Pilot mode: 50 PMIDs total, deterministically partitioned across pairs
"""

import logging
import math
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
import certifi

from app.config.manifest import (
    ManifestFileEntry,
    PubMedRunManifest,
    ReconciliationResult,
    RunStatus,
)
from app.config.model import NCBISettings, PubMedConfig, StorageConfig, GeneDrugPair
from app.ingestion.git_utils import get_git_commit_hash
from app.ingestion.hash_utils import compute_sha256, write_raw_file_atomically
from app.ingestion.rate_limiter import RateLimiter
from app.ingestion.retry import execute_with_retry

logger = logging.getLogger(__name__)


def build_query_string(
    pair: GeneDrugPair,
    require_abstract: bool = True,
    abstract_filter: str = "hasabstract[text]",
    mindate: Optional[str] = None,
    maxdate: Optional[str] = None,
) -> str:
    """Build exact PubMed query string for a gene-drug pair."""
    base_term = f"({pair.gene}[Title/Abstract] AND {pair.drug}[Title/Abstract])"
    parts = [base_term]
    if require_abstract and abstract_filter:
        parts.append(abstract_filter)
    if mindate and maxdate:
        parts.append(f'("{mindate}"[Date - Publication] : "{maxdate}"[Date - Publication])')
    elif mindate:
        parts.append(f'("{mindate}"[Date - Publication] : "3000"[Date - Publication])')
    elif maxdate:
        parts.append(f'("1800"[Date - Publication] : "{maxdate}"[Date - Publication])')
    return " AND ".join(parts)


def sanitize_url_for_logging(url: str) -> str:
    """Redact api_key parameter from URLs before logging or storing."""
    return re.sub(r"([?&]api_key=)[^&]+", r"\1***REDACTED***", str(url))


def extract_pmids_from_xml(xml_bytes: bytes) -> set[str]:
    """Extract all PMIDs present in a PubMed XML batch byte string."""
    pmids = set()
    try:
        root = ET.fromstring(xml_bytes)
        # Search for MedlineCitation/PMID or PubmedArticle/MedlineCitation/PMID
        for pmid_elem in root.iter("PMID"):
            if pmid_elem.text and pmid_elem.text.strip():
                pmids.add(pmid_elem.text.strip())
    except ET.ParseError as e:
        logger.warning("XML parsing warning during PMID extraction: %s", e)
    return pmids


def acquire_pubmed(
    config: PubMedConfig,
    gene_drug_pairs: list[GeneDrugPair],
    storage: StorageConfig,
    ncbi_settings: NCBISettings,
    workspace_root: Path = Path("."),
    is_pilot: bool = False,
    pilot_total_cap: int = 50,
    resume_run_id: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> tuple[PubMedRunManifest, Path]:
    """Execute raw acquisition of PubMed literature abstracts via E-utilities."""
    # Determine request rate limiter
    has_api_key = bool(ncbi_settings.ncbi_api_key)
    rps = config.rate_limit_rps_with_key if has_api_key else config.rate_limit_rps_default
    rate_limiter = RateLimiter(rps)
    logger.info("PubMed rate limiter initialized at %.1f requests/second (API key: %s)", rps, has_api_key)

    # Establish run directory
    run_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = resume_run_id or f"{run_date}_{uuid.uuid4().hex[:8]}"
    raw_run_dir = workspace_root / storage.raw_dir / "pubmed" / run_id
    raw_run_dir.mkdir(parents=True, exist_ok=True)

    git_commit = get_git_commit_hash(workspace_root)
    utc_timestamp = datetime.now(timezone.utc).isoformat()

    manifest = PubMedRunManifest(
        run_id=run_id,
        source_name="PubMed",
        endpoint_url=config.base_url.rstrip("/"),
        retrieval_timestamp_utc=utc_timestamp,
        source_version="not provided",
        license_name="NLM / Public Domain (citations); Publisher Copyright (abstracts)",
        license_url="https://www.ncbi.nlm.nih.gov/About/disclaimer.html",
        license_checked_date="2026-10-30",
        git_commit=git_commit,
        run_status=RunStatus.INCOMPLETE,
        is_pilot=is_pilot,
        pilot_selection_rule=(
            f"Pilot cap {pilot_total_cap} PMIDs partitioned evenly across {len(gene_drug_pairs)} "
            "pairs in esearch return order" if is_pilot else None
        ),
        batch_size=config.efetch_batch_size,
    )

    should_close_client = False
    if client is None:
        client = httpx.Client(
            verify=certifi.where(),
            headers={"User-Agent": f"{ncbi_settings.ncbi_tool}-Research/0.1.0"},
            timeout=60.0,
            follow_redirects=True,
        )
        should_close_client = True

    try:
        # Step 1: Execute esearch for each gene-drug pair
        query_to_pmids: dict[str, list[str]] = {}
        pmid_to_queries: dict[str, list[str]] = {}

        for pair in gene_drug_pairs:
            q_str = build_query_string(
                pair=pair,
                require_abstract=config.require_abstract,
                abstract_filter=config.abstract_filter,
                mindate=config.date_range.mindate,
                maxdate=config.date_range.maxdate,
            )
            manifest.queries[pair.id] = q_str
            logger.info("Running esearch for %s: %s", pair.id, q_str)

            # Standard base params
            base_params: dict[str, str] = {
                "db": config.db,
                "term": q_str,
                "retmode": "json",
                "tool": ncbi_settings.ncbi_tool,
            }
            if ncbi_settings.ncbi_email:
                base_params["email"] = ncbi_settings.ncbi_email
            if ncbi_settings.ncbi_api_key:
                base_params["api_key"] = ncbi_settings.ncbi_api_key

            # First page to get total count
            first_page_params = {**base_params, "retstart": "0", "retmax": "100"}
            esearch_url = f"{config.base_url.rstrip('/')}/esearch.fcgi"

            def call_esearch(params: dict[str, str] = first_page_params) -> httpx.Response:
                rate_limiter.wait()
                return client.get(esearch_url, params=params)

            resp = execute_with_retry(call_esearch, max_retries=config.retry.max_retries)
            data = resp.json().get("esearchresult", {})
            total_count = int(data.get("count", 0))
            manifest.esearch_counts[pair.id] = total_count

            pmids = list(data.get("idlist", []))

            # Determine how many records we want to fetch for this pair
            if is_pilot:
                target_count = math.ceil(pilot_total_cap / len(gene_drug_pairs))
            else:
                target_count = min(total_count, config.max_records_per_pair)

            # Paginate if needed
            while len(pmids) < target_count and len(pmids) < total_count:
                retstart = str(len(pmids))
                retmax = str(min(100, target_count - len(pmids)))
                page_params = {**base_params, "retstart": retstart, "retmax": retmax}

                def call_page() -> httpx.Response:
                    rate_limiter.wait()
                    return client.get(esearch_url, params=page_params)

                page_resp = execute_with_retry(call_page, max_retries=config.retry.max_retries)
                page_ids = page_resp.json().get("esearchresult", {}).get("idlist", [])
                if not page_ids:
                    break
                pmids.extend(page_ids)

            # Truncate to target_count
            pmids = pmids[:target_count]
            query_to_pmids[pair.id] = pmids
            logger.info("Pair %s: reported count=%d, selected PMIDs=%d", pair.id, total_count, len(pmids))

            for pmid in pmids:
                pmid_to_queries.setdefault(pmid, []).append(pair.id)

        # Deduplicate deterministically preserving order
        ordered_unique_pmids: list[str] = []
        seen = set()
        for pair in gene_drug_pairs:
            for pmid in query_to_pmids.get(pair.id, []):
                if pmid not in seen:
                    seen.add(pmid)
                    ordered_unique_pmids.append(pmid)

        # In pilot mode, strictly enforce exact cap (e.g. 50)
        if is_pilot and len(ordered_unique_pmids) > pilot_total_cap:
            ordered_unique_pmids = ordered_unique_pmids[:pilot_total_cap]

        manifest.pmids_retrieved = ordered_unique_pmids
        manifest.pmid_to_queries = {pmid: pmid_to_queries[pmid] for pmid in ordered_unique_pmids}

        logger.info(
            "Total deduplicated PMIDs to fetch: %d across %d pairs",
            len(ordered_unique_pmids), len(gene_drug_pairs)
        )

        # Large job reminder per NCBI guidelines (>100 requests)
        batch_size = config.efetch_batch_size
        num_batches = math.ceil(len(ordered_unique_pmids) / batch_size) if ordered_unique_pmids else 0
        if num_batches > 100:
            logger.warning(
                "NCBI USAGE POLICY REMINDER: Planned request batch count is %d (>100). "
                "NCBI requests large bulk runs take place on weekends or 9:00 PM to 5:00 AM US Eastern Time.",
                num_batches
            )

        # Step 2: Fetch raw XML batches via efetch
        efetch_url = f"{config.base_url.rstrip('/')}/efetch.fcgi"
        all_received_pmids = set()

        for b_idx in range(num_batches):
            batch_num = b_idx + 1
            batch_file_name = f"batch_{batch_num:04d}.xml"
            batch_path = raw_run_dir / batch_file_name
            batch_pmids = ordered_unique_pmids[b_idx * batch_size : (b_idx + 1) * batch_size]

            # Resume support: if batch already exists and valid, skip download
            if batch_path.exists() and batch_path.stat().st_size > 0:
                logger.info("Batch file %s already exists. Checking for resume...", batch_file_name)
                with batch_path.open("rb") as bf:
                    content = bf.read()
                xml_pmids = extract_pmids_from_xml(content)
                if xml_pmids:
                    all_received_pmids.update(xml_pmids)
                    batch_sha = compute_sha256(batch_path)
                    batch_rel = str(batch_path.relative_to(workspace_root)).replace("\\", "/")
                    manifest.files.append(
                        ManifestFileEntry(
                            relative_path=batch_rel,
                            byte_size=batch_path.stat().st_size,
                            sha256=batch_sha,
                            record_count=len(xml_pmids),
                        )
                    )
                    continue

            logger.info("Fetching efetch batch %d/%d (%d PMIDs)...", batch_num, num_batches, len(batch_pmids))

            post_data = {
                "db": config.db,
                "id": ",".join(batch_pmids),
                "retmode": "xml",
                "tool": ncbi_settings.ncbi_tool,
            }
            if ncbi_settings.ncbi_email:
                post_data["email"] = ncbi_settings.ncbi_email
            if ncbi_settings.ncbi_api_key:
                post_data["api_key"] = ncbi_settings.ncbi_api_key

            def call_efetch() -> httpx.Response:
                rate_limiter.wait()
                return client.post(efetch_url, data=post_data)

            resp = execute_with_retry(call_efetch, max_retries=config.retry.max_retries)
            # Write byte-for-byte as received, never reformatted
            write_raw_file_atomically(batch_path, resp.content)

            xml_pmids = extract_pmids_from_xml(resp.content)
            all_received_pmids.update(xml_pmids)

            batch_sha = compute_sha256(batch_path)
            batch_rel = str(batch_path.relative_to(workspace_root)).replace("\\", "/")
            manifest.files.append(
                ManifestFileEntry(
                    relative_path=batch_rel,
                    byte_size=batch_path.stat().st_size,
                    sha256=batch_sha,
                    record_count=len(xml_pmids),
                )
            )

        # Step 3: Reconciliation check (requested vs present in XML)
        requested_set = set(ordered_unique_pmids)
        missing_pmids = sorted(list(requested_set - all_received_pmids))

        manifest.reconciliation = ReconciliationResult(
            total_requested=len(requested_set),
            total_received=len(all_received_pmids & requested_set),
            missing_count=len(missing_pmids),
            missing_pmids=missing_pmids,
            reconciled=(len(missing_pmids) == 0),
        )

        if missing_pmids:
            logger.warning("Reconciliation note: %d PMIDs missing from XML response: %s", len(missing_pmids), missing_pmids)
        else:
            logger.info("Reconciliation 100%% successful: all %d requested PMIDs accounted for.", len(requested_set))

        # Mark complete
        manifest.run_status = RunStatus.COMPLETE
        manifest_path = manifest.save(workspace_root / storage.manifests_dir)
        logger.info("PubMed acquisition complete. Manifest saved to %s", manifest_path)
        return manifest, manifest_path

    finally:
        if should_close_client:
            client.close()

