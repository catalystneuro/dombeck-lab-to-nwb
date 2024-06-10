from datetime import datetime
from pathlib import Path

import numpy as np
from natsort import natsorted
from neuroconv import BaseDataInterface
from neuroconv.utils import FolderPathType
from pynwb import NWBFile, TimeSeries
from spikeinterface import ConcatenateSegmentRecording

from dombeck_lab_to_nwb.azcorra2023.extractors import PicoscopeRecordingExtractor


class PicoscopeTimeSeriesInterface(BaseDataInterface):
    """
    Data interface class for converting PicoScope signals.
    """

    display_name = "Picoscope Time Series Interface"
    associated_suffixes = ".mat"
    info = "Interface for writing PicoScope acquisition signals as TimeSeries to NWB."

    def __init__(
        self,
        folder_path: FolderPathType,
        file_pattern: str,
        verbose: bool = True,
    ):
        """
        Load and prepare raw data and corresponding metadata from the Piscoscope (.mat files).

        Parameters
        ----------
        folder_path : FolderPathType
            The folder containing the .mat files from the Picoscope.
        channel_ids : list
            The channel ids to load from the .mat files.
        verbose : bool, optional
            Allows for verbose output, by default True.
        """

        self.folder_path = Path(folder_path)
        mat_files = natsorted(self.folder_path.glob(file_pattern))
        if not len(mat_files):
            raise ValueError(f"No .mat files found in {self.folder_path}")

        super().__init__(folder_path=folder_path, verbose=verbose)

        self.file_paths = mat_files

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        # TODO: confirm whether there is a more precise session start time
        date_string = self.folder_path.name.split("-")[0]
        session_start_time = datetime.strptime(date_string, "%Y%m%d")
        metadata["NWBFile"].update(session_start_time=session_start_time)

        metadata["PicoScopeTimeSeries"] = dict(
            Fluorescence=dict(
                name="Fluorescence",
                description="The fluorescence traces from one or two optical fibers during 405 nm and 470 nm illumination collected at 4000 Hz by Picoscope.",
                unit="Volts",
            ),
            Velocity=dict(
                name="Velocity",
                description="Velocity from rotary encoder collected at 4000 Hz by Picoscope.",
                unit="Volts",
            ),
        )

        return metadata

    def get_trace_extractor_from_picoscope(self, channel_name: str):
        recording_list = [
            PicoscopeRecordingExtractor(file_path=str(file_path), channel_name=channel_name)
            for file_path in self.file_paths
        ]
        return ConcatenateSegmentRecording(recording_list=recording_list)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        time_series_name_to_channel_id_mapping: dict,
        stub_test: bool = False,
    ) -> None:
        """
        Add the Picoscope traces as TimeSeries to the NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to which to add the Picoscope time series.
        metadata : dict
            The metadata for the Picoscope time series.
        time_series_name_to_channel_id_mapping : dict
            A mapping from the time series name to the channel id(s).
        stub_test : bool, optional
            Whether to run a stub test, by default False.
        """

        picoscope_time_series_metadata = metadata["PicoScopeTimeSeries"]

        end_frame = 1000 if stub_test else None

        # Create TimeSeries for each data channel
        for time_series_name, channel_names in time_series_name_to_channel_id_mapping.items():
            time_series_metadata = picoscope_time_series_metadata[time_series_name]

            data_to_add = []
            for channel_name in channel_names:
                trace_extractor = self.get_trace_extractor_from_picoscope(channel_name=channel_name)
                data = trace_extractor.get_traces(end_frame=end_frame)
                data_to_add.append(data if not stub_test else data[:6000])

            sampling_frequency = trace_extractor.get_sampling_frequency()

            time_series = np.column_stack(data_to_add)
            picoscope_time_series = TimeSeries(
                name=time_series_name,
                data=time_series if len(channel_names) > 1 else time_series.squeeze(axis=1),
                rate=sampling_frequency,
                description=time_series_metadata["description"],
                unit=time_series_metadata["unit"],
                conversion=1.0,
            )
            nwbfile.add_acquisition(picoscope_time_series)
