from datetime import datetime
from pathlib import Path

from natsort import natsorted
from neuroconv.datainterfaces.ecephys.baserecordingextractorinterface import BaseRecordingExtractorInterface
from neuroconv.utils import FolderPathType
from spikeinterface import ConcatenateSegmentRecording

from dombeck_lab_to_nwb.azcorra2023.extractors import PicoscopeRecordingExtractor


class PicoscopeRecordingInterface(BaseRecordingExtractorInterface):
    Extractor = ConcatenateSegmentRecording

    def __init__(
        self,
        folder_path: FolderPathType,
        verbose: bool = True,
        es_key: str = "ElectricalSeriesSync",
    ):
        """
        Load and prepare raw data and corresponding metadata from the Piscoscope (.mat files).

        Parameters
        ----------
        folder_path : FolderPathType
            The folder containing the .mat files from the Picoscope.
        verbose : bool, optional
            Allows for verbose output, by default True.
        es_key : str, optional
            The key to use for the ElectricalSeries, by default "ElectricalSeriesSync".
        """

        self.folder_path = Path(folder_path)
        session_name = self.folder_path.stem
        mat_files = natsorted(self.folder_path.glob(f"{session_name}_*.mat"))
        assert mat_files, f"The .mat files are missing from {folder_path}."

        recording_list = [PicoscopeRecordingExtractor(file_path=str(file_path)) for file_path in mat_files]

        super().__init__(recording_list=recording_list, verbose=verbose, es_key=es_key)

        custom_channel_names = [
            "chMov",
            "chRed",
            "chGreen",
            "Light",
            "ch470",
            "Reward",
            "Licking",
            "AirPuff",
        ]
        extractor_channel_ids = self.recording_extractor.get_channel_ids()
        self.recording_extractor.set_property(
            key="custom_channel_name", ids=extractor_channel_ids, values=custom_channel_names
        )

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
            description="The Picoscope 6 device used to record the data.",  # TODO update placeholder description
        )

        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"][0]
        electrode_group_metadata.update(
            description="The group of electrodes used to record the data.",  # TODO update placeholder description
            device=device_name,
        )

        ecephys_metadata[self.es_key].update(
            description="The acquisition traces from the Picoscope device acquired at 4000 Hz.",
        )

        return metadata
