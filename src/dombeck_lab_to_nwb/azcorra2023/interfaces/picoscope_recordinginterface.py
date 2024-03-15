from datetime import datetime
from pathlib import Path
from typing import List, Optional

from natsort import natsorted
from neuroconv.datainterfaces.ecephys.baserecordingextractorinterface import BaseRecordingExtractorInterface
from neuroconv.utils import FolderPathType
from spikeinterface import ConcatenateSegmentRecording

from dombeck_lab_to_nwb.azcorra2023.extractors import PicoscopeRecordingExtractor


class PicoscopeRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting PicoScope signals.
    """

    display_name = "Picoscope Recording"
    associated_suffixes = ".mat"
    info = "Interface for PicoScope acquisition signals."

    Extractor = ConcatenateSegmentRecording

    def __init__(
        self,
        folder_path: FolderPathType,
        channel_name: str,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Load and prepare raw data and corresponding metadata from the Piscoscope (.mat files).

        Parameters
        ----------
        folder_path : FolderPathType
            The folder containing the .mat files from the Picoscope.
        channel_name: str
            The name of the channel to load from the MAT file.
        verbose : bool, optional
            Allows for verbose output, by default True.
        es_key : str, optional
            The key to use for the ElectricalSeries, by default "ElectricalSeries".
        """

        self.folder_path = Path(folder_path)
        session_name = self.folder_path.stem
        mat_files = natsorted(self.folder_path.glob(f"{session_name}_*.mat"))
        assert mat_files, f"The .mat files are missing from {folder_path}."

        recording_list = [
            PicoscopeRecordingExtractor(file_path=str(file_path), channel_name=channel_name) for file_path in mat_files
        ]

        super().__init__(recording_list=recording_list, verbose=verbose, es_key=es_key)

        extractor_channel_ids = self.recording_extractor.get_channel_ids()
        group_names = ["PicoscopeChannelGroup"] * len(extractor_channel_ids)
        self.recording_extractor.set_property(key="group_name", ids=extractor_channel_ids, values=group_names)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        # TODO: confirm whether there is a more precise session start time
        date_string = self.folder_path.name.split("-")[0]
        session_start_time = datetime.strptime(date_string, "%Y%m%d")
        metadata["NWBFile"].update(session_start_time=session_start_time)

        ecephys_metadata = metadata["Ecephys"]
        device_metadata = ecephys_metadata["Device"][0]
        device_name = "Picoscope"
        device_metadata.update(
            name=device_name,
            description="The Picoscope oscilloscope used to record the data.",
            manufacturer="Pico Technology",
        )

        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"][0]
        electrode_group_metadata.update(
            name="PicoscopeChannelGroup",
            description="The group of channels used to record the data.",
            device=device_name,
        )

        # Add electrodes and electrode groups
        ecephys_metadata.update(
            Electrodes=[
                dict(name="group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
            ]
        )

        return metadata
