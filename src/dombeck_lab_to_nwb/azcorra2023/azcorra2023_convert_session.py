"""Primary script to run to convert an entire session for of data using the NWBConverter."""
from pathlib import Path
from typing import Union, Optional

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update
from nwbinspector import inspect_nwbfile
from pymatreader import read_mat

from dombeck_lab_to_nwb.azcorra2023 import Azcorra2023NWBConverter
from dombeck_lab_to_nwb.azcorra2023.photometry_utils import process_extra_metadata


def session_to_nwb(
    picoscope_folder_path: Union[str, Path],
    processed_photometry_mat_file_path: Union[str, Path],
    allen_location_mapping: dict,
    nwbfile_path: Union[str, Path],
    binned_photometry_mat_file_path: Optional[Union[str, Path]] = None,
    stub_test: bool = False,
):
    """
    Convert a session of data to NWB format.

    Parameters
    ----------
    picoscope_folder_path : Union[str, Path]
        The folder containing the Picoscope data (.mat files).
    processed_photometry_mat_file_path : Union[str, Path]
        The path to the .mat file containing the processed photometry data.
    nwbfile_path : Union[str, Path]
        The path to the NWB file to be created.
    binned_photometry_mat_file_path : Union[str, Path], optional
        The path to the .mat file containing the binned photometry data.
    stub_test : bool, optional
        Whether to run a stub test, by default False.

    """
    picoscope_folder_path = Path(picoscope_folder_path)
    nwbfile_path = Path(nwbfile_path)

    # e.g. '20200129-0001'
    session_id = picoscope_folder_path.parts[-1]
    # e.g. 'VGlut-A997'
    subject_id = picoscope_folder_path.parts[-2]

    source_data = dict()
    conversion_options = dict()

    # Add Picoscope data
    source_data.update(
        dict(
            PicoScopeTimeSeries=dict(
                folder_path=str(picoscope_folder_path),
                file_pattern=f"{picoscope_folder_path.stem.split('-')[0]}*.mat",
            ),
            PicoScopeEvents=dict(folder_path=str(picoscope_folder_path)),
        )
    )

    # Add binned photometry data
    if binned_photometry_mat_file_path:
        # Check that file can be read in Python
        binned = read_mat(binned_photometry_mat_file_path)
        if "#subsystem#" not in binned:
            raise ValueError(
                f"Could not read {binned_photometry_mat_file_path} with pymatreader."
                f"The file should be resaved in MATLAB with '-v7.3' option."
            )

        source_data.update(
            dict(FiberPhotometry=dict(file_path=str(binned_photometry_mat_file_path), session_id=session_id))
        )

    # Add processed photometry data
    source_data.update(dict(ProcessedFiberPhotometry=dict(file_path=str(processed_photometry_mat_file_path))))

    converter = Azcorra2023NWBConverter(source_data=source_data, verbose=False)

    # Add datetime to conversion
    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    tzinfo = tz.gettz("US/Central")
    metadata["NWBFile"].update(
        session_start_time=session_start_time.replace(tzinfo=tzinfo),
        session_id=session_id,
    )

    # Update default metadata with the editable in the corresponding yaml file
    editable_metadata_path = Path(__file__).parent / "metadata" / "azcorra2023_nwbfile_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    subjects_metadata_path = Path(__file__).parent / "metadata" / "azcorra2023_subjects_metadata.yaml"
    subjects_metadata = load_dict_from_file(subjects_metadata_path)
    subject_type = processed_photometry_mat_file_path.stem.split("-")[0]
    subject_metadata = subjects_metadata["Subjects"][subject_type]
    subject_metadata["subject_id"] = subject_id
    virus_metadata = subject_metadata.pop("virus")
    metadata["Subject"].update(**subject_metadata)
    metadata["NWBFile"].update(virus=virus_metadata)

    fiber_photometry_metadata = load_dict_from_file(
        Path(__file__).parent / "metadata" / "azcorra2023_fiber_photometry_metadata.yaml"
    )
    metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    extra_metadata = process_extra_metadata(
        file_path=processed_photometry_mat_file_path,
        metadata=metadata,
        allen_location_mapping=allen_location_mapping,
    )

    # Determine whether single or multi-fiber experiment and adjust conversion options accordingly
    fibers_metadata = extra_metadata["Ophys"]["FiberPhotometry"]["OpticalFibers"]
    trace_name_to_channel_id_mapping = dict(
        FiberPhotometryResponseSeries=[],
        FiberPhotometryResponseSeriesIsosbestic=[],
    )
    time_series_name_to_channel_id_mapping = dict(Velocity=["A"], Fluorescence=[])
    for fiber_metadata in fibers_metadata:
        fiber_name = fiber_metadata["name"]
        channel_name = fiber_metadata.pop("label")
        isosbestic_channel_name = f"{channel_name}405"

        trace_name_to_channel_id_mapping["FiberPhotometryResponseSeries"].append(channel_name)
        trace_name_to_channel_id_mapping["FiberPhotometryResponseSeriesIsosbestic"].append(isosbestic_channel_name)

        picoscope_channel_name = "C" if fiber_name == "Fiber1" else "B"
        time_series_name_to_channel_id_mapping["Fluorescence"].append(picoscope_channel_name)

    if binned_photometry_mat_file_path:
        conversion_options.update(
            dict(
                FiberPhotometry=dict(
                    trace_name_to_channel_id_mapping=trace_name_to_channel_id_mapping,
                    stub_test=stub_test,
                ),
            ),
        )

    dff_channel_name_mapping = {
        f"DfOverF{series_name}": channel_names
        for series_name, channel_names in trace_name_to_channel_id_mapping.items()
    }

    # Update conversion options
    conversion_options.update(
        dict(
            ProcessedFiberPhotometry=dict(
                trace_name_to_channel_id_mapping=dff_channel_name_mapping,
                stub_test=stub_test,
            ),
            PicoScopeTimeSeries=dict(
                time_series_name_to_channel_id_mapping=time_series_name_to_channel_id_mapping,
                stub_test=stub_test,
            ),
            PicoScopeEvents=dict(stub_test=stub_test),
        )
    )

    # Run conversion
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=extra_metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )

    results = list(inspect_nwbfile(nwbfile_path=nwbfile_path))

    return results


if __name__ == "__main__":

    # Parameters for conversion
    data_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/Azcorra2023/2020-02-26 Vglut2/VGlut-A997")
    # The folder containing the Picoscope output (.mat files) for a single session of data.
    picoscope_folder_path = data_folder_path / "20200205-0001"
    # The path to the .mat file containing the binned photometry data. (optional)
    binned_photometry_mat_file_path = data_folder_path / "Binned405_VGlut-A997-20200205.mat"

    # The path to the .mat file containing the processed photometry data.
    processed_photometry_mat_file_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/tmp2/VGlut-A997-20200205-0001.mat")

    # Mapping of the location names in the processed photometry data to the Allen Brain Atlas location names.
    location_name_mapping = dict(
        dls="DLS",
        dms="DMS",
        ds="DS",
        snc="SNc",
        ts="TS",
    )
    # The path to the NWB file to be created.
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/20200205-0001.nwb")

    stub_test = True

    session_to_nwb(
        picoscope_folder_path=picoscope_folder_path,
        binned_photometry_mat_file_path=binned_photometry_mat_file_path,
        processed_photometry_mat_file_path=processed_photometry_mat_file_path,
        allen_location_mapping=location_name_mapping,
        nwbfile_path=nwbfile_path,
        stub_test=stub_test,
    )
