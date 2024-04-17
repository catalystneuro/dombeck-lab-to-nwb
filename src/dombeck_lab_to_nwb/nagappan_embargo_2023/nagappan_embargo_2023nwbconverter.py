"""Primary NWBConverter class for this dataset."""
from pathlib import Path

from natsort import natsorted
from neuroconv import NWBConverter
from neuroconv.datainterfaces import ScanImageSinglePlaneMultiFileImagingInterface, Suite2pSegmentationInterface
from neuroconv.utils import FolderPathType


class NagappanEmbargo2023NWBConverter(NWBConverter):
    """Primary conversion class for the Two Photon experiment from Shiva Nagappan."""

    def __init__(
        self,
        folder_path: FolderPathType,
        file_pattern: str,
        suite2p_folder_path: FolderPathType,
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
            self.data_interface_objects[interface_name] = ScanImageSinglePlaneMultiFileImagingInterface(
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
