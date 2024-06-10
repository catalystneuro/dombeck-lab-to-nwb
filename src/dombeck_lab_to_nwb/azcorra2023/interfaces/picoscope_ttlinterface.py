from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from hdmf.common import DynamicTableRegion
from natsort import natsorted
from ndx_events import EventsTable, TtlsTable, EventTypesTable, TtlTypesTable
from neuroconv import BaseDataInterface
from neuroconv.tools.signal_processing import get_falling_frames_from_ttl, get_rising_frames_from_ttl
from neuroconv.utils import FolderPathType
from pynwb import NWBFile
from spikeinterface import ConcatenateSegmentRecording, ChannelSliceRecording

from dombeck_lab_to_nwb.azcorra2023.extractors import PicoscopeRecordingExtractor


class PicoscopeTtlInterface(BaseDataInterface):
    """
    Custom data interface class for converting the TTL signals from PicoScope.
    """

    display_name = "Picoscope TTL Interface"
    associated_suffixes = ".mat"
    info = "Interface for PicoScope TTL signals (405 nm and 470 nm excitation sources)."

    def __init__(self, folder_path: FolderPathType, channel_name: str = None, verbose: bool = True):

        self.folder_path = Path(folder_path)
        self.channel_name = channel_name or "E"
        session_name = self.folder_path.stem
        file_pattern = f"{session_name.split('-')[0]}*.mat"
        mat_files = natsorted(self.folder_path.glob(file_pattern))
        if not len(mat_files):
            raise ValueError(f"No .mat files found in {self.folder_path}")

        super().__init__(file_paths=mat_files, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["Events"] = dict(
            TtlTypesTable=dict(
                description="Contains the TTL event types from PicoScope.",
            ),
            TtlsTable=dict(
                description="Contains the 405 nm and 470 nm illumination onset times.",
            ),
        )

        return metadata

    def get_trace_extractor_from_picoscope(self, channel_name: str):
        recording_list = [
            PicoscopeRecordingExtractor(file_path=str(file_path), channel_name=channel_name)
            for file_path in self.source_data["file_paths"]
        ]
        return ConcatenateSegmentRecording(recording_list=recording_list)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        stub_test: bool = False,
    ) -> None:

        events_metadata = metadata["Events"]

        ttls_table_name = "TtlsTable"
        assert ttls_table_name not in nwbfile.acquisition, f"The {ttls_table_name} is already in nwbfile."

        ttl_types_table = TtlTypesTable(**events_metadata["TtlTypesTable"])
        ttl_types_table.add_column(name="duration", description="The duration of the TTL pulse.")

        ttl_types_table.add_row(
            event_name="Ch405",
            event_type_description="The times when the 405 nm LED was on.",
            pulse_value=np.uint8(1),
            duration=0.005,
        )
        ttl_types_table.add_row(
            event_name="Ch470",
            event_type_description="The times when the 470 nm LED was on.",
            pulse_value=np.uint8(1),
            duration=0.005,
        )

        ttls_table = TtlsTable(**events_metadata["TtlsTable"], target_tables={"ttl_type": ttl_types_table})

        ttls_dfs = []
        waveform_extractor = self.get_trace_extractor_from_picoscope(channel_name=self.channel_name)
        waveform_traces = waveform_extractor.get_traces()
        times = waveform_extractor.get_times()
        ch405_event_times = get_falling_frames_from_ttl(waveform_traces, threshold=0.5)
        ch405_timestamps = times[ch405_event_times] if not stub_test else times[ch405_event_times][:100]

        ttls_dfs.append(
            pd.DataFrame(
                {
                    "timestamp": ch405_timestamps,
                    "ttl_type": [0] * len(ch405_timestamps),
                    # NOT the pulse value, but a row index into the ttl_types_table
                    "duration": [0.005] * len(ch405_timestamps),
                }
            )
        )

        ch470_event_times = get_rising_frames_from_ttl(waveform_traces, threshold=0.5)
        ch470_timestamps = times[ch470_event_times] if not stub_test else times[ch470_event_times][:100]

        ttls_dfs.append(
            pd.DataFrame(
                {
                    "timestamp": ch470_timestamps,
                    "ttl_type": [1] * len(ch470_timestamps),
                    # NOT the pulse value, but a row index into the ttl_types_table
                    "duration": [0.005] * len(ch470_timestamps),
                }
            )
        )

        ttls_to_add = pd.concat(ttls_dfs, ignore_index=True)
        ttls_to_add["ttl_type"] = ttls_to_add["ttl_type"].astype(np.uint8)
        ttls_to_add = ttls_to_add.sort_values("timestamp")

        for row_index, row in ttls_to_add.reset_index(drop=True).iterrows():
            ttls_table.add_row(
                timestamp=row["timestamp"],
                ttl_type=row["ttl_type"],
                check_ragged=False,
                id=row_index,
            )
        nwbfile.add_acquisition(ttl_types_table)
        nwbfile.add_acquisition(ttls_table)
