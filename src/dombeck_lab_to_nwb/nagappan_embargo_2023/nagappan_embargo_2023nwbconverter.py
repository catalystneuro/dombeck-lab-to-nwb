"""Primary NWBConverter class for this dataset."""
from pathlib import Path
from typing import Optional, Union

from natsort import natsorted
from pynwb import NWBFile
from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    ScanImageMultiFileImagingInterface,
    Suite2pSegmentationInterface,
    DeepLabCutInterface,
    VideoInterface,
)
from neuroconv.tools.nwb_helpers import get_default_backend_configuration, configure_backend
from neuroconv.utils import FolderPathType, FilePathType

from dombeck_lab_to_nwb.nagappan_embargo_2023.interfaces import (
    NagappanEmbargoBehaviorInterface,
    NagappanEmbargo2023MotionCorrectionInterface,
)


class NagappanEmbargo2023NWBConverter(NWBConverter):
    """Primary conversion class for the Two Photon experiment from Shiva Nagappan."""

    def __init__(
        self,
        folder_path: FolderPathType,
        file_pattern: str,
        suite2p_folder_path: FolderPathType,
        dlc_file_path: FilePathType,
        dlc_config_file_path: FilePathType,
        events_dat_file_path: FilePathType,
        events_mat_file_path: FilePathType,
        daq_dat_file_path: FilePathType,
        behavior_movie_file_path: Optional[FilePathType] = None,
        channel_1_motion_correction_file_path: Optional[Union[str, Path]] = None,
        channel_2_motion_correction_file_path: Optional[Union[str, Path]] = None,
        verbose: bool = False,
    ):
        from roiextractors import ScanImageTiffSinglePlaneImagingExtractor

        self.verbose = verbose
        self.data_interface_objects = dict()

        folder_path = Path(folder_path)
        file_paths = natsorted(folder_path.glob(file_pattern))
        first_file_path = file_paths[0]
        available_channels = ScanImageTiffSinglePlaneImagingExtractor.get_available_channels(file_path=first_file_path)

        for channel_name in available_channels:
            channel_name_without_spaces = channel_name.replace(" ", "")
            interface_name = f"Imaging{channel_name_without_spaces}"
            self.data_interface_objects[interface_name] = ScanImageMultiFileImagingInterface(
                folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=verbose
            )

        # Add Suite2p segmentation for Channel 1
        self.data_interface_objects["SegmentationChannel1"] = Suite2pSegmentationInterface(
            folder_path=suite2p_folder_path,
            channel_name="chan1",
            plane_name="plane0",
            verbose=verbose,
            plane_segmentation_name="PlaneSegmentationChannel1",
        )

        # Add motion correction
        if channel_1_motion_correction_file_path:
            xy_shifts_file_name = Path(channel_1_motion_correction_file_path).stem + "_shifts.mat"
            xy_shifts_file_path = channel_1_motion_correction_file_path.parent / xy_shifts_file_name
            assert xy_shifts_file_path.exists(), f"The xy shifts file '{xy_shifts_file_path}' does not exist."
            self.data_interface_objects["MotionCorrectionChannel1"] = NagappanEmbargo2023MotionCorrectionInterface(
                file_path=channel_1_motion_correction_file_path,
                xy_shifts_file_path=xy_shifts_file_path,
                verbose=verbose,
            )

        if channel_2_motion_correction_file_path:
            xy_shifts_file_name = Path(channel_2_motion_correction_file_path).stem + "_shifts.mat"
            xy_shifts_file_path = channel_2_motion_correction_file_path.parent / xy_shifts_file_name
            assert xy_shifts_file_path.exists(), f"The xy shifts file '{xy_shifts_file_path}' does not exist."
            self.data_interface_objects["MotionCorrectionChannel2"] = NagappanEmbargo2023MotionCorrectionInterface(
                file_path=channel_2_motion_correction_file_path,
                xy_shifts_file_path=xy_shifts_file_path,
                verbose=verbose,
            )

        self.data_interface_objects["Events"] = NagappanEmbargoBehaviorInterface(
            dat_file_path=events_dat_file_path,
            daq_dat_file_path=daq_dat_file_path,
            mat_file_path=events_mat_file_path,
            verbose=verbose,
        )

        self.data_interface_objects["DLC"] = DeepLabCutInterface(
            file_path=dlc_file_path,
            config_file_path=dlc_config_file_path,
            verbose=verbose,
        )

        if behavior_movie_file_path:
            self.data_interface_objects["BehaviorMovie"] = VideoInterface(
                file_paths=[behavior_movie_file_path],
                verbose=verbose,
            )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:

        if "MotionCorrectionChannel1" in conversion_options:
            conversion_options["MotionCorrectionChannel1"].update(
                corrected_image_stack_name="CorrectedImageStackChannel1",
                sampling_frequency=30.0421,
            )
        if "MotionCorrectionChannel2" in conversion_options:
            conversion_options["MotionCorrectionChannel2"].update(
                corrected_image_stack_name="CorrectedImageStackChannel2",
                sampling_frequency=30.0421,
            )

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    def temporally_align_data_interfaces(self):
        """Temporally align the data interfaces."""

        aligned_imaging_times, aligned_camera_times = self.data_interface_objects["Events"].get_aligned_times_from_ttl()

        imaging_interfaces = [interface for interface in self.data_interface_objects.keys() if "Imaging" in interface]
        for interface_name in imaging_interfaces:
            imaging_interface = self.data_interface_objects[interface_name]
            imaging_interface.set_aligned_timestamps(aligned_timestamps=aligned_imaging_times)

        first_camera_pulse_time = aligned_camera_times[0]
        video_interface = self.data_interface_objects["BehaviorMovie"]
        video_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=[first_camera_pulse_time],
        )

        dlc_interface = self.data_interface_objects["DLC"]
        dlc_interface.set_aligned_timestamps(
            aligned_timestamps=aligned_camera_times[2:]
        )  # todo: fix temporary mismatch in shape
