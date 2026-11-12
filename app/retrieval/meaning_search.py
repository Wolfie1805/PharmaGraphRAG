"""
Meaning search module: dense embedding and vector search using local Qdrant on disk.
"""

import ctypes
import gc
import json
import os
import time
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.ingestion.hash_utils import compute_sha256, write_raw_file_atomically


def get_process_ram_mb() -> Tuple[float, float]:
    """
    Return (current_ram_mb, peak_ram_mb) for the current process.
    Uses Win32 K32GetProcessMemoryInfo on Windows and resource.getrusage on POSIX.
    """
    if os.name == "nt":
        try:

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            k32.K32GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
            pmc = _PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            if k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return (
                    pmc.WorkingSetSize / (1024.0 * 1024.0),
                    pmc.PeakWorkingSetSize / (1024.0 * 1024.0),
                )
        except Exception:
            pass
    else:
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            peak_mb = usage.ru_maxrss / 1024.0
            return peak_mb, peak_mb
        except Exception:
            pass
    return 0.0, 0.0


class MeaningHit(BaseModel):
    """Dense vector search hit."""

    chunk_id: str
    source_type: str
    source_id: str
    title: str
    content: str
    date: str
    date_precision: str
    entity_ids: List[str] = Field(default_factory=list)
    dense_score: float
    rank: int


