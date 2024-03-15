from pathlib import Path
from typing import Optional

from natsort import natsorted
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
            name="PicoscopeEvents",
            description="Contains the onset times of binary signals from the PicoScope.",
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

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        from ndx_events import AnnotatedEventsTable

        events_metadata = metadata["Events"]
        events_table_name = events_metadata["name"]
        assert events_table_name not in nwbfile.acquisition, f"The {events_metadata['name']} is already in nwbfile."

        events = AnnotatedEventsTable(
            name=events_table_name,
            description=events_metadata["description"],
        )

        channel_names_mapping = dict(
            D="Light stimulus trigger",
            F="Reward delivery trigger",
            G="Licking sensor output",
            H="Airpuff delivery trigger",
        )

        extractor = self.get_picoscope_extractor_for_binary_traces()
        times = extractor.get_times()

        for channel_name, renamed_channel_name in channel_names_mapping.items():
            traces = extractor.get_traces(channel_ids=[channel_name])
            # Using the same threshold as in
            # https://github.com/DombeckLab/Azcorra2023/blob/2819bd5b7a6021243c44dfd45b5b25fd24ae8122/Fiber%20photometry%20data%20analysis/Data%20pre%20processing/selectSignals_paper.m#L110C1-L110C22
            event_times = get_rising_frames_from_ttl(traces, threshold=0.05)

            if len(event_times):
                events.add_event_type(
                    label=renamed_channel_name,
                    event_description=f"The onset times of the {renamed_channel_name} event.",
                    event_times=times[event_times],
                )
        # LEDs are alternated at 100Hz, as reported by variable E (output of waveform generator)
        # <0.5 for 405, >0.5 5 for 470.
        waveform_traces = extractor.get_traces(channel_ids=["E"])

        ch405_event_times = get_falling_frames_from_ttl(waveform_traces, threshold=0.5)
        events.add_event_type(
            label="Ch405",
            event_description=f"The event times when the 405 nm LED was on.",
            event_times=times[ch405_event_times],
        )

        ch470_event_times = get_rising_frames_from_ttl(waveform_traces, threshold=0.5)
        events.add_event_type(
            label="Ch470",
            event_description=f"The event times when the 470 nm LED was on.",
            event_times=times[ch470_event_times],
        )

        nwbfile.add_acquisition(events)
