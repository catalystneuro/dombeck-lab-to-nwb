"""Primary script to run to convert an entire session for of data using the NWBConverter."""
from copy import deepcopy
from pathlib import Path
from typing import Union

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update

from dombeck_lab_to_nwb.azcorra2023 import Azcorra2023NWBConverter
from dombeck_lab_to_nwb.azcorra2023.photometry_utils import process_extra_metadata


def session_to_nwb(
    picoscope_folder_path: Union[str, Path],
    binned_photometry_mat_file_path: Union[str, Path],
    processed_photometry_mat_file_path: Union[str, Path],
    nwbfile_path: Union[str, Path],
    stub_test: bool = False,
):
    """
    Convert a session of data to NWB format.

    Parameters
    ----------
    picoscope_folder_path : Union[str, Path]
        The folder containing the Picoscope data (.mat files).
    binned_photometry_mat_file_path : Union[str, Path]
        The path to the .mat file containing the binned photometry data.
    processed_photometry_mat_file_path : Union[str, Path]
        The path to the .mat file containing the processed photometry data.
    nwbfile_path : Union[str, Path]
        The path to the NWB file to be created.
    stub_test : bool, optional
        Whether to run a stub test, by default False.

    """
    picoscope_folder_path = Path(picoscope_folder_path)
    nwbfile_path = Path(nwbfile_path)

    source_data = dict()
    conversion_options = dict()

    # Add Picoscope data
    source_data.update(
        dict(
            PicoScopeTimeSeries=dict(
                folder_path=str(picoscope_folder_path),
                channel_ids=["A", "B", "C"],
            ),
            Events=dict(folder_path=str(picoscope_folder_path)),
        )
    )

    # Add binned photometry data
    session_id = ("-").join(picoscope_folder_path.parts[-2:])
    source_data.update(
        dict(FiberPhotometry=dict(file_path=str(binned_photometry_mat_file_path), session_id=session_id))
    )

    # Add processed photometry data
    source_data.update(dict(ProcessedFiberPhotometry=dict(file_path=str(processed_photometry_mat_file_path))))

    converter = Azcorra2023NWBConverter(source_data=source_data)

    # Add datetime to conversion
    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    tzinfo = tz.gettz("US/Central")
    metadata["NWBFile"].update(
        session_start_time=session_start_time.replace(tzinfo=tzinfo),
        session_id=session_id,
    )

    # Update default metadata with the editable in the corresponding yaml file
    editable_metadata_path = Path(__file__).parent / "azcorra2023_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    fiber_photometry_metadata = load_dict_from_file(
        Path(__file__).parent / "metadata" / "azcorra2023_fiber_photometry_metadata.yaml"
    )
    metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    extra_metadata = process_extra_metadata(file_path=processed_photometry_mat_file_path, metadata=metadata)
    metadata = dict_deep_update(metadata, extra_metadata)

    # Determine whether single or multi-fiber experiment and adjust conversion options accordingly
    fibers_metadata = metadata["Ophys"]["FiberPhotometry"]["Fibers"]
    num_fibers = len([fiber for fiber in fibers_metadata if "depth" in fiber])
    assert num_fibers in [1, 2], f"Number of fibers must be 1 or 2, but got {num_fibers} fibers metadata."

    channel_name_mapping = dict(
        chGreen="FiberPhotometryResponseSeriesGreen",
        chGreen405="FiberPhotometryResponseSeriesGreenIsosbestic",
    )
    channel_id_to_time_series_name_mapping = dict(A="Velocity", C="FluorescenceGreen")

    if num_fibers == 2:
        channel_name_mapping.update(
            dict(
                chRed="FiberPhotometryResponseSeriesRed",
                chRed405="FiberPhotometryResponseSeriesRedIsosbestic",
            )
        )
        channel_id_to_time_series_name_mapping.update(dict(B="FluorescenceRed"))

    dff_channel_name_mapping = {
        ch_name: "DfOverF" + series_name for ch_name, series_name in channel_name_mapping.items()
    }

    # Update conversion options
    conversion_options.update(
        dict(
            FiberPhotometry=dict(
                channel_name_to_photometry_series_name_mapping=channel_name_mapping,
                stub_test=stub_test,
            ),
            ProcessedFiberPhotometry=dict(
                channel_name_to_photometry_series_name_mapping=dff_channel_name_mapping,
                stub_test=stub_test,
            ),
            PicoScopeTimeSeries=dict(
                channel_id_to_time_series_name_mapping=channel_id_to_time_series_name_mapping,
                stub_test=stub_test,
            ),
            Events=dict(stub_test=stub_test),
        )
    )

    # Run conversion
    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )


if __name__ == "__main__":

    # Parameters for conversion
    data_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/2020-02-26 Vglut2/VGlut-A997")
    # The folder containing the Picoscope output (.mat files) for a single session of data.
    picoscope_folder_path = data_folder_path / "20200129-0002"

    # The path to the .mat file containing the binned photometry data.
    binned_photometry_mat_file_path = data_folder_path / "Binned405_VGlut-A997-20200129.mat"

    # The path to the .mat file containing the processed photometry data.
    processed_photometry_mat_file_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/tmp2/VGlut-A997-20200129-0002.mat")

    # The path to the NWB file to be created.
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/20200129-0002.nwb")

    stub_test = True

    session_to_nwb(
        picoscope_folder_path=picoscope_folder_path,
        binned_photometry_mat_file_path=binned_photometry_mat_file_path,
        processed_photometry_mat_file_path=processed_photometry_mat_file_path,
        nwbfile_path=nwbfile_path,
        stub_test=stub_test,
    )
