"""Primary script to run to convert an entire session for of data using the NWBConverter."""
from pathlib import Path
from typing import Union

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update

from dombeck_lab_to_nwb.azcorra2023 import Azcorra2023NWBConverter


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

    channel_id_to_time_series_name_mapping = dict(
        A="Velocity",
        B="FluorescenceRed",
        C="FluorescenceGreen",
    )
    conversion_options.update(
        dict(
            PicoScopeTimeSeries=dict(
                channel_id_to_time_series_name_mapping=channel_id_to_time_series_name_mapping,
                stub_test=stub_test,
            ),
            Events=dict(stub_test=stub_test),
        )
    )

    # Add binned photometry data
    session_id = ("-").join(picoscope_folder_path.parts[-2:])
    channel_name_mapping = dict(
        chGreen="FiberPhotometryResponseSeriesGreen",
        chGreen405="FiberPhotometryResponseSeriesGreenIsosbestic",
        chRed="FiberPhotometryResponseSeriesRed",
        chRed405="FiberPhotometryResponseSeriesRedIsosbestic",
    )
    source_data.update(
        dict(FiberPhotometry=dict(file_path=str(binned_photometry_mat_file_path), session_id=session_id))
    )
    conversion_options.update(
        dict(
            FiberPhotometry=dict(
                channel_name_to_photometry_series_name_mapping=channel_name_mapping,
                stub_test=stub_test,
            )
        )
    )

    # Add processed photometry data
    source_data.update(dict(ProcessedFiberPhotometry=dict(file_path=str(processed_photometry_mat_file_path))))
    dff_channel_name_mapping = dict(
        chGreen="DfOverFFiberPhotometryResponseSeriesGreen",
        chGreen405="DfOverFFiberPhotometryResponseSeriesGreenIsosbestic",
        chRed="DfOverFFiberPhotometryResponseSeriesRed",
        chRed405="DfOverFFiberPhotometryResponseSeriesRedIsosbestic",
    )
    conversion_options.update(
        dict(
            ProcessedFiberPhotometry=dict(
                channel_name_to_photometry_series_name_mapping=dff_channel_name_mapping,
                stub_test=stub_test,
            )
        )
    )

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
    picoscope_folder_path = data_folder_path / "20200205-0001"

    # The path to the .mat file containing the binned photometry data.
    binned_photometry_mat_file_path = data_folder_path / "T_Binned405_VGlut-A997-20200205.mat"

    # The path to the .mat file containing the processed photometry data.
    processed_photometry_mat_file_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/tmp/VGlut-A997-20200205-0001.mat")

    # The path to the NWB file to be created.
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/20200205-0001.nwb")
    stub_test = False

    session_to_nwb(
        picoscope_folder_path=picoscope_folder_path,
        binned_photometry_mat_file_path=binned_photometry_mat_file_path,
        processed_photometry_mat_file_path=processed_photometry_mat_file_path,
        nwbfile_path=nwbfile_path,
        stub_test=stub_test,
    )
