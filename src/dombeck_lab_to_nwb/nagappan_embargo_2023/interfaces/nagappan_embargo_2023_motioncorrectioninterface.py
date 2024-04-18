from pathlib import Path
from typing import Union

from neuroconv import BaseDataInterface
from neuroconv.tools.roiextractors.imagingextractordatachunkiterator import ImagingExtractorDataChunkIterator
from pynwb import NWBFile
from roiextractors import TiffImagingExtractor

from dombeck_lab_to_nwb.nagappan_embargo_2023.utils import get_xy_shifts, add_motion_correction


class NagappanEmbargo2023MotionCorrectionInterface(BaseDataInterface):
    """Data interface for adding the motion corrected image data."""

    display_name = "NagappanEmbargo2023MotionCorrection"
    associated_suffixes = (".tif", ".mat")
    info = "Custom interface for motion corrected imaging data."

    def __init__(
        self,
        file_path: Union[str, Path],
        xy_shifts_file_path: Union[str, Path],
        verbose: bool = True,
    ):
        """
        Interface for motion corrected imaging data.

        Parameters
        ----------
        file_path : Union[str, Path]
            The path to the motion corrected imaging data (.tif file).
        xy_shifts_file_path : Union[str, Path]
            The path to the xy shifts file (.mat file).
        """
        super().__init__(file_path=file_path, xy_shifts_file_path=xy_shifts_file_path, verbose=verbose)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        sampling_frequency: float = None,
        corrected_image_stack_name: str = "CorrectedImageStack",
        stub_test: bool = False,
    ) -> None:

        xy_shifts = get_xy_shifts(self.source_data["xy_shifts_file_path"])
        # Sampling frequency is required for the extractor, but we will write with the timestamps from the original data
        imaging_extractor = TiffImagingExtractor(
            file_path=self.source_data["file_path"], sampling_frequency=sampling_frequency
        )
        corrected = (
            imaging_extractor.get_video(end_frame=100)
            if stub_test
            else ImagingExtractorDataChunkIterator(
                imaging_extractor=imaging_extractor,
            )
        )
        add_motion_correction(
            nwbfile=nwbfile,
            corrected=corrected,
            xy_shifts=xy_shifts[:100, :] if stub_test else xy_shifts,
            corrected_image_stack_name=corrected_image_stack_name,
        )
