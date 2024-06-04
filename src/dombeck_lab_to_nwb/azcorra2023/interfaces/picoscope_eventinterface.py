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


class PicoscopeEventInterface(BaseDataInterface):
    """
    Custom data interface class for converting binary signals from PicoScope.
    """

    display_name = "Picoscope Events"
    associated_suffixes = ".mat"
    info = "Interface for PicoScope binary signals."

    def __init__(self, folder_path: FolderPathType, channel_ids: Optional[list] = None, verbose: bool = True):

        self.folder_path = Path(folder_path)
        self.channel_ids = channel_ids or ["E", "D", "F", "G", "H"]
        session_name = self.folder_path.stem
        file_pattern = f"{session_name.split('-')[0]}*.mat"
        mat_files = natsorted(self.folder_path.glob(file_pattern))
        if not len(mat_files):
            raise ValueError(f"No .mat files found in {self.folder_path}")

        super().__init__(file_paths=mat_files, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["Events"] = dict(
            EventTypesTable=dict(
                name="PicoScopeEventTypes",
                description="Contains the type of binary signals from PicoScope.",
            ),
            EventsTable=dict(
                name="PicoScopeEvents",
                description="Contains the onset times of binary signals from PicoScope.",
            ),
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

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False) -> None:
        from ndx_events import EventsTable

        events_metadata = metadata["Events"]
        events_table_name = events_metadata["EventsTable"]["name"]
        assert events_table_name not in nwbfile.acquisition, f"The {events_metadata['name']} is already in nwbfile."

        event_types_table = EventTypesTable(**events_metadata["EventTypesTable"])

        channel_names_mapping = dict(
            D="Light stimulus trigger",
            F="Reward delivery trigger",
            G="Licking sensor output",
            H="Airpuff delivery trigger",
        )

        for event_name in channel_names_mapping.values():
            event_types_table.add_row(
                event_name=event_name,
                event_type_description=f"The onset times of the {event_name} event.",
            )

        events = EventsTable(
            **events_metadata["EventsTable"],
            target_tables={"event_type": event_types_table},  # sets the dynamic table region link
        )

        events_dfs = []
        for event_id, (channel_name, renamed_channel_name) in enumerate(channel_names_mapping.items()):
            extractor = self.get_trace_extractor_from_picoscope(channel_name=channel_name)
            times = extractor.get_times()

            traces = extractor.get_traces(channel_ids=[channel_name])
            # Using the same threshold as in
            # https://github.com/DombeckLab/Azcorra2023/blob/2819bd5b7a6021243c44dfd45b5b25fd24ae8122/Fiber%20photometry%20data%20analysis/Data%20pre%20processing/selectSignals_paper.m#L110C1-L110C22
            event_times = get_rising_frames_from_ttl(traces, threshold=0.05)
            if not len(event_times):
                continue

            timestamps = times[event_times] if not stub_test else times[event_times][:100]
            events_df = pd.DataFrame(columns=["timestamp", "event_type"])
            events_df["timestamp"] = timestamps
            events_df["event_type"] = [event_id] * len(timestamps)
            events_dfs.append(events_df)

        if len(events_dfs):
            events_to_add = pd.concat(events_dfs, ignore_index=True)
            events_to_add["event_type"] = events_to_add["event_type"].astype(np.uint8)
            events_to_add = events_to_add.sort_values("timestamp")

            for row_index, row in events_to_add.reset_index(drop=True).iterrows():
                events.add_row(
                    timestamp=row["timestamp"],
                    event_type=row["event_type"],
                    check_ragged=False,
                    id=row_index,
                )
            nwbfile.add_acquisition(event_types_table)
            nwbfile.add_acquisition(events)

        ttls_table_name = "TtlsTable"
        assert ttls_table_name not in nwbfile.acquisition, f"The {ttls_table_name} is already in nwbfile."

        ttl_types_table = TtlTypesTable(**events_metadata["TtlTypesTable"])
        ttl_types_table.add_column(name="duration", description="The duration of the TTL pulse.")

        ttl_types_table.add_row(
            event_name="Ch405",
            event_type_description="The times when the 405 nm LED was on.",
            pulse_value=np.uint8(0),
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
        waveform_extractor = self.get_trace_extractor_from_picoscope(channel_name="E")
        waveform_traces = waveform_extractor.get_traces(channel_ids=["E"])
        times = waveform_extractor.get_times()
        ch405_event_times = get_falling_frames_from_ttl(waveform_traces, threshold=0.5)
        ch405_timestamps = times[ch405_event_times] if not stub_test else times[ch405_event_times][:100]

        ttls_dfs.append(
            pd.DataFrame(
                {
                    "timestamp": ch405_timestamps,
                    "ttl_type": [0]
                    * len(ch405_timestamps),  # NOT the pulse value, but a row index into the ttl_types_table
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
                    "ttl_type": [1]
                    * len(ch470_timestamps),  # NOT the pulse value, but a row index into the ttl_types_table
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
