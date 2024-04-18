from pathlib import Path
from typing import Union

from neuroconv.datainterfaces.ophys.baseimagingextractorinterface import BaseImagingExtractorInterface
from neuroconv.utils import DeepDict
from pynwb import NWBFile

from dombeck_lab_to_nwb.nagappan_embargo_2023.utils import get_xy_shifts, add_motion_correction


class NagappanEmbargo2023MotionCorrectionInterface(BaseImagingExtractorInterface):
    """Data interface for adding the motion corrected image data."""

    display_name = "NagappanEmbargo2023MotionCorrection"
    associated_suffixes = (".tif", ".mat")
    info = "Custom interface for motion corrected imaging data."

    ExtractorName = "TiffImagingExtractor"

    def __init__(
        self,
        file_path: Union[str, Path],
        xy_shifts_file_path: Union[str, Path],
        sampling_frequency: float,
        photon_series_name: str = "TwoPhotonSeriesCorrected",
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
        sampling_frequency : float
            The sampling frequency of the imaging data.
        photon_series_name : str, optional
            The name of the corrected photon series to add, by default "TwoPhotonSeriesCorrected".
        """
        self.xy_shifts_file_path = xy_shifts_file_path
        self.photon_series_name = photon_series_name
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def get_metadata(self) -> DeepDict:

        metadata = super().get_metadata()
        two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"][0]

        two_photon_series_metadata.update(
            name=f"{self.photon_series_name}", description="Motion corrected two-photon imaging data."
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        photon_series_index: int = 0,
        stub_test: bool = False,
    ) -> None:

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            parent_container="processing/ophys",
            photon_series_index=photon_series_index,
        )

        xy_translation = get_xy_shifts(self.xy_shifts_file_path)
        raw_two_photon_series_name = self.photon_series_name.replace("Corrected", "")
        add_motion_correction(
            nwbfile=nwbfile,
            xy_shifts=xy_translation,
            original_two_photon_series_name=raw_two_photon_series_name,
        )
