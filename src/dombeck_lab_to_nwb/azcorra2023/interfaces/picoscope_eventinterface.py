from pathlib import Path
from typing import Optional

import numpy as np
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
        mat_files = natsorted(self.folder_path.glob(f"{session_name}_*.mat"))
        assert mat_files, f"The .mat files are missing from {folder_path}."

        super().__init__(file_list=mat_files, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["Events"] = dict(
            EventTypesTable=dict(
                name="PicosScopeEventTypes",
                description="Contains the type of binary signals from PicoScope.",
            ),
            EventsTable=dict(
                name="PicoscopeEvents",
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

    def get_picoscope_extractor_for_binary_traces(self):
        recording_list = [
            PicoscopeRecordingExtractor(file_path=str(file_path)) for file_path in self.source_data["file_list"]
        ]
        concatenated_recording = ConcatenateSegmentRecording(recording_list=recording_list)

        extractor = ChannelSliceRecording(
            parent_recording=concatenated_recording,
            channel_ids=self.channel_ids,
        )

        return extractor

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

        nwbfile.add_acquisition(event_types_table)

        events = EventsTable(
            **events_metadata["EventsTable"],
            target_tables={"event_type": event_types_table},  # sets the dynamic table region link
        )

        extractor = self.get_picoscope_extractor_for_binary_traces()
        times = extractor.get_times()

        for event_id, (channel_name, renamed_channel_name) in enumerate(channel_names_mapping.items()):
            traces = extractor.get_traces(channel_ids=[channel_name])
            # Using the same threshold as in
            # https://github.com/DombeckLab/Azcorra2023/blob/2819bd5b7a6021243c44dfd45b5b25fd24ae8122/Fiber%20photometry%20data%20analysis/Data%20pre%20processing/selectSignals_paper.m#L110C1-L110C22
            event_times = get_rising_frames_from_ttl(traces, threshold=0.05)

            timestamps = times[event_times] if not stub_test else times[event_times][:100]
            if len(event_times):
                for timestamp in timestamps:
                    events.add_row(
                        event_type=event_id,
                        timestamp=timestamp,
                    )

        nwbfile.add_acquisition(events)

        ttl_types_table = TtlTypesTable(**events_metadata["TtlTypesTable"])
        ttl_types_table.add_column(name="duration", description="The duration of the TTL pulse.")

        ttl_types_table.add_row(
            event_name="Ch405",
            event_type_description="The times when the 405 nm LED was on.",
            pulse_value=0,
            duration=0.005,
        )
        ttl_types_table.add_row(
            event_name="Ch470",
            event_type_description="The times when the 470 nm LED was on.",
            pulse_value=1,
            duration=0.005,
        )

        ttls_table = TtlsTable(**events_metadata["TtlsTable"], target_tables={"ttl_type": ttl_types_table})

        waveform_traces = extractor.get_traces(channel_ids=["E"])
        ch405_event_times = get_falling_frames_from_ttl(waveform_traces, threshold=0.5)
        ch405_timestamps = times[ch405_event_times] if not stub_test else times[ch405_event_times][:100]
        for timestamp in ch405_timestamps:
            ttls_table.add_row(
                timestamp=timestamp,
                ttl_type=0,  # NOT the pulse value, but a row index into the ttl_types_table
                duration=0.005,
            )

        ch470_event_times = get_rising_frames_from_ttl(waveform_traces, threshold=0.5)
        ch470_timestamps = times[ch470_event_times] if not stub_test else times[ch470_event_times][:100]
        for timestamp in ch470_timestamps:
            ttls_table.add_row(
                timestamp=timestamp,
                ttl_type=1,
                duration=0.005,
            )

        nwbfile.add_acquisition(ttl_types_table)
        nwbfile.add_acquisition(ttls_table)
