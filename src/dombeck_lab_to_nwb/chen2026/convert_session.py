"""Convert a single Chen et al. 2026 session to NWB.

Edit the paths and parameters in the ``if __name__ == "__main__"`` block at the
bottom of this file, then run::

    python convert_session.py
"""

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

GENOTYPE_LABELS = {
    "WT": "LRRK2-WT",
    "GS": "LRRK2-G2019S",
}


def convert_session(
    file_path: str | Path,
    nwb_folder_path: str | Path,
    subject_id: str,
    group: Literal["Anxa", "Calb"] = "Anxa",
    genotype: Literal["WT", "GS"] = "WT",
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
    }

    # Processed interfaces — present only when mat_file is provided
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
            }
        )

    converter = Chen2026NWBConverter(source_data=source_data)
    metadata = converter.get_metadata()

    fp_metadata = load_dict_from_file(METADATA_DIR / "fiber_photometry.yaml")
    metadata = dict_deep_update(metadata, fp_metadata)

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
    subject_meta["description"] = general_metadata["SubjectDescriptions"][group]
    metadata["Subject"] = subject_meta

    conversion_options: dict = {
        "RawSignal": {"stub_test": stub_test},
        "IsosbesticControl": {"stub_test": stub_test},
    }
    if mat_file is not None:
        conversion_options.update(
            {
                "CorrectedSignal": {"stub_test": stub_test},
                "CorrectedIsosbestic": {"stub_test": stub_test},
                "DfOverF": {"stub_test": stub_test},
                "DfOverFIsosbestic": {"stub_test": stub_test},
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
    # --- Edit these paths and parameters before running ---
    abf_file = Path("/Users/weian/lrrk2_data/Anxa-LRRK2/2025_08_13_0005.abf")
    mat_file = Path("/Users/weian/lrrk2_data/Anxa-LRRK2/4007/4007_data.mat")  # set to None to skip processed
    output_path = Path("/Users/weian/lrrk2_data/nwb-output")
    animal_id = "4007"
    group = "Anxa"  # "Anxa" or "Calb"
    genotype = "GS"  # "WT" or "GS"
    stub_test = False
    # ------------------------------------------------------

    convert_session(
        file_path=abf_file,
        mat_file=mat_file,
        nwb_folder_path=output_path,
        subject_id=animal_id,
        group=group,
        genotype=genotype,
        stub_test=stub_test,
    )
