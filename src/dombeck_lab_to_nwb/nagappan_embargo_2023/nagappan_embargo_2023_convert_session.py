"""Primary script to run to convert an entire session for of data using the NWBConverter."""
from pathlib import Path
from typing import Union, Optional

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update

from dombeck_lab_to_nwb.nagappan_embargo_2023 import NagappanEmbargo2023NWBConverter
from dombeck_lab_to_nwb.nagappan_embargo_2023.utils import convert_tiff_to_avi


def session_to_nwb(
    scanimage_folder_path: Union[str, Path],
    scanimage_file_pattern: str,
    suite2p_folder_path: Union[str, Path],
    dlc_file_path: Union[str, Path],
    dlc_config_file_path: Union[str, Path],
    events_dat_file_path: Union[str, Path],
    events_mat_file_path: Union[str, Path],
    daq_dat_file_path: Union[str, Path],
    nwbfile_path: Union[str, Path],
    channel_1_motion_correction_file_path: Optional[Union[str, Path]] = None,
    channel_2_motion_correction_file_path: Optional[Union[str, Path]] = None,
    tiff_movie_folder_path: Optional[Union[str, Path]] = None,
    tiff_movie_frame_rate: Optional[int] = None,
    stub_test: bool = False,
):
    """
    Convert a session of data to NWB format.

    Parameters
    ----------
    scanimage_folder_path : Union[str, Path]
        The folder containing the ScanImage data (.tif files).
    scanimage_file_pattern : str
        The file pattern to match the ScanImage files.
    suite2p_folder_path : Union[str, Path]
        The folder containing the Suite2p output.
    nwbfile_path : Union[str, Path]
        The path to the NWB file to be created.
    channel_1_motion_correction_file_path : Union[str, Path], optional
        The path to the motion corrected imaging data for channel 1 (.tif file), by default None.
    channel_2_motion_correction_file_path : Union[str, Path], optional
        The path to the motion corrected imaging data for channel 2 (.tif file), by default None.
    stub_test : bool, optional
        Whether to run a stub test, by default False.

    """
    scanimage_folder_path = Path(scanimage_folder_path)

    session_identifier = scanimage_folder_path.parent.name
    avi_file_path = None
    if tiff_movie_folder_path is not None:
        avi_file_name = f"{session_identifier}.avi"
        avi_file_path = Path(tiff_movie_folder_path) / avi_file_name
        if tiff_movie_frame_rate is None:
            raise ValueError(
                "The frame rate of the tiff movie ('tiff_movie_frame_rate') must be specified if 'tiff_movie_folder_path' is provided."
            )
        if not avi_file_path.exists():
            print(f"Converting tiff files to avi file: {avi_file_name}")
            convert_tiff_to_avi(
                folder_path=tiff_movie_folder_path,
                file_pattern=f"{session_identifier}_%d.tif",
                frame_rate=tiff_movie_frame_rate,
                avi_file_name=avi_file_name,
            )

    nwbfile_path = Path(nwbfile_path)

    converter = NagappanEmbargo2023NWBConverter(
        folder_path=scanimage_folder_path,
        file_pattern=scanimage_file_pattern,
        suite2p_folder_path=suite2p_folder_path,
        channel_1_motion_correction_file_path=channel_1_motion_correction_file_path,
        channel_2_motion_correction_file_path=channel_2_motion_correction_file_path,
        dlc_file_path=dlc_file_path,
        dlc_config_file_path=dlc_config_file_path,
        behavior_movie_file_path=avi_file_path,
        events_dat_file_path=events_dat_file_path,
        events_mat_file_path=events_mat_file_path,
        daq_dat_file_path=daq_dat_file_path,
        verbose=True,
    )

    # Add conversion options
    conversion_options = {
        interface_name: dict(stub_test=stub_test)
        for interface_name in converter.data_interface_objects.keys()
        if interface_name != "DLC"
    }
    imaging_interfaces = [interface for interface in converter.data_interface_objects.keys() if "Imaging" in interface]
    for interface_ind, interface_name in enumerate(imaging_interfaces):
        conversion_options[interface_name].update(photon_series_index=interface_ind)

    # Add datetime to conversion
    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    tzinfo = tz.gettz("US/Central")
    metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))

    # Update default metadata with the editable in the corresponding yaml file
    editable_metadata_path = Path(__file__).parent / "nagappan_embargo_2023_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Add ophys metadata
    ophys_metadata_path = Path(__file__).parent / "metadata" / "nagappan_embargo_2023_ophys_metadata.yaml"
    ophys_metadata = load_dict_from_file(ophys_metadata_path)
    metadata = dict_deep_update(metadata, ophys_metadata)

    session_id = scanimage_folder_path.parent.name.replace("_", "-")
    metadata["NWBFile"].update(session_id=session_id)

    # Run conversion
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=True
    )

    # if avi_file_path is not None:
    #     # delete the avi file after conversion
    #     avi_file_path.unlink()


if __name__ == "__main__":

    # Parameters for conversion
    root_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/2620749R2_231211")

    # The folder containing the ScanImage data (.tif files).
    scanimage_folder_path = root_folder_path / "231211_data"
    scanimage_file_pattern = "2620749R2_231211_00001*.tif"

    # The folder containing the Suite2p output.
    suite2p_folder_path = root_folder_path / "suite2p"

    # The path to the motion corrected imaging data for channel 1 and channel 2.
    channel_1_motion_correction_file_path = root_folder_path / "2620749R2_231211_00001_ch1_mot_corrected_x2.tif"
    channel_2_motion_correction_file_path = root_folder_path / "2620749R2_231211_00001_ch2_mot_corrected_x2.tif"

    # DLC
    dlc_folder_path = root_folder_path / "DeepLabCut"
    dlc_file_path = dlc_folder_path / "2620749R2_231211DLC_resnet50_FrontPaw_fixedCamera_105FPSSep10shuffle1_500000.h5"
    dlc_config_file_path = dlc_folder_path / "config.yaml"

    # The folder containing the tiff movie files.
    tiff_movie_folder_path = root_folder_path / "tiff_movie"
    tiff_movie_frame_rate = 105

    # The path to the events files.
    events_mat_file_path = root_folder_path / "2620749R2_20231211_expLog3.mat"
    events_dat_file_path = root_folder_path / "2620749R2_20231211_expLog.dat"

    # The path to the daq file.
    daq_dat_file_path = root_folder_path / "2620749R2_20231211_expLog1.dat"

    # The path to the NWB file to be created.
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/2620749R2_231211.nwb")

    stub_test = True

    session_to_nwb(
        scanimage_folder_path=scanimage_folder_path,
        scanimage_file_pattern=scanimage_file_pattern,
        suite2p_folder_path=suite2p_folder_path,
        dlc_file_path=dlc_file_path,
        dlc_config_file_path=dlc_config_file_path,
        events_dat_file_path=events_dat_file_path,
        events_mat_file_path=events_mat_file_path,
        daq_dat_file_path=daq_dat_file_path,
        channel_1_motion_correction_file_path=channel_1_motion_correction_file_path,
        channel_2_motion_correction_file_path=channel_2_motion_correction_file_path,
        nwbfile_path=nwbfile_path,
        tiff_movie_folder_path=tiff_movie_folder_path,
        tiff_movie_frame_rate=tiff_movie_frame_rate,
        stub_test=stub_test,
    )
