"""Primary NWBConverter class for this dataset."""
from pathlib import Path

from natsort import natsorted
from neuroconv import NWBConverter
from neuroconv.datainterfaces import ScanImageSinglePlaneMultiFileImagingInterface
from neuroconv.utils import FolderPathType


class NagappanEmbargo2023NWBConverter(NWBConverter):
    """Primary conversion class for the Two Photon experiment from Shiva Nagappan."""

    def __init__(
        self,
        folder_path: FolderPathType,
        file_pattern: str,
        verbose: bool = False,
    ):
        from roiextractors import ScanImageTiffSinglePlaneImagingExtractor

        self.verbose = verbose
        self.data_interface_objects = dict()

        file_paths = natsorted(Path(folder_path).glob(file_pattern))
        first_file_path = file_paths[0]
        available_channels = ScanImageTiffSinglePlaneImagingExtractor.get_available_channels(file_path=first_file_path)

        for channel_name in available_channels:
            interface_name = f"Imaging{channel_name}"
            self.data_interface_objects[interface_name] = ScanImageSinglePlaneMultiFileImagingInterface(
                folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=verbose
            )
