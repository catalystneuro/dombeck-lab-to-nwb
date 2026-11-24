"""Convert a single Chen et al. 2026 session to NWB.

Edit the paths and parameters in the ``if __name__ == "__main__"`` block at the
bottom of this file, then run::

    python convert_session.py
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from neuroconv.utils import dict_deep_update, load_dict_from_file

from dombeck_lab_to_nwb.chen2026.nwbconverter import Chen2026NWBConverter

METADATA_DIR = Path(__file__).parent / "metadata"

# Map group → (raw_signal_key, isosbestic_key, corrected_key, corrected_iso_key, dff_key, dff_iso_key)
GROUP_TO_METADATA_KEYS = {
    "Anxa": {
        "RawSignal": "raw_signal_anxa",
        "IsosbesticControl": "isosbestic_anxa",
        "CorrectedSignal": "corrected_signal_anxa",
        "CorrectedIsosbestic": "corrected_isosbestic_anxa",
        "DfOverF": "dff_anxa",
        "DfOverFIsosbestic": "dff_isosbestic_anxa",
    },
    "Calb": {
        "RawSignal": "raw_signal_calb",
        "IsosbesticControl": "isosbestic_calb",
        "CorrectedSignal": "corrected_signal_calb",
        "CorrectedIsosbestic": "corrected_isosbestic_calb",
        "DfOverF": "dff_calb",
        "DfOverFIsosbestic": "dff_isosbestic_calb",
    },
}

# Map group → (key suffix of the group's recording site, key suffix of the other group's site) in
# fiber_photometry.yaml. Each mouse has one photometry fiber: DLS for Anxa-LRRK2, DMS for Calb-LRRK2.
GROUP_TO_SITE_SUFFIXES = {
    "Anxa": ("_dls", "_anxa"),
    "Calb": ("_dms", "_calb"),
}


def _select_recording_site(fp_metadata: dict, group: str) -> dict:
    """Drop the fiber, injection, indicator, table rows and series entries of the other group's recording site.

    fiber_photometry.yaml describes both sites. A file holds one mouse with one fiber, so only the entries of
    that mouse's site are written.
    """
    other_group = "Calb" if group == "Anxa" else "Anxa"
    other_site, other_series = GROUP_TO_SITE_SUFFIXES[other_group]

    def keep(key: str) -> bool:
        return not (key.endswith(other_site) or key.endswith(other_series) or key.startswith(other_site[1:] + "_"))

    fp_metadata = dict(fp_metadata)
    fp_metadata["Devices"] = {key: value for key, value in fp_metadata["Devices"].items() if keep(key)}
    fiber_photometry = dict(fp_metadata["FiberPhotometry"])
    for section in ("FiberPhotometryVirusInjections", "FiberPhotometryIndicators"):
        fiber_photometry[section] = {key: value for key, value in fiber_photometry[section].items() if keep(key)}
    table = dict(fiber_photometry["FiberPhotometryTable"])
    table["rows"] = {key: value for key, value in table["rows"].items() if keep(key)}
    fiber_photometry["FiberPhotometryTable"] = table
    fp_metadata["FiberPhotometry"] = {key: value for key, value in fiber_photometry.items() if keep(key)}
    return fp_metadata


GENOTYPE_LABELS = {
    "WT": "LRRK2-WT",
    "GS": "LRRK2-G2019S",
}

_OPTO_THRESHOLD_V = 0.01  # V — catches both high (~1.2 V) and low (~0.05 V) amplitude trains
_MIN_PULSE_S = 0.002  # pulses are 8 or 9 ms; single-sample (0.5 ms) threshold crossings are noise
_MIN_POWER_AMPLITUDE_CORRELATION = 0.9


def _detect_opto_pulse_params(
    abf_file: str | Path,
) -> tuple[list[float], list[float], list[int], list[float]]:
    """Detect per-epoch pulse parameters from the raw ABF opto_TTL channel.

    Returns (pulse_length_in_ms, period_in_ms, number_pulses_per_pulse_train, amplitude_in_V),
    one value per detected stimulation train. Trains are separated by gaps > 1 s
    between consecutive pulse onsets; intra-train inter-onset intervals are used
    to compute the period. The amplitude is the median opto_TTL voltage while the
    pulses of the train are on; it scales with the commanded LED power.
    """
    import numpy as np
    import pyabf

    abf = pyabf.ABF(str(abf_file), loadData=True)
    channel_names = [abf.adcNames[i].strip() for i in range(abf.channelCount)]

    opto_idx = channel_names.index("opto_TTL")
    opto = abf.data[opto_idx]
    sr = float(abf.dataRate)

    above = opto > _OPTO_THRESHOLD_V
    diff = np.diff(above.astype(np.int8))
    rising = np.where(diff == 1)[0]
    falling = np.where(diff == -1)[0]

    if len(falling) and len(rising) and falling[0] < rising[0]:
        falling = falling[1:]
    n = min(len(rising), len(falling))
    rising = rising[:n]
    falling = falling[:n]

    # Drop isolated threshold crossings (two sessions have one 0.5 ms blip between trains);
    # counted as a train they shift the parameters of every later epoch by one row.
    is_pulse = (falling - rising) / sr >= _MIN_PULSE_S
    rising = rising[is_pulse]
    falling = falling[is_pulse]
    n = len(rising)

    if n == 0:
        return [], [], [], []

    onsets = rising / sr
    durations = (falling - rising) / sr

    # Split into trains: gap > 1 s between consecutive pulse onsets
    inter_onset = np.diff(onsets)
    breaks = np.where(inter_onset > 1.0)[0]
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks + 1, [n]])

    pulse_length_ms: list[float] = []
    period_ms: list[float] = []
    n_pulses: list[int] = []
    amplitude_v: list[float] = []

    for s, e in zip(starts, ends):
        epoch_onsets = onsets[s:e]
        epoch_durations = durations[s:e]
        pulse_length_ms.append(round(float(np.mean(epoch_durations)) * 1000, 0))
        period_ms.append(round(float(np.mean(np.diff(epoch_onsets))) * 1000, 0))
        n_pulses.append(int(e - s))
        train = opto[rising[s] : falling[e - 1] + 1]
        amplitude_v.append(float(np.median(train[train > 0.5 * train.max()])))

    return pulse_length_ms, period_ms, n_pulses, amplitude_v


def _check_power_sequence(power_sequence: list[float], amplitude_v: list[float], abf_file: str | Path) -> None:
    """Raise if the labelled power order disagrees with the opto_TTL amplitude of the trains.

    The opto_TTL amplitude increases with the commanded power, so the rank correlation
    between the two is ~0.99 when the stimulation sequence label is right and negative
    when the session was run with the other sequence.
    """
    from scipy.stats import spearmanr

    if len(power_sequence) != len(amplitude_v):
        raise ValueError(
            f"{Path(abf_file).name}: {len(power_sequence)} labelled powers for {len(amplitude_v)} detected trains."
        )
    correlation = spearmanr(power_sequence, amplitude_v).statistic
    if correlation < _MIN_POWER_AMPLITUDE_CORRELATION:
        raise ValueError(
            f"{Path(abf_file).name}: the labelled power sequence does not follow the opto_TTL amplitude "
            f"(Spearman correlation {correlation:.2f}). Check the stimulation sequence of this session."
        )


def convert_session(
    file_path: str | Path,
    nwb_folder_path: str | Path,
    subject_id: str,
    group: Literal["Anxa", "Calb"] = "Anxa",
    genotype: Literal["WT", "GS"] = "WT",
    sex: str = "U",
    date_of_birth: datetime | None = None,
    power_sequence: list[float] | None = None,
    mat_file: str | Path | None = None,
    stub_test: bool = False,
) -> None:
    """Convert one ABF (and optionally its *_data.mat) recording to NWB.

    Parameters
    ----------
    file_path : str | Path
        Path to the raw .abf file.
    nwb_folder_path : str | Path
        Destination folder for the .nwb file.
    subject_id : str
        Animal identifier (e.g. "302").
    group : Literal["Anxa", "Calb"], default "Anxa"
        Experimental group: "Anxa" or "Calb".
    genotype : Literal["WT", "GS"], default "WT"
        Genotype: "WT" or "GS" (LRRK2-G2019S).
    sex : str, default "U"
        Subject sex: "M", "F", or "U".
    date_of_birth : datetime | None
        Subject date of birth (timezone-aware). Written as ``Subject.date_of_birth``.
    power_sequence : list[float] | None
        Per-epoch stimulation powers in mW, one entry per TTL epoch in the session.
        If None the power field in the epochs table is left as NaN.
    mat_file : str | Path | None
        Path to the *_data.mat file. When provided the four processed
        fluorescence series (corrected470/405, dff470/405) are also written.
    stub_test : bool
        If True write only the first 100 samples (for CI / smoke tests).
    """

    metadata_keys = GROUP_TO_METADATA_KEYS[group]
    genotype_label = GENOTYPE_LABELS[genotype]

    nwb_folder_path = Path(nwb_folder_path)
    if stub_test:
        nwb_folder_path = nwb_folder_path / "stub"
    nwb_folder_path.mkdir(parents=True, exist_ok=True)

    # e.g. 2025-01-24-0002
    session_id = Path(file_path).stem.replace("_", "-")
    # e.g. 4007-anxa-wt
    subject_id += f"-{group.lower()}-{genotype.lower()}"
    nwbfile_path = nwb_folder_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    # Raw interfaces — always present
    source_data: dict = {
        "RawSignal": {
            "file_path": str(file_path),
            "stream_names": ["470nm"],
            "metadata_key": metadata_keys["RawSignal"],
        },
        "IsosbesticControl": {
            "file_path": str(file_path),
            "stream_names": ["405nm"],
            "metadata_key": metadata_keys["IsosbesticControl"],
        },
        "RawTreadmill": {
            "file_path": str(file_path),
        },
        "RawTriggers": {
            "file_path": str(file_path),
        },
    }

    # Processed + optogenetics interfaces — present only when mat_file is provided
    if mat_file is not None:
        mat_file = str(mat_file)
        source_data.update(
            {
                "CorrectedSignal": {
                    "file_path": mat_file,
                    "stream_names": ["corrected470"],
                    "metadata_key": metadata_keys["CorrectedSignal"],
                },
                "CorrectedIsosbestic": {
                    "file_path": mat_file,
                    "stream_names": ["corrected405"],
                    "metadata_key": metadata_keys["CorrectedIsosbestic"],
                },
                "DfOverF": {
                    "file_path": mat_file,
                    "stream_names": ["dff470"],
                    "metadata_key": metadata_keys["DfOverF"],
                },
                "DfOverFIsosbestic": {
                    "file_path": mat_file,
                    "stream_names": ["dff405"],
                    "metadata_key": metadata_keys["DfOverFIsosbestic"],
                },
                "Behavior": {
                    "file_path": mat_file,
                },
                "Optogenetics": {
                    "file_path": mat_file,
                },
            }
        )

    converter = Chen2026NWBConverter(source_data=source_data)
    metadata = converter.get_metadata()

    fp_metadata = load_dict_from_file(METADATA_DIR / "fiber_photometry.yaml")
    fp_metadata = _select_recording_site(fp_metadata, group)
    metadata = dict_deep_update(metadata, fp_metadata)

    if mat_file is not None:
        opto_metadata = load_dict_from_file(METADATA_DIR / "optogenetics.yaml")
        metadata = dict_deep_update(metadata, opto_metadata)

    # NWBFile: static fields from YAML + dynamic per-session fields
    general_metadata = load_dict_from_file(METADATA_DIR / "general_metadata.yaml")
    nwbfile_meta = general_metadata["NWBFile"].copy()
    nwbfile_meta["session_description"] = general_metadata["SessionDescriptions"][group].format(
        genotype_label=genotype_label
    )
    nwbfile_meta["session_id"] = session_id
    metadata = dict_deep_update(metadata, {"NWBFile": nwbfile_meta})

    # Subject: static fields from YAML + dynamic per-animal fields
    subject_meta = general_metadata["Subject"].copy()
    subject_meta["subject_id"] = subject_id
    subject_meta["genotype"] = genotype_label
    subject_meta["sex"] = sex
    if date_of_birth is not None:
        subject_meta["date_of_birth"] = date_of_birth
    subject_meta["description"] = general_metadata["SubjectDescriptions"][group]
    metadata["Subject"] = subject_meta

    conversion_options: dict = {
        "RawSignal": {"stub_test": stub_test},
        "IsosbesticControl": {"stub_test": stub_test},
        "RawTreadmill": {},
        "RawTriggers": {},
    }
    if mat_file is not None:
        pulse_length_ms, period_ms, n_pulses, amplitude_v = _detect_opto_pulse_params(file_path)
        n_epochs = len(pulse_length_ms)
        if power_sequence is not None:
            _check_power_sequence(power_sequence, amplitude_v, file_path)
        conversion_options.update(
            {
                "CorrectedSignal": {"stub_test": stub_test},
                "CorrectedIsosbestic": {"stub_test": stub_test},
                "DfOverF": {"stub_test": stub_test},
                "DfOverFIsosbestic": {"stub_test": stub_test},
                "Behavior": {"stub_test": stub_test},
                "Optogenetics": {
                    "stub_test": stub_test,
                    "pulse_length_in_ms": pulse_length_ms,
                    "period_in_ms": period_ms,
                    "number_pulses_per_pulse_train": n_pulses,
                    "number_trains": 1,
                    "power_in_mW": power_sequence if power_sequence is not None else [float("nan")] * n_epochs,
                },
            }
        )

    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    print(f"Saved: {nwbfile_path}")


if __name__ == "__main__":
    from datetime import timezone

    # --- Edit these paths and parameters before running ---
    abf_file = Path("/Users/weian/lrrk2_data/Anxa-LRRK2/2025_08_13_0005.abf")
    mat_file = Path("/Users/weian/lrrk2_data/Anxa-LRRK2/4007/4007_data.mat")  # set to None to skip processed
    output_path = Path("/Users/weian/lrrk2_data/nwb-output")
    animal_id = "4007"
    group = "Anxa"  # "Anxa" or "Calb"
    genotype = "GS"  # "WT" or "GS"
    stub_test = False
    # Per-animal metadata from metadata-LRRK2-chen2026.xlsx
    subject_sex = "M"
    subject_dob = datetime(2025, 1, 13, tzinfo=timezone.utc)
    # Power sequence A from stimulation sequence LRRK2.xlsx (stim_sequence = 'a')
    subject_power_sequence = [
        2.0,
        2.0,
        3.0,
        3.0,
        0.25,
        0.25,
        1.5,
        1.5,
        2.0,
        2.0,
        3.0,
        3.0,
        0.25,
        0.25,
        1.5,
        1.5,
        2.0,
        2.0,
        3.0,
        3.0,
        0.25,
        0.25,
        1.5,
        1.5,
        2.0,
        2.0,
        3.0,
        3.0,
        0.25,
        0.25,
        1.5,
        1.5,
        1.0,
        1.0,
        0.1,
        0.1,
        0.5,
        0.5,
        4.0,
        4.0,
        1.0,
        1.0,
        0.1,
        0.1,
        0.5,
        0.5,
        4.0,
        4.0,
        1.0,
        1.0,
        0.1,
        0.1,
        0.5,
        0.5,
        4.0,
        4.0,
        1.0,
        1.0,
        0.1,
        0.1,
        0.5,
        0.5,
        4.0,
        4.0,
    ]
    # ------------------------------------------------------

    convert_session(
        file_path=abf_file,
        mat_file=mat_file,
        nwb_folder_path=output_path,
        subject_id=animal_id,
        group=group,
        genotype=genotype,
        sex=subject_sex,
        date_of_birth=subject_dob,
        power_sequence=subject_power_sequence,
        stub_test=stub_test,
    )
