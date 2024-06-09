from collections import defaultdict
from pathlib import Path

from neuroconv.utils import FolderPathType
from nwbinspector.inspector_tools import save_report, format_messages
from tqdm import tqdm

from dombeck_lab_to_nwb.azcorra2023.azcorra2023_convert_session import session_to_nwb

import warnings

# Ignore all UserWarnings
warnings.filterwarnings("ignore", category=UserWarning)

# Ignore specific warning messages
warnings.filterwarnings("ignore", message="Complex objects (like classes) are not supported.")
warnings.filterwarnings(
    "ignore",
    message="The linked table for DynamicTableRegion 'event_type' does not share an ancestor with the DynamicTableRegion.",
)

# Ignore specific DtypeConversionWarnings
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Spec 'EventsTable/event_type': Value with data type uint8 is being converted to data type int32 as specified.",
)
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Spec 'TtlsTable/ttl_type': Value with data type uint8 is being converted to data type int32 as specified.",
)


def find_picoscope_sessions(folder_path: FolderPathType) -> dict:
    """
    Find all the fiber photometry sessions in the root folder path.

    Parameters
    ----------
    folder_path : Path
        The root folder path to search for fiber photometry sessions.

    Returns
    -------
    sessions_dict : dict
        A dictionary with the subject folder paths as keys and a list of session folder paths as values.
    """

    subject_folder_paths = [folder for folder in folder_path.iterdir() if folder.is_dir()]
    sessions_dict = defaultdict(list)
    for subject_folder_path in subject_folder_paths:
        for folder in subject_folder_path.iterdir():
            if folder.is_dir():
                for sub_folder in folder.iterdir():
                    if list(sub_folder.glob("*.mat")):
                        sessions_dict[subject_folder_path].append(sub_folder)

    return sessions_dict


def convert_all_sessions(
    folder_path: FolderPathType,
    processed_photometry_folder_path: FolderPathType,
    nwbfile_folder_path: FolderPathType,
    allen_location_mapping: dict,
    stub_test: bool = False,
    overwrite: bool = False,
):
    """
    Convert all the sessions in the folder path to NWB format.

    Parameters
    ----------
    folder_path : Path
        The root folder path to search for fiber photometry sessions.
    processed_photometry_folder_path : Path
        The folder containing the processed photometry data for each session.
    nwbfile_folder_path : Path
        The folder path to save the NWB files.
    allen_location_mapping : dict
        A mapping of the location names in the processed photometry data to the Allen Brain Atlas location names.
    stub_test : bool, optional
        Whether to run a stub test, by default False.
    overwrite : bool, optional
        Whether to overwrite existing NWB files, by default False.
    """
    all_sessions_inspector_results = []

    sessions_dict = find_picoscope_sessions(folder_path)
    total_file_paths = sum(len(paths) for paths in sessions_dict.values())

    progress_bar = tqdm(
        sessions_dict.items(),
        desc=f"Converting {total_file_paths} sessions",
        position=0,
        total=total_file_paths,
        dynamic_ncols=True,
    )

    for data_folder_path, picoscope_folder_paths in progress_bar:
        for picoscope_folder_path in picoscope_folder_paths:
            picoscope_folder_path = Path(picoscope_folder_path)
            # e.g. '20200129-0001'
            session_id = picoscope_folder_path.parts[-1]
            # e.g. 'VGlut-A997'
            subject_id = picoscope_folder_path.parts[-2]

            progress_bar.set_description(f"\nConverting session {session_id} of subject {subject_id}")

            # The path to the .mat file containing the processed photometry data.
            processed_photometry_mat_file_path = (
                Path(processed_photometry_folder_path) / f"{subject_id}-{session_id}.mat"
            )
            if not processed_photometry_mat_file_path.exists():
                print(
                    f"Skipping session {session_id} because the processed photometry file ({processed_photometry_mat_file_path}) does not exist."
                )
                continue

            # The path to the NWB file to be created.
            nwbfile_path = Path(nwbfile_folder_path) / f"{subject_id}-{session_id}.nwb"

            if nwbfile_path.exists() and not overwrite:
                progress_bar.update(1)
                continue

            # The path to the .mat file containing the binned photometry data.
            session_id_part = session_id.split("-")[0]
            binned_photometry_mat_file_paths = list(
                Path(picoscope_folder_path.parent).glob(f"Binned*{session_id_part}*.mat")
            )
            if len(binned_photometry_mat_file_paths) == 1:
                binned_photometry_mat_file_path = binned_photometry_mat_file_paths[0]
            else:
                binned_photometry_mat_file_path = None

            # Convert the session to NWB
            session_inspector_results = session_to_nwb(
                picoscope_folder_path=Path(picoscope_folder_path),
                binned_photometry_mat_file_path=binned_photometry_mat_file_path,
                processed_photometry_mat_file_path=processed_photometry_mat_file_path,
                allen_location_mapping=allen_location_mapping,
                nwbfile_path=nwbfile_path,
                stub_test=stub_test,
            )
            progress_bar.update(1)
            all_sessions_inspector_results.extend(session_inspector_results)

    report_path = nwbfile_folder_path / "inspector_result.txt"
    save_report(
        report_file_path=report_path,
        formatted_messages=format_messages(
            all_sessions_inspector_results,
            levels=["importance", "file_path"],
        ),
        overwrite=True,
    )


if __name__ == "__main__":

    # Parameters for conversion

    # The root folder path to search for fiber photometry sessions.
    root_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/Azcorra2023/")

    # The folder containing the processed photometry data for each session.
    # Use matlab_utils/convert_data6.m to convert the data6.mat files to .mat files expected by the converter.
    processed_photometry_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/tmp2/")

    # Mapping of the location names in the processed photometry data to the Allen Brain Atlas location names.
    location_name_mapping = dict(
        dls="DLS",
        dms="DMS",
        ds="DS",
        snc="SNc",
        ts="TS",
    )

    # The folder path to save the NWB files.
    nwbfile_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/Azcorra2023_nwbfiles/")
    if not nwbfile_folder_path.exists():
        nwbfile_folder_path.mkdir(parents=True)

    # Whether to run a stub test, by default False.
    stub_test = False
    # Whether to overwrite existing NWB files, by default False.
    overwrite = False

    convert_all_sessions(
        folder_path=root_folder_path,
        processed_photometry_folder_path=processed_photometry_folder_path,
        allen_location_mapping=location_name_mapping,
        nwbfile_folder_path=nwbfile_folder_path,
        stub_test=stub_test,
        overwrite=overwrite,
    )
