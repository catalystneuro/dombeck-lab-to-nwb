"""Batch conversion of all Chen et al. 2026 (LRRK2) sessions to NWB.

Edit DATA_DIR and NWB_OUTPUT_DIR at the top of this file, then run::

    python src/dombeck_lab_to_nwb/chen2026/convert_all_sessions.py

Sessions run in parallel (one process per CPU core by default).
Failed sessions are logged individually and do not abort the batch.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from dombeck_lab_to_nwb.chen2026.convert_session import convert_session

# ---------------------------------------------------------------------------
# Configure paths here
# ---------------------------------------------------------------------------
DATA_DIR = Path("/Users/weian/lrrk2_data")
NWB_OUTPUT_DIR = Path("/Users/weian/lrrk2_data/nwb-output")
STUB_TEST = False
MAX_WORKERS = 4  # number of parallel conversion processes
# ---------------------------------------------------------------------------

# Complete animal × session table derived from LRRK2-animal-list-meta.mat
# and the filename column of each *_data.mat file.
# Columns: animal_id, group, genotype, abf_filename
SESSIONS = [
    # Anxa-LRRK2 group (DLS, Anxa1-iCre)
    {"animal_id": "3742", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_01_24_0006.abf"},
    {"animal_id": "3743", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_01_24_0004.abf"},
    {"animal_id": "3947", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_01_27_0000.abf"},
    {"animal_id": "3948", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_01_27_0002.abf"},
    {"animal_id": "4004", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_08_13_0001.abf"},
    {"animal_id": "4005", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_08_13_0002.abf"},
    {"animal_id": "4007", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_08_13_0005.abf"},
    {"animal_id": "4253", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_08_14_0003.abf"},
    {"animal_id": "4398", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_05_02_0001.abf"},
    {"animal_id": "4401", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_07_02_0005.abf"},
    {"animal_id": "4558", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_05_20_0001.abf"},
    {"animal_id": "4561", "group": "Anxa", "genotype": "WT", "abf_filename": "2025_07_02_0003.abf"},
    {"animal_id": "4651", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_07_02_0001.abf"},
    {"animal_id": "4652", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_05_20_0003.abf"},
    {"animal_id": "4885", "group": "Anxa", "genotype": "GS", "abf_filename": "2025_01_24_0002.abf"},
    # Calb-LRRK2 group (DMS, Calb1-Cre)
    {"animal_id": "302", "group": "Calb", "genotype": "GS", "abf_filename": "2025_11_10_0005.abf"},
    {"animal_id": "306", "group": "Calb", "genotype": "GS", "abf_filename": "2025_11_10_0009.abf"},
    {"animal_id": "671", "group": "Calb", "genotype": "WT", "abf_filename": "2026_03_19_0000.abf"},
    {"animal_id": "673", "group": "Calb", "genotype": "WT", "abf_filename": "2026_03_19_0004.abf"},
    {"animal_id": "688", "group": "Calb", "genotype": "WT", "abf_filename": "2025_12_17_0007.abf"},
    {"animal_id": "740", "group": "Calb", "genotype": "GS", "abf_filename": "2026_03_24_0003.abf"},
    {"animal_id": "741", "group": "Calb", "genotype": "GS", "abf_filename": "2026_03_24_0004.abf"},
    {"animal_id": "848", "group": "Calb", "genotype": "GS", "abf_filename": "2025_12_17_0006.abf"},
    {"animal_id": "852", "group": "Calb", "genotype": "GS", "abf_filename": "2025_12_17_0003.abf"},
    {"animal_id": "935", "group": "Calb", "genotype": "GS", "abf_filename": "2026_04_23_0004.abf"},
    {"animal_id": "966", "group": "Calb", "genotype": "WT", "abf_filename": "2026_04_23_0003.abf"},
    {"animal_id": "1803", "group": "Calb", "genotype": "WT", "abf_filename": "2025_11_10_0002.abf"},
]


def _session_to_nwb(session: dict, data_dir: Path, nwb_output_dir: Path, stub_test: bool) -> str:
    """Convert one session; return a status string."""
    animal_id = session["animal_id"]
    group = session["group"]
    genotype = session["genotype"]
    group_dir = f"{group}-LRRK2"

    abf_file = data_dir / group_dir / session["abf_filename"]

    convert_session(
        file_path=abf_file,
        nwb_folder_path=nwb_output_dir,
        subject_id=animal_id,
        group=group,
        genotype=genotype,
        stub_test=stub_test,
    )
    return f"OK  {animal_id}"


def _safe_session_to_nwb(session: dict, data_dir: Path, nwb_output_dir: Path, stub_test: bool) -> str:
    """Wrapper that catches exceptions and writes an error log instead of crashing the pool."""
    try:
        return _session_to_nwb(session, data_dir, nwb_output_dir, stub_test)
    except Exception:
        animal_id = session["animal_id"]
        error_path = nwb_output_dir / f"error_{animal_id}.txt"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(f"Session: {session}\n\n{traceback.format_exc()}")
        return f"ERR {animal_id} — see {error_path}"


def dataset_to_nwb(
    data_dir: Path = DATA_DIR,
    nwb_output_dir: Path = NWB_OUTPUT_DIR,
    stub_test: bool = STUB_TEST,
    max_workers: int = MAX_WORKERS,
) -> None:
    nwb_output_dir.mkdir(parents=True, exist_ok=True)

    futures = {}
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        for session in SESSIONS:
            future = pool.submit(_safe_session_to_nwb, session, data_dir, nwb_output_dir, stub_test)
            futures[future] = session["animal_id"]

        results = []
        with tqdm(total=len(futures), desc="Converting sessions", unit="session") as pbar:
            for future in as_completed(futures):
                status = future.result()
                results.append(status)
                pbar.update(1)
                pbar.set_postfix_str(status)

    print("\n--- Conversion summary ---")
    errors = [r for r in results if r.startswith("ERR")]
    ok = [r for r in results if r.startswith("OK")]
    print(f"  Succeeded: {len(ok)} / {len(SESSIONS)}")
    if errors:
        print(f"  Failed ({len(errors)}):")
        for e in errors:
            print(f"    {e}")


if __name__ == "__main__":
    dataset_to_nwb()
