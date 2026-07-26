"""Batch conversion of all Chen et al. 2026 (LRRK2) sessions to NWB.

Edit DATA_DIR and NWB_OUTPUT_DIR at the top of this file, then run::

    python src/dombeck_lab_to_nwb/chen2026/convert_all_sessions.py

Sessions run in parallel (one process per CPU core by default).
Failed sessions are logged individually and do not abort the batch.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from dombeck_lab_to_nwb.chen2026.convert_session import convert_session

# ---------------------------------------------------------------------------
# Configure paths here
# ---------------------------------------------------------------------------
DATA_DIR = Path("/Users/weian/lrrk2_data")
NWB_OUTPUT_DIR = Path("/Users/weian/lrrk2_data/nwb-output")
SUBJECT_METADATA_XLSX = Path("/Users/weian/lrrk2_data/metadata-LRRK2-chen2026.xlsx")
STIM_SEQUENCE_XLSX = Path("/Users/weian/lrrk2_data/stimulation sequence LRRK2.xlsx")
STUB_TEST = False
MAX_WORKERS = 4  # number of parallel conversion processes
# ---------------------------------------------------------------------------

# Code → power (mW) mapping from stimulation sequence LRRK2.xlsx
_CODE_TO_POWER: dict[str, float] = {
    "a": 0.1,
    "b": 0.25,
    "c": 0.5,
    "d": 1.0,
    "e": 1.5,
    "f": 2.0,
    "g": 3.0,
    "h": 4.0,
}


def _load_stim_sequences(xlsx_path: Path) -> dict[str, list[float]]:
    """Return {'a': [...64 powers...], 'b': [...64 powers...]} from the stim sequence xlsx."""
    df = pd.read_excel(xlsx_path, header=None)
    sequences: dict[str, list[float]] = {}
    for _, row in df.iterrows():
        label = str(row.iloc[0]).strip()
        if label.lower().startswith("sequence a"):
            codes = [str(v).strip("' ") for v in row.iloc[1:] if pd.notna(v)]
            sequences["a"] = [_CODE_TO_POWER[c] for c in codes]
        elif label.lower().startswith("sequence b"):
            codes = [str(v).strip("' ") for v in row.iloc[1:] if pd.notna(v)]
            sequences["b"] = [_CODE_TO_POWER[c] for c in codes]
    return sequences


def _load_subject_metadata(xlsx_path: Path) -> dict[str, dict]:
    """Return a dict keyed by abf filename → {sex, date_of_birth, stim_sequence}."""
    df = pd.read_excel(xlsx_path)
    lookup: dict[str, dict] = {}
    for _, row in df.iterrows():
        filename = str(row["filename"]).strip("'")
        sex = str(row["sex"]).strip().upper()
        dob: datetime = pd.to_datetime(row["DOB"]).to_pydatetime().replace(tzinfo=timezone.utc)
        stim_seq = str(row["stim_sequence"]).strip().lower()
        lookup[filename] = {"sex": sex, "date_of_birth": dob, "stim_sequence": stim_seq}
    return lookup


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


def _session_to_nwb(
    session: dict,
    data_dir: Path,
    nwb_output_dir: Path,
    stub_test: bool,
    subject_lookup: dict[str, dict],
    stim_sequences: dict[str, list[float]],
) -> str:
    """Convert one session; return a status string."""
    animal_id = session["animal_id"]
    group = session["group"]
    genotype = session["genotype"]
    group_dir = f"{group}-LRRK2"

    abf_file = data_dir / group_dir / session["abf_filename"]
    mat_file = data_dir / group_dir / animal_id / f"{animal_id}_data.mat"

    subject_info = subject_lookup.get(session["abf_filename"], {})
    sex = subject_info.get("sex", "U")
    date_of_birth = subject_info.get("date_of_birth")
    stim_seq_key = subject_info.get("stim_sequence")
    power_sequence = stim_sequences.get(stim_seq_key) if stim_seq_key else None

    convert_session(
        file_path=abf_file,
        mat_file=mat_file,
        nwb_folder_path=nwb_output_dir,
        subject_id=animal_id,
        group=group,
        genotype=genotype,
        sex=sex,
        date_of_birth=date_of_birth,
        power_sequence=power_sequence,
        stub_test=stub_test,
    )
    return f"OK  {animal_id}"


def _safe_session_to_nwb(
    session: dict,
    data_dir: Path,
    nwb_output_dir: Path,
    stub_test: bool,
    subject_lookup: dict[str, dict],
    stim_sequences: dict[str, list[float]],
) -> str:
    """Wrapper that catches exceptions and writes an error log instead of crashing the pool."""
    try:
        return _session_to_nwb(session, data_dir, nwb_output_dir, stub_test, subject_lookup, stim_sequences)
    except Exception:
        animal_id = session["animal_id"]
        error_path = nwb_output_dir / f"error_{animal_id}.txt"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(f"Session: {session}\n\n{traceback.format_exc()}")
        return f"ERR {animal_id} — see {error_path}"


def dataset_to_nwb(
    data_dir: Path = DATA_DIR,
    nwb_output_dir: Path = NWB_OUTPUT_DIR,
    subject_metadata_xlsx: Path = SUBJECT_METADATA_XLSX,
    stim_sequence_xlsx: Path = STIM_SEQUENCE_XLSX,
    stub_test: bool = STUB_TEST,
    max_workers: int = MAX_WORKERS,
) -> None:
    nwb_output_dir.mkdir(parents=True, exist_ok=True)

    subject_lookup = _load_subject_metadata(subject_metadata_xlsx)
    stim_sequences = _load_stim_sequences(stim_sequence_xlsx)

    futures = {}
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        for session in SESSIONS:
            future = pool.submit(
                _safe_session_to_nwb, session, data_dir, nwb_output_dir, stub_test, subject_lookup, stim_sequences
            )
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