class MeaningSearchIndex:
    """Local on-disk Qdrant vector index over data/processed/chunks.parquet."""

    CHUNK_ORDER = "text_length_asc_chunk_id_asc"
    VALID_SOURCE_TYPES = ("annotation", "drug_label", "guideline", "pubmed")

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        qdrant_path: Path = Path("data/processed/qdrant_db"),
        collection_name: str = "pharmagraph_chunks",
        chunks_path: Path = Path("data/processed/chunks.parquet"),
    ):
        self.model_name = model_name
        self.qdrant_path = qdrant_path
        self.collection_name = collection_name
        self.chunks_path = chunks_path
        self.manifest_path = qdrant_path / "qdrant_manifest.json"
        self.checkpoint_path = qdrant_path / "build_checkpoint.json"
        self.progress_log_path = qdrant_path / "build_progress.log"
        self._coverage_cache: Optional[Dict[str, Any]] = None

        self.qdrant_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(self.qdrant_path))
        self.encoder = SentenceTransformer(self.model_name)
        dim_fn = getattr(self.encoder, "get_embedding_dimension", None) or getattr(
            self.encoder, "get_sentence_embedding_dimension"
        )
        self.vector_dim = dim_fn() or 384

    @staticmethod
    def _point_id_for_chunk(chunk_id: str) -> str:
        """Deterministic UUIDv5 per chunk_id so multi-stage builds never overwrite prior stages."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    def _detect_model_version(self) -> str:
        """Determine concise model version string from model name/metadata."""
        if "-v" in self.model_name:
            tail = self.model_name.rsplit("-v", 1)[-1].strip()
            if tail:
                return tail
        return "unknown"

    def _log_progress(self, message: str, log_path: Optional[Path] = None) -> None:
        target = log_path or self.progress_log_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(message + "\n")
        print(message, flush=True)

    def _expected_counts_by_type(self) -> Dict[str, int]:
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks table not found at {self.chunks_path}")
        con = duckdb.connect(":memory:")
        rows = con.execute(
            f"""
            SELECT source_type, COUNT(*)
            FROM '{self.chunks_path.as_posix()}'
            GROUP BY source_type
            ORDER BY source_type ASC
            """
        ).fetchall()
        return {str(st): int(cnt) for st, cnt in rows}

    def _normalize_source_types(
        self,
        source_types: Optional[List[str]],
        expected_counts_all: Dict[str, int],
    ) -> List[str]:
        available = sorted(expected_counts_all.keys())
        if source_types is None:
            return available
        cleaned = sorted({s.strip() for s in source_types if s and s.strip()})
        if not cleaned:
            raise ValueError("source_types must contain at least one valid source type.")
        valid_pool = set(available) | set(self.VALID_SOURCE_TYPES)
        unknown = [s for s in cleaned if s not in valid_pool]
        if unknown:
            raise ValueError(
                f"Invalid source_type(s): {unknown}. Valid types: {sorted(valid_pool)}"
            )
        return cleaned

    def _load_ordered_chunks(
        self, source_types: Optional[List[str]] = None
    ) -> List[Tuple[Any, ...]]:
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks table not found at {self.chunks_path}")
        con = duckdb.connect(":memory:")
        params: List[Any] = []
        where_clause = ""
        if source_types is not None:
            placeholders = ", ".join(["?"] * len(source_types))
            where_clause = f"WHERE source_type IN ({placeholders})"
            params.extend(source_types)
        sql = f"""
            SELECT chunk_id, source_type, source_id, title, content,
                   date, date_precision, entity_ids
            FROM '{self.chunks_path.as_posix()}'
            {where_clause}
            ORDER BY LENGTH(TRIM(COALESCE(title, '') || ' ' || COALESCE(content, ''))) ASC,
                     chunk_id ASC
        """
        return con.execute(sql, params).fetchall()

    def _scroll_collection_counts(self) -> Tuple[int, Dict[str, Dict[str, int]], int]:
        """
        Scroll existing Qdrant collection payloads (without vectors) to count unique chunk_ids
        and duplicates per source_type.
        Returns (total_points, {st: {"unique": n, "duplicates": d}}, total_unique).
        """
        if not self.client.collection_exists(self.collection_name):
            return 0, {}, 0
        total_points = self.client.count(collection_name=self.collection_name).count
        seen_by_cid: Dict[str, str] = {}
        dup_by_type: Dict[str, int] = {}
        unique_by_type: Dict[str, int] = {}
        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=["chunk_id", "source_type"],
                with_vectors=False,
            )
            if not points:
                break
            for pt in points:
                payload = pt.payload or {}
                cid = str(payload.get("chunk_id", ""))
                st = str(payload.get("source_type", "unknown"))
                if cid in seen_by_cid:
                    dup_by_type[st] = dup_by_type.get(st, 0) + 1
                else:
                    seen_by_cid[cid] = st
                    unique_by_type[st] = unique_by_type.get(st, 0) + 1
            if next_offset is None:
                break
            offset = next_offset

        all_types = set(unique_by_type.keys()) | set(dup_by_type.keys())
        by_type = {
            st: {"unique": unique_by_type.get(st, 0), "duplicates": dup_by_type.get(st, 0)}
            for st in sorted(all_types)
        }
        return total_points, by_type, len(seen_by_cid)

    def get_coverage_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Return per-source_type coverage summary comparing indexed Qdrant points to chunks.parquet.
        Works cleanly both with new multi-stage manifests and legacy minimal manifests.
        """
        if self._coverage_cache is not None and not force_refresh:
            return self._coverage_cache

        expected_all = (
            self._expected_counts_by_type() if self.chunks_path.exists() else {}
        )
        indexed_by_type: Dict[str, int] = {}
        complete_by_type: Dict[str, bool] = {}

        loaded_from_manifest = False
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                m_pts = manifest.get("points_per_source_type")
                m_comp = manifest.get("complete_per_source_type")
                if isinstance(m_pts, dict) and isinstance(m_comp, dict):
                    indexed_by_type = {str(k): int(v) for k, v in m_pts.items()}
                    complete_by_type = {str(k): bool(v) for k, v in m_comp.items()}
                    loaded_from_manifest = True
            except Exception:
                loaded_from_manifest = False

        if not loaded_from_manifest:
            _, by_type, _ = self._scroll_collection_counts()
            indexed_by_type = {st: vals["unique"] for st, vals in by_type.items()}
            complete_by_type = {
                st: (
                    indexed_by_type.get(st, 0) == exp
                    and exp > 0
                    and by_type.get(st, {}).get("duplicates", 0) == 0
                )
                for st, exp in expected_all.items()
            }

        all_types = sorted(set(expected_all.keys()) | set(indexed_by_type.keys()))
        per_source_type: Dict[str, Dict[str, Any]] = {}
        covered_types: List[str] = []
        complete_types: List[str] = []

        for st in all_types:
            exp = expected_all.get(st, 0)
            idx_n = indexed_by_type.get(st, 0)
            comp = bool(complete_by_type.get(st, idx_n >= exp and exp > 0))
            per_source_type[st] = {
                "indexed": idx_n,
                "expected": exp,
                "complete": comp,
            }
            if idx_n > 0:
                covered_types.append(st)
            if comp:
                complete_types.append(st)

        is_partial = any(not info["complete"] for info in per_source_type.values()) or not all_types
        summary = {
            "per_source_type": per_source_type,
            "is_partial": is_partial,
            "covered_source_types": covered_types,
            "complete_source_types": complete_types,
        }
        self._coverage_cache = summary
        return summary

    def build_index(
        self,
        force_rebuild: bool = False,
        batch_size: int = 16,
        checkpoint_every: int = 10,
        progress_log_path: Optional[Path] = None,
        max_batches: Optional[int] = None,
        source_types: Optional[List[str]] = None,
    ) -> int:
        """
        Embed chunks for the requested source_types and populate local Qdrant collection
        with per-stage checkpoint & resume. Appends safely to an existing collection when
        building a subsequent stage without --force.
        """
        expected_counts_all = self._expected_counts_by_type()
        target_types = self._normalize_source_types(source_types, expected_counts_all)
        rows = self._load_ordered_chunks(target_types)
        total_chunks = len(rows)
        chunks_sha256 = compute_sha256(self.chunks_path)

        exists = self.client.collection_exists(self.collection_name)

        start_idx = 0
        prior_elapsed = 0.0
        cur_ram, max_ram_seen = get_process_ram_mb()

        # Check whether the requested source_types are already completely built
        if exists and not force_rebuild and not self.checkpoint_path.exists():
            count = self.client.count(collection_name=self.collection_name).count
            manifest_ok = False
            if self.manifest_path.exists():
                try:
                    manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                    complete_map = manifest.get("complete_per_source_type", {})
                    if not isinstance(complete_map, dict) or not complete_map:
                        # Fallback for older manifest without per-type map
                        stages_done = manifest.get("total_points") == len(
                            self._load_ordered_chunks(None)
                        )
                    else:
                        stages_done = all(
                            bool(complete_map.get(st, False)) for st in target_types
                        )
                    manifest_ok = (
                        manifest.get("chunks_parquet_sha256") == chunks_sha256
                        and manifest.get("model_name") == self.model_name
                        and stages_done
                    )
                except Exception:
                    manifest_ok = False
            if count > 0 and total_chunks > 0 and manifest_ok:
                return count

        # Check for valid resumable checkpoint for this stage
        resumed = False
        if exists and not force_rebuild and self.checkpoint_path.exists():
            try:
                ckpt = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                ckpt_types = ckpt.get("source_types")
                if (
                    ckpt_types is not None
                    and sorted(str(s) for s in ckpt_types) != target_types
                ):
                    raise RuntimeError(
                        f"Existing checkpoint in {self.checkpoint_path} is for "
                        f"source_types={ckpt_types}, not requested source_types={target_types}. "
                        "Resume the active stage first or pass --force on a separate --output-dir."
                    )
                ckpt_next = int(ckpt.get("next_idx", -1))
                if (
                    ckpt.get("chunks_parquet_sha256") == chunks_sha256
                    and ckpt.get("model_name") == self.model_name
                    and ckpt.get("collection_name") == self.collection_name
                    and ckpt.get("chunk_order", self.CHUNK_ORDER) == self.CHUNK_ORDER
                    and int(ckpt.get("total_chunks", -1)) == total_chunks
                    and 0 <= ckpt_next <= total_chunks
                ):
                    start_idx = ckpt_next
                    prior_elapsed = float(ckpt.get("elapsed_seconds", 0.0))
                    max_ram_seen = max(max_ram_seen, float(ckpt.get("peak_ram_mb", 0.0)))
                    resumed = True
            except RuntimeError:
                raise
            except Exception:
                resumed = False

        log_target = progress_log_path or self.progress_log_path
        now_utc = datetime.now(timezone.utc).isoformat()
        types_label = ",".join(target_types)

        if force_rebuild or not exists:
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
            if self.manifest_path.exists():
                self.manifest_path.unlink()
            if exists:
                self.client.delete_collection(self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_dim, distance=Distance.COSINE),
            )
            self._log_progress(
                f"[{now_utc}] START index build: source_types=[{types_label}], "
                f"total={total_chunks}, batch_size={batch_size}, "
                f"checkpoint_every={checkpoint_every}, model={self.model_name}, "
                f"chunks_sha256={chunks_sha256[:12]}...",
                log_path=log_target,
            )
        elif resumed:
            self._log_progress(
                f"[{now_utc}] RESUME index build: source_types=[{types_label}], "
                f"next_idx={start_idx}/{total_chunks} "
                f"({(100.0 * start_idx / total_chunks) if total_chunks else 100.0:.1f}%), "
                f"batch_size={batch_size}, prior_elapsed={prior_elapsed:.1f}s",
                log_path=log_target,
            )
        else:
            # Stage 2+ append into existing collection without deleting Stage 1 points
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
            existing_cnt = self.client.count(self.collection_name).count
            self._log_progress(
                f"[{now_utc}] APPEND index build: source_types=[{types_label}], "
                f"stage_total={total_chunks}, existing_points={existing_cnt}, "
                f"batch_size={batch_size}, model={self.model_name}, "
                f"chunks_sha256={chunks_sha256[:12]}...",
                log_path=log_target,
            )

        session_start = time.perf_counter()
        session_chunks_done = 0
        batches_executed = 0

        for batch_num, batch_start in enumerate(
            range(start_idx, total_chunks, batch_size), start=1
        ):
            if max_batches is not None and batches_executed >= max_batches:
                break

            batch_rows = rows[batch_start : batch_start + batch_size]
            texts_to_embed = [f"{r[3] or ''} {r[4] or ''}".strip() for r in batch_rows]
            embeddings = self.encoder.encode(
                texts_to_embed,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )

            points: List[PointStruct] = []
            for offset, r in enumerate(batch_rows):
                chunk_id, st, sid, title, content, dt, dp, eids = r
                point_id = self._point_id_for_chunk(str(chunk_id))
                payload: Dict[str, Any] = {
                    "chunk_id": chunk_id,
                    "source_type": st,
                    "source_id": sid,
                    "title": title or "",
                    "content": content or "",
                    "date": dt or "unknown",
                    "date_precision": dp or "unknown",
                    "entity_ids": list(eids) if eids else [],
                }
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embeddings[offset].tolist(),
                        payload=payload,
                    )
                )

            # Upsert batch immediately to Qdrant SQLite storage
            self.client.upsert(collection_name=self.collection_name, points=points)
            next_idx = batch_start + len(batch_rows)
            session_chunks_done += len(batch_rows)
            batches_executed += 1

            cur_ram, peak_ram = get_process_ram_mb()
            max_ram_seen = max(max_ram_seen, peak_ram, cur_ram)

            is_final = next_idx >= total_chunks
            is_limit_stop = max_batches is not None and batches_executed >= max_batches
            if is_final or is_limit_stop or (batch_num % max(1, checkpoint_every) == 0):
                session_dt = max(1e-6, time.perf_counter() - session_start)
                total_elapsed = prior_elapsed + session_dt
                rate = session_chunks_done / session_dt
                remaining = total_chunks - next_idx
                eta_min = (remaining / rate) / 60.0 if rate > 0 else 0.0

                ckpt_data = {
                    "source_types": target_types,
                    "chunks_parquet_sha256": chunks_sha256,
                    "model_name": self.model_name,
                    "collection_name": self.collection_name,
                    "chunk_order": self.CHUNK_ORDER,
                    "batch_size": batch_size,
                    "total_chunks": total_chunks,
                    "next_idx": next_idx,
                    "peak_ram_mb": round(max_ram_seen, 2),
                    "elapsed_seconds": round(total_elapsed, 2),
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                write_raw_file_atomically(
                    self.checkpoint_path,
                    json.dumps(ckpt_data, indent=2).encode("utf-8"),
                    allow_overwrite=True,
                )
                pct = (100.0 * next_idx / total_chunks) if total_chunks > 0 else 100.0
                self._log_progress(
                    f"[{ckpt_data['updated_at_utc']}] [{types_label}] "
                    f"{next_idx}/{total_chunks} ({pct:.1f}%) "
                    f"| rate={rate:.2f} chunks/s | ETA={eta_min:.1f}m "
                    f"| RAM={cur_ram:.1f} MB (peak={max_ram_seen:.1f} MB)",
                    log_path=log_target,
                )
                gc.collect()

        final_count = self.client.count(collection_name=self.collection_name).count

        # Write/update manifest only when the requested stage completed
        completed_stage = True
        if self.checkpoint_path.exists():
            try:
                ckpt_after = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                completed_stage = int(ckpt_after.get("next_idx", 0)) >= total_chunks
            except Exception:
                completed_stage = False

        if completed_stage:
            scrolled_total, by_type, _ = self._scroll_collection_counts()
            counts_by_type = {
                st: by_type.get(st, {}).get("unique", 0)
                for st in sorted(set(expected_counts_all.keys()) | set(by_type.keys()))
            }
            complete_per_type = {
                st: (
                    counts_by_type.get(st, 0) == exp
                    and exp > 0
                    and by_type.get(st, {}).get("duplicates", 0) == 0
                )
                for st, exp in sorted(expected_counts_all.items())
            }

            cur_ram, peak_ram = get_process_ram_mb()
            max_ram_seen = max(max_ram_seen, peak_ram, cur_ram)
            manifest_data = {
                "model_name": self.model_name,
                "model_version": self._detect_model_version(),
                "vector_dimension": self.vector_dim,
                "distance_metric": "Cosine",
                "collection_name": self.collection_name,
                "total_points": final_count,
                "points_per_source_type": counts_by_type,
                "expected_per_source_type": dict(sorted(expected_counts_all.items())),
                "complete_per_source_type": complete_per_type,
                "last_completed_stage_source_types": target_types,
                "chunks_parquet_sha256": chunks_sha256,
                "batch_size": batch_size,
                "peak_ram_mb": round(max_ram_seen, 2),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            write_raw_file_atomically(
                self.manifest_path,
                json.dumps(manifest_data, indent=2).encode("utf-8"),
                allow_overwrite=True,
            )
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
            self._coverage_cache = None
            self._log_progress(
                f"[{manifest_data['created_at_utc']}] STAGE COMPLETE [{types_label}] "
                f"total_points={final_count} (scrolled={scrolled_total}) "
                f"| complete={complete_per_type} "
                f"| peak_ram={manifest_data['peak_ram_mb']} MB | manifest={self.manifest_path}",
                log_path=log_target,
            )

        return final_count

    def verify_index(self, source_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Verify Qdrant collection matches chunks.parquet exactly for the specified source_types
        (or all source_types if omitted), and report per-type coverage across the corpus.
        """
        expected_counts_all = self._expected_counts_by_type()
        target_types = self._normalize_source_types(source_types, expected_counts_all)
        target_set = set(target_types)

        con = duckdb.connect(":memory:")
        parquet_rows = con.execute(
            f"SELECT chunk_id, source_type FROM '{self.chunks_path.as_posix()}'"
        ).fetchall()
        expected_ids_target = {r[0] for r in parquet_rows if r[1] in target_set}
        expected_by_type_target: Dict[str, int] = {}
        for _, st in parquet_rows:
            if st in target_set:
                expected_by_type_target[st] = expected_by_type_target.get(st, 0) + 1

        qdrant_count = (
            self.client.count(collection_name=self.collection_name).count
            if self.client.collection_exists(self.collection_name)
            else 0
        )

        seen_ids_all: Dict[str, int] = {}
        actual_by_type_all: Dict[str, int] = {}
        seen_ids_target: Dict[str, int] = {}
        actual_by_type_target: Dict[str, int] = {}
        offset = None
        scrolled_total = 0

        if qdrant_count > 0:
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["chunk_id", "source_type"],
                    with_vectors=False,
                )
                if not points:
                    break
                for pt in points:
                    scrolled_total += 1
                    payload = pt.payload or {}
                    cid = str(payload.get("chunk_id", ""))
                    st = str(payload.get("source_type", ""))
                    seen_ids_all[cid] = seen_ids_all.get(cid, 0) + 1
                    actual_by_type_all[st] = actual_by_type_all.get(st, 0) + 1
                    if st in target_set:
                        seen_ids_target[cid] = seen_ids_target.get(cid, 0) + 1
                        actual_by_type_target[st] = actual_by_type_target.get(st, 0) + 1
                if next_offset is None:
                    break
                offset = next_offset

        duplicate_ids = [cid for cid, cnt in seen_ids_target.items() if cnt > 1]
        missing_ids = sorted(expected_ids_target - set(seen_ids_target.keys()))
        extra_ids = sorted(set(seen_ids_target.keys()) - expected_ids_target)

        coverage_per_type: Dict[str, Dict[str, Any]] = {}
        for st in sorted(expected_counts_all.keys()):
            exp_n = expected_counts_all[st]
            act_n = actual_by_type_all.get(st, 0)
            coverage_per_type[st] = {
                "indexed": act_n,
                "expected": exp_n,
                "complete": act_n == exp_n and exp_n > 0,
            }

        is_exact_match = (
            qdrant_count == scrolled_total
            and sum(actual_by_type_target.values()) == len(expected_ids_target)
            and len(duplicate_ids) == 0
            and len(missing_ids) == 0
            and len(extra_ids) == 0
            and actual_by_type_target == expected_by_type_target
        )

        return {
            "is_exact_match": is_exact_match,
            "verified_source_types": target_types,
            "parquet_count": len(expected_ids_target),
            "qdrant_count": qdrant_count,
            "scrolled_total": scrolled_total,
            "unique_chunk_ids": len(seen_ids_target),
            "duplicate_count": len(duplicate_ids),
            "missing_count": len(missing_ids),
            "extra_count": len(extra_ids),
            "expected_by_source_type": dict(sorted(expected_by_type_target.items())),
            "actual_by_source_type": dict(sorted(actual_by_type_target.items())),
            "coverage_per_source_type": coverage_per_type,
            "chunks_parquet_sha256": compute_sha256(self.chunks_path),
        }

    def close(self):
        """Explicitly close QdrantClient."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def search(self, query: str, top_k: int = 50) -> List[MeaningHit]:
        """Search chunks with dense vector embeddings."""
        query_vector = self.encoder.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
            )
            search_result = response.points
        else:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
            )

        hits: List[MeaningHit] = []
        for rank, res in enumerate(search_result, start=1):
            payload = res.payload or {}
            hits.append(
                MeaningHit(
                    chunk_id=str(payload.get("chunk_id", "")),
                    source_type=str(payload.get("source_type", "")),
                    source_id=str(payload.get("source_id", "")),
                    title=str(payload.get("title", "")),
                    content=str(payload.get("content", "")),
                    date=str(payload.get("date", "unknown")),
                    date_precision=str(payload.get("date_precision", "unknown")),
                    entity_ids=list(payload.get("entity_ids", [])),
                    dense_score=float(res.score),
                    rank=rank,
                )
            )
        return hits
