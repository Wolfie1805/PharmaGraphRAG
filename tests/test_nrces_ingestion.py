"""Offline unit tests for Phase 1 NRCeS Flat Files Package ingestion and profiling."""

from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import pytest

from app.ingestion.nrces import (
    find_brands_by_substring,
    ingest_nrces_flat_files,
    match_nrces_substances_to_clinpgx,
    parse_nrces_tsv_bytes,
    profile_nrces_zip,
    read_license_txt_from_zip,
)
from app.ingestion.verify import verify_manifest


def _build_synthetic_nrces_zip(zip_path: Path) -> Path:
    """Create a realistic synthetic NRCeS Flat Files ZIP archive for offline testing."""
    prefix = "CommonDrugCodesForIndia_FlatFilePackage/"
    files = {
        "License.txt": "Copyright (c) 2019, C-DAC Pune.\nSample verbatim license.\n",
        "SubstanceMaster.txt": (
            "Identifier\tSubstance Name\tCAS Number\tUNII\tSubstance Description\t"
            "Molecular Weight\tToxicity\tSMILE\tInChI\tIUPAC Name\t"
            "Molecular Formula\tlast_updated_on\n"
            "387517004\tAcetaminophen\t103-90-2\t\t\t\t\t\t\t\t\t20260831\t\n"
            "387207008\tIbuprofen\t15687-27-1\t\t\t\t\t\t\t\t\t20260831\t\n"
            "9990001\tAbacavir sulfate\t\t\t\t\t\t\t\t\t\t20260831\t\n"
            "9990002\tAmbigChem\t\t\t\t\t\t\t\t\t\t20260831\t\n"
        ),
        "GenericMaster.txt": (
            "Identifier\tGeneric Name\tSubstance Identifier\tRoute of Administration\tDose Form\t"
            "Therapeutic Role\tIndication\tContra Indication\tInteraction with Drugs\t"
            "Classification of Drugs\tSource/ Regulatory\tlast_updated_on\n"
            "370151002\tAcetaminophen 650 mg oral tablet\t387517004\t26643006\t421026006\t"
            "\t\t\t\t\t\t20260831\t\n"
            "7471000189101\tAcetaminophen 325 mg and ibuprofen 400 mg oral tablet\t"
            "387517004+387207008\t26643006\t421026006\t\t\t\t\t\t\t20260831\t\n"
            "8880001\tOrphan Sub Generic\t7777777\t26643006\t421026006\t\t\t\t\t\t\t20260831\t\n"
        ),
        "BrandMaster.txt": (
            "Identifier\tBrand Name\tProduct Identifier\tSupplier Identifier\tGeneric Identifier\t"
            "License Number\tLicense Status\tExcipient\tlast_updated_on\n"
            "1148541000189109\tDolo 650 mg oral tablet\t1001\t2001\t370151002\t"
            "\tUNKNOWN\t\t20260831\t\n"
            "440721000189105\tFlexon 400 mg + 325 mg oral tablet\t1002\t2001\t7471000189101\t"
            "\tUNKNOWN\t\t20260831\t\n"
            "3000001\tOrphanBrand 10 mg\t1001\t2001\t99999999\t\tUNKNOWN\t\t20260831\t\n"
            "3000002\tNoGenericVaccine\t1001\t2001\t\t\tUNKNOWN\t\n"
        ),
        "ProductMaster.txt": "Identifier\tProduct Name\n1001\tDolo\t\n1002\tFlexon\t\n",
        "SupplierMaster.txt": "Identifier\tSupplier Name\tCountry\n2001\tMicro Labs\tIndia\t\n",
        "DrugFormMaster.txt": "Id\tDose Form\n421026006\tOral tablet\n",
        "RouteOfAdministrationMaster.txt": (
            "Identifier\tRouteOfAdministration\n26643006\tOral route\n"
        ),
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fname, content in files.items():
            z.writestr(prefix + fname, content.encode("utf-8"))
    return zip_path


def test_parse_nrces_tsv_handles_trailing_and_short_rows():
    raw = ("A\tB\tC\n1\t2\t3\n4\t5\t6\t\n7\t8\t9\t\t\t\n10\t11\n").encode("utf-8")
    headers, rows, stats = parse_nrces_tsv_bytes(raw)
    assert headers == ["A", "B", "C"]
    assert len(rows) == 4
    assert stats == {
        "exact": 1,
        "trailing_empty_tab": 1,
        "extra_empty_tabs": 1,
        "padded_short": 1,
    }
    assert rows[3] == {"A": "10", "B": "11", "C": ""}


def test_ingest_nrces_write_once_manifest_and_immutability(tmp_path: Path):
    manual_dir = tmp_path / "manual_downloads" / "nrces"
    manual_dir.mkdir(parents=True)
    src_zip = _build_synthetic_nrces_zip(manual_dir / "CommonDrugCodesForIndia_FlatFilePackage.zip")
    orig_bytes = src_zip.read_bytes()

    raw_base = tmp_path / "data" / "raw" / "nrces"
    manifests_dir = tmp_path / "data" / "manifests"

    dest_zip, manifest_path, manifest = ingest_nrces_flat_files(
        source_zip_path=src_zip,
        raw_base_dir=raw_base,
        manifests_dir=manifests_dir,
        workspace_root=tmp_path,
        run_id="20261118_test1234",
    )

    # Original untouched and never unzipped in raw
    assert src_zip.exists()
    assert src_zip.read_bytes() == orig_bytes
    assert dest_zip.is_file()
    assert list(dest_zip.parent.iterdir()) == [dest_zip]

    assert manifest.acquisition_method == "manual_download_by_user"
    assert len(manifest.archive_members) == 8
    assert "Sample verbatim license." in read_license_txt_from_zip(dest_zip)

    # Manifest verification passes offline
    ver = verify_manifest(manifest_path, workspace_root=tmp_path)
    assert ver.is_valid is True
    assert ver.total_files_checked == 1

    # Write-once immutability rejects duplicate run_id overwrite
    with pytest.raises(FileExistsError):
        ingest_nrces_flat_files(
            source_zip_path=src_zip,
            raw_base_dir=raw_base,
            manifests_dir=manifests_dir,
            workspace_root=tmp_path,
            run_id="20261118_test1234",
        )


def test_profile_and_dolo_flexon_joins_in_memory(tmp_path: Path):
    zpath = _build_synthetic_nrces_zip(tmp_path / "nrces.zip")
    profile = profile_nrces_zip(zpath)

    assert profile["tables"]["Substance"]["row_count"] == 4
    assert profile["tables"]["Generic"]["row_count"] == 3
    assert profile["tables"]["Brand"]["row_count"] == 4

    b2g = profile["joins"]["brand_to_generic"]
    assert b2g["matched"] == 2
    assert b2g["empty_fk"] == 1
    assert b2g["orphan_fk"] == 1

    g2s = profile["joins"]["generic_to_substance"]
    assert g2s["single_substance_generics"] == 2
    assert g2s["combination_generics_gt1_substance"] == 1
    assert g2s["matched_substance_tokens"] == 3
    assert g2s["orphan_substance_tokens"] == 1

    brands = find_brands_by_substring(zpath, ("dolo", "flexon"))
    assert len(brands["dolo"]) == 1
    assert brands["dolo"][0]["brand_name"] == "Dolo 650 mg oral tablet"
    assert brands["dolo"][0]["substance_names"] == ["Acetaminophen"]

    assert len(brands["flexon"]) == 1
    assert brands["flexon"][0]["substance_names"] == ["Acetaminophen", "Ibuprofen"]


def test_exact_normalized_match_no_fuzzy_matching(tmp_path: Path):
    zpath = _build_synthetic_nrces_zip(tmp_path / "nrces.zip")
    ent_pq = tmp_path / "entities.parquet"
    syn_pq = tmp_path / "synonyms.parquet"

    con = duckdb.connect(":memory:")
    con.execute(
        f"""
        COPY (
            SELECT * FROM (VALUES
                ('pg:chem:448015', 'chemical', 'acetaminophen', 'acetaminophen', false),
                ('pg:chem:449956', 'chemical', 'ibuprofen', 'ibuprofen', false),
                ('pg:chem:1001', 'chemical', 'abacavir', 'abacavir', false),
                ('pg:chem:2001', 'chemical', 'ambig_a', 'ambig_a', false),
                ('pg:chem:2002', 'chemical', 'ambig_b', 'ambig_b', false)
            ) AS t(canonical_id, entity_type, display_name, normalized_name, is_artifact)
        ) TO '{ent_pq.as_posix()}' (FORMAT PARQUET)
        """
    )
    con.execute(
        f"""
        COPY (
            SELECT * FROM (VALUES
                ('pg:chem:2001', 'AmbigChem', 'ambigchem', false),
                ('pg:chem:2002', 'AmbigChem', 'ambigchem', false)
            ) AS t(canonical_id, synonym_text, normalized_synonym, is_artifact)
        ) TO '{syn_pq.as_posix()}' (FORMAT PARQUET)
        """
    )

    rep = match_nrces_substances_to_clinpgx(zpath, ent_pq, syn_pq)
    # Acetaminophen & Ibuprofen match exact; Abacavir sulfate must NOT fuzzy-match abacavir;
    # AmbigChem maps to 2 ClinPGx IDs -> ambiguous.
    assert rep["matched_count"] == 2
    assert rep["unmatched_count"] == 1
    assert rep["ambiguous_count"] == 1
    assert rep["sample_unmatched_30"] == ["Abacavir sulfate"]
    assert (
        rep["paracetamol_acetaminophen_report"]["acetaminophen"]["in_nrces_substance_master"]
        is True
    )
    assert (
        rep["paracetamol_acetaminophen_report"]["acetaminophen"]["in_clinpgx_chemical_display_name"]
        is True
    )
    assert (
        rep["paracetamol_acetaminophen_report"]["paracetamol"]["in_nrces_substance_master"] is False
    )


def test_real_ingested_nrces_manifest_integrity_if_present():
    """Verify the local raw NRCeS manifest passes hash checks and contains no unzipped files."""
    manifest_path = Path("data/manifests/manifest_nrces_20261118_2cab0068.json")
    if not manifest_path.exists():
        pytest.skip("Local private NRCeS manifest not present")
    ver = verify_manifest(manifest_path)
    assert ver.is_valid is True
    assert ver.missing_files == []
    assert ver.mismatched_hashes == []
    assert ver.unexpected_files == []
    raw_dir = Path("data/raw/nrces/20261118_2cab0068")
    assert [p.name for p in raw_dir.iterdir()] == ["CommonDrugCodesForIndia_FlatFilePackage.zip"]
