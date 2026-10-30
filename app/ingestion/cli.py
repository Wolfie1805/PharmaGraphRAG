"""Command Line Interface for PharmaGraph Raw Data Acquisition and Verification.

CLI commands:
- acquire-clinpgx: download ClinPGx confirmed archives and catalog snapshot
- acquire-pubmed [--pilot] [--resume RUN_ID]: download PubMed XML batches
- verify <manifest_path>: verify file hashes and integrity against manifest
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from app.config.model import NCBISettings, load_acquisition_config
from app.ingestion.clinpgx import acquire_clinpgx
from app.ingestion.pubmed import acquire_pubmed
from app.ingestion.verify import verify_manifest


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_clinpgx(args):
    config = load_acquisition_config(args.config)
    print("=" * 60)
    print("STARTING CLINPGX RAW ACQUISITION")
    print(f"Target files: {len(config.clinpgx.selected_files)} archives")
    print("=" * 60)
    manifest, manifest_path = acquire_clinpgx(
        config=config.clinpgx,
        storage=config.storage,
        workspace_root=Path("."),
    )
    print("\n" + "=" * 60)
    print("CLINPGX ACQUISITION COMPLETED")
    print(f"Run ID: {manifest.run_id}")
    print(f"Files acquired: {len(manifest.files)}")
    print(f"Manifest written to: {manifest_path}")
    print("=" * 60)


def cmd_pubmed(args):
    config = load_acquisition_config(args.config)
    ncbi_settings = NCBISettings()
    is_pilot = args.pilot
    pilot_cap = args.pilot_cap if is_pilot else None

    print("=" * 60)
    if is_pilot:
        print(f"STARTING PUBMED PILOT ACQUISITION (CAP: {pilot_cap} PMIDs)")
    else:
        print("STARTING PUBMED FULL ACQUISITION")
    print(f"Gene-Drug Pairs: {len(config.gene_drug_pairs)}")
    print(f"API Key present: {bool(ncbi_settings.ncbi_api_key)}")
    print("=" * 60)

    manifest, manifest_path = acquire_pubmed(
        config=config.pubmed,
        gene_drug_pairs=config.gene_drug_pairs,
        storage=config.storage,
        ncbi_settings=ncbi_settings,
        workspace_root=Path("."),
        is_pilot=is_pilot,
        pilot_total_cap=pilot_cap or 50,
        resume_run_id=args.resume,
    )

    print("\n" + "=" * 60)
    print(f"PUBMED {'PILOT ' if is_pilot else ''}ACQUISITION COMPLETED")
    print(f"Run ID: {manifest.run_id}")
    print(f"Unique PMIDs retrieved: {len(manifest.pmids_retrieved)}")
    print(f"Batch files written: {len(manifest.files)}")
    if manifest.reconciliation:
        print(f"Reconciliation status: {'100% MATCH' if manifest.reconciliation.reconciled else 'MISMATCH'}")
        print(f"Requested: {manifest.reconciliation.total_requested}, Received in XML: {manifest.reconciliation.total_received}")
        if manifest.reconciliation.missing_pmids:
            print(f"Missing PMIDs: {manifest.reconciliation.missing_pmids}")
    print(f"Manifest written to: {manifest_path}")
    print("=" * 60)


def cmd_verify(args):
    report = verify_manifest(args.manifest, workspace_root=Path("."))
    print("=" * 60)
    print("MANIFEST VERIFICATION REPORT")
    print(f"Manifest: {report.manifest_path}")
    print(f"Source: {report.source_name} (Run ID: {report.run_id})")
    print(f"Total files checked: {report.total_files_checked}")
    print(f"Valid files: {len(report.valid_files)}")
    print(f"Mismatched hashes: {len(report.mismatched_hashes)}")
    print(f"Missing files: {len(report.missing_files)}")
    print(f"Unexpected extra files: {len(report.unexpected_files)}")
    print("-" * 60)

    if report.mismatched_hashes:
        print("MISMATCH DETAILS:")
        for m in report.mismatched_hashes:
            print(f"  File: {m['file']}")
            print(f"    Expected SHA: {m['expected_sha']}")
            print(f"    Actual SHA:   {m['actual_sha']}")

    if report.missing_files:
        print("MISSING FILES:")
        for mf in report.missing_files:
            print(f"  - {mf}")

    if report.unexpected_files:
        print("UNEXPECTED EXTRA FILES:")
        for uf in report.unexpected_files:
            print(f"  - {uf}")

    print("=" * 60)
    if report.is_valid:
        print("RESULT: SUCCESS - ALL FILE HASHES AND INTEGRITY CONFIRMED")
        sys.exit(0)
    else:
        print("RESULT: FAILED - INTEGRITY VIOLATION DETECTED")
        sys.exit(1)


def main():
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--config", default="configs/acquisition.yaml", help="Path to acquisition config YAML")
    base_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    parser = argparse.ArgumentParser(
        description="PharmaGraph Raw Acquisition & Verification CLI",
        parents=[base_parser],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ClinPGx acquisition
    p_clinpgx = subparsers.add_parser("clinpgx", parents=[base_parser], help="Acquire ClinPGx raw archives")
    p_clinpgx.set_defaults(func=cmd_clinpgx)

    # PubMed acquisition
    p_pubmed = subparsers.add_parser("pubmed", parents=[base_parser], help="Acquire PubMed literature abstracts")
    p_pubmed.add_argument("--pilot", action="store_true", help="Run in pilot mode with strict cap (default 50)")
    p_pubmed.add_argument("--pilot-cap", type=int, default=50, help="Total PMIDs cap in pilot mode")
    p_pubmed.add_argument("--resume", type=str, default=None, help="Resume an interrupted run by run_id")
    p_pubmed.set_defaults(func=cmd_pubmed)

    # Verify command
    p_verify = subparsers.add_parser("verify", parents=[base_parser], help="Verify raw data integrity against a manifest")
    p_verify.add_argument("manifest", help="Path to manifest JSON file")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()

