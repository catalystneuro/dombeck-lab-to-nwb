from pathlib import Path

import numpy as np
import pandas as pd
from ndx_events import EventsTable, EventTypesTable
from ndx_fiber_photometry import FiberPhotometryResponseSeries
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import TimeSeries, NWBFile
from pynwb.epoch import TimeIntervals


class Azcorra2023ProcessedFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Data interface for Azcorra2023 fiber photometry data conversion."""

    display_name = "Azcorra2023ProcessedPhotometry"
    associated_suffixes = ".mat"
    info = "Interface for processed fiber photometry data."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            The path that points to the .mat file containing the processed photometry data.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.file_path = file_path
        self.verbose = verbose
        processed_photometry_data = read_mat(filename=str(self.file_path))["data6"]
        self._experiment_type = processed_photometry_data["RunRew"]
        assert "data" in processed_photometry_data, f"Processed photometry data not found in {self.file_path}."
        self._processed_photometry_data = processed_photometry_data["data"]
        self._timestamps = None
        self._sampling_frequency = 100.0

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        metadata["Behavior"].update(
            dict(
                Velocity=dict(
                    name="Velocity", description="The velocity from rotary encoder converted to m/s.", unit="m/s"
                ),
                Acceleration=dict(
                    name="Acceleration", description="The acceleration measured in the unit of m/s2.", unit="m/s2"
                ),
                Events=dict(
                    name="Events",
                    description="Contains the times when the mouse was moving and the reward, air puff, light, and licking event times.",
                ),
                WheelEvents=dict(
                    EventsTable=dict(
                        name="WheelEvents",
                        description="Contains the accelerations, decelerations times.",
                    ),
                    EventTypesTable=dict(
                        name="WheelEventTypes",
                        description="Contains the type of wheel events.",
                    ),
                ),
            ),
        )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        processed_photometry_data = read_mat(filename=str(self.file_path))["data6"]
        num_frames = len(processed_photometry_data["data"]["chGreen"])
        return np.arange(num_frames) / self._sampling_frequency

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        if stub_test:
            return timestamps[:6000]
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.array(aligned_timestamps)

    def add_continuous_behavior(self, nwbfile: NWBFile, metadata: dict):
        """
        Add continuous behavior data (velocity, acceleration) to the NWB file.
        """

        behavior_metadata = metadata["Behavior"]

        assert (
            "chMov" in self._processed_photometry_data
        ), f"Velocity data not found in {self.source_data['file_path']}."
        velocity = self._processed_photometry_data["chMov"]
        velocity_metadata = behavior_metadata["Velocity"]
        velocity_ts = TimeSeries(
            data=velocity,
            rate=self._sampling_frequency,
            **velocity_metadata,
        )

        assert (
            "Acceleration" in self._processed_photometry_data
        ), f"Acceleration data not found in {self.source_data['file_path']}."
        acceleration = self._processed_photometry_data["Acceleration"]
        acceleration_metadata = behavior_metadata["Acceleration"]
        acceleration_ts = TimeSeries(
            data=acceleration,
            rate=self._sampling_frequency,
            **acceleration_metadata,
        )

        behavior_module = get_module(
            nwbfile,
            name="behavior",
            description="Contains velocity and acceleration measured over time.",
        )

        behavior_module.add(velocity_ts)
        behavior_module.add(acceleration_ts)

    def add_delta_f_over_f_traces(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_name_to_photometry_series_name_mapping: dict,
        stub_test: bool = False,
    ):
        """
        Add the DFF traces to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the data will be added.
        metadata : dict
            The metadata dictionary.
        channel_name_to_photometry_series_name_mapping : dict
            A dictionary mapping the channel names from the file to the photometry series names that are going to be added.
        stub_test : bool, optional
            Whether to run a stub test, by default False.

        """
        df_over_f_metadata = metadata["Ophys"]["FiberPhotometry"]["DfOverF"]

        traces_metadata = df_over_f_metadata["FiberPhotometryResponseSeries"]
        traces_metadata_to_add = [
            trace
            for trace in traces_metadata
            if trace["name"] in channel_name_to_photometry_series_name_mapping.values()
        ]

        ophys_module = get_module(nwbfile=nwbfile, name="ophys", description=f"Processed fiber photometry data.")

        for channel_name, series_name in channel_name_to_photometry_series_name_mapping.items():
            if series_name in ophys_module.data_interfaces:
                raise ValueError(f"The fiber photometry series {series_name} already exists in the NWBfile.")

            # Get photometry response series metadata
            photometry_response_series_metadata = next(
                series_metadata for series_metadata in traces_metadata_to_add if series_metadata["name"] == series_name
            )

            raw_series_name = series_name.replace("DfOverF", "")
            # Retrieve references to the raw photometry data
            description = photometry_response_series_metadata["description"]

            data = self._processed_photometry_data[channel_name]
            response_series = FiberPhotometryResponseSeries(
                name=series_name,
                description=description,
                data=data if not stub_test else data[:6000],
                unit="n.a.",
                rate=self._sampling_frequency,
                fiber_photometry_table_region=nwbfile.acquisition[raw_series_name].fiber_photometry_table_region,
            )

            ophys_module.add(response_series)

    def _get_start_end_times(self, binary_event_data):

        timestamps = self.get_timestamps()
        if isinstance(binary_event_data, dict):
            ones_indices = binary_event_data["ir"] if "ir" in binary_event_data else []
            binary_event_data = np.zeros_like(timestamps)
            binary_event_data[ones_indices] = 1

        if not np.any(binary_event_data):
            return [], []

        ones = np.where(binary_event_data == 1)[0]

        # Calculate the differences between consecutive indices
        diff = np.diff(ones)

        # Find where the difference is not 1
        ends = np.where(diff != 1)[0]

        # The start of an interval is one index after the end of the previous interval
        starts = ends + 1

        # Handle the case for the first interval
        starts = np.insert(starts, 0, 0)

        # Handle the case for the last interval
        ends = np.append(ends, len(ones) - 1)

        # Return the start and end indices of the intervals
        return timestamps[ones[starts]], timestamps[ones[ends]]

    def add_events(self, nwbfile, metadata):

        if (
            self._experiment_type == "run"
        ):  # whether the mouse was only running ('run') or received stimuli (reward, air puff, light... - 'rew')
            return

        events_metadata = metadata["Behavior"]["Events"]
        events = TimeIntervals(**events_metadata)
        events.add_column(
            name="event_type",
            description="The type of event (licking, air puff, light or reward delivery).",
        )

        events_start_times, events_end_times, events_types, events_tags = [], [], [], []

        timestamps = self.get_timestamps()

        events_to_add = ["MovOnOff", "Light", "Licking", "AirPuff"]

        for event_name in events_to_add:
            binary_event_data = self._processed_photometry_data[event_name]
            start_times, end_times = self._get_start_end_times(binary_event_data)
            if not len(start_times):
                continue
            events_start_times.extend(start_times)
            events_end_times.extend(end_times)
            events_types.extend([event_name] * len(start_times))

            event_tags = [[""]] * len(start_times)
            if event_name in ["Light", "AirPuff"]:
                rest_ones_indices = np.where(self._processed_photometry_data[f"{event_name}Rest"] == 1)[0]
                rest_times = timestamps[rest_ones_indices]
                tags_indices = np.where(np.isin(start_times, rest_times))[0]
                if len(tags_indices):
                    event_tags = [["rest"] if i in tags_indices else [""] for i in range(len(start_times))]

            events_tags.extend(event_tags)

        reward_events = dict(
            RewardLong=["long"],
            RewardShort=["short"],
            RewardRest=["rest"],
            RewardLongRest=["long", "rest"],
            RewardShortRest=["short", "rest"],
        )
        reward_events_renamed = dict(
            RewardLong="Reward",
            RewardShort="Reward",
            RewardRest="Reward",
            RewardLongRest="Reward",
            RewardShortRest="Reward",
        )

        for event_name, event_tag in reward_events.items():
            binary_event_data = self._processed_photometry_data[event_name]
            start_times, end_times = self._get_start_end_times(binary_event_data)
            if not len(start_times):
                continue
            events_start_times.extend(start_times)
            events_end_times.extend(end_times)
            events_types.extend([reward_events_renamed[event_name]] * len(start_times))
            events_tags.extend([event_tag] * len(start_times))

        df = pd.DataFrame(columns=["start_time", "stop_time", "event_type", "tags"])
        df["start_time"] = events_start_times
        df["stop_time"] = events_end_times
        df["event_type"] = events_types
        df["tags"] = events_tags
        df = df.sort_values(by="start_time")

        for _, row in df.iterrows():
            events.add_interval(**row)

        behavior = get_module(nwbfile, name="behavior")
        behavior.add(events)

    def add_wheel_events(self, nwbfile, metadata):
        events_metadata = metadata["Behavior"]["WheelEvents"]

        behavior = get_module(nwbfile, name="behavior")
        event_types_table = EventTypesTable(**events_metadata["EventTypesTable"])
        behavior.add(event_types_table)

        events_table = EventsTable(
            **events_metadata["EventsTable"],
            target_tables={"event_type": event_types_table},  # sets the dynamic table region link
        )

        event_names_mapping = dict(
            AccOn="Acceleration onset",
            DecOn="Deceleration onset",
        )

        for event_name in event_names_mapping.values():
            event_types_table.add_row(
                event_name=event_name,
                event_type_description=f"The times of the {event_name} event.",
            )

        wheel_events_dfs = []
        for event_id, (event_name, renamed_event_name) in enumerate(event_names_mapping.items()):
            event_onset = self._processed_photometry_data[event_name]
            if isinstance(event_onset, dict):
                event_indices = event_onset["ir"] if "ir" in event_onset else []
            else:
                event_indices = np.where(event_onset)[0]
            if not len(event_indices):
                continue
            event_times = self.get_timestamps()[event_indices]

            wheel_events_dfs.append(
                pd.DataFrame(
                    {
                        "timestamp": event_times,
                        "event_type": [event_id] * len(event_times),
                    }
                )
            )

        wheel_events_to_add = pd.concat(wheel_events_dfs, ignore_index=True)
        wheel_events_to_add["event_type"] = wheel_events_to_add["event_type"].astype(np.uint8)
        wheel_events_to_add = wheel_events_to_add.sort_values("timestamp")

        wheel_events_table = events_table.from_dataframe(
            wheel_events_to_add,
            name=events_metadata["EventsTable"]["name"],
            table_description=events_metadata["EventsTable"]["description"],
        )
        wheel_events_table.event_type.table = event_types_table
        behavior.add(wheel_events_table)

    def add_analysis(self, nwbfile: NWBFile) -> None:
        event_types_table = EventTypesTable(
            name="EventTypes",
            description="Contains the type of events.",
        )

        event_names_mapping = dict(
            peaksG="Large transient peaks for green fluorescence",
            peaksR="Large transient peaks for red fluorescence",
            peaksGRun="Large transient peaks occurring during running periods for green fluorescence",
            peaksRRun="Large transient peaks occurring during running periods for red fluorescence",
        )

        for event_name, event_type_description in event_names_mapping.items():
            if event_name in self._processed_photometry_data:
                if np.any(self._processed_photometry_data[event_name]):
                    event_types_table.add_row(
                        event_name=event_name,
                        event_type_description=event_type_description,
                    )

        if not len(event_types_table):
            return

        events = EventsTable(
            name="Events",
            description="Contains the onset times of events.",
            target_tables={"event_type": event_types_table},
        )
        events.add_column(
            name="peak_fluorescence",
            description="The value of the large transient peaks.",
        )

        timestamps = self.get_timestamps()

        peak_events_dfs = []
        for event_id, event_name in enumerate(event_types_table["event_name"][:]):
            peaks = self._processed_photometry_data[event_name]
            peak_indices = np.where(peaks)[0]

            peak_times = timestamps[peak_indices]
            peak_events_dfs.append(
                pd.DataFrame(
                    {
                        "timestamp": peak_times,
                        "event_type": [event_id] * len(peak_times),
                        "peak_fluorescence": peaks[peak_indices],
                    }
                )
            )

        peak_events_to_add = pd.concat(peak_events_dfs, ignore_index=True)
        peak_events_to_add["event_type"] = peak_events_to_add["event_type"].astype(np.uint8)
        peak_events_to_add = peak_events_to_add.sort_values("timestamp")

        peak_events_table = events.from_dataframe(
            peak_events_to_add,
            name="Events",
            table_description="Contains the onset times of large fluorescence peaks.",
        )
        peak_events_table.event_type.table = event_types_table

        nwbfile.add_analysis(peak_events_table)
        nwbfile.add_analysis(event_types_table)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_name_to_photometry_series_name_mapping: dict = None,
        stub_test: bool = False,
    ):
        """
        Add the continuous velocity, acceleration, binary events and DFF traces to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the data will be added.
        metadata : dict
            The metadata dictionary.
        channel_name_to_photometry_series_name_mapping : dict
            A dictionary mapping the channel names from the file to the photometry series names that are going to be added.
        stub_test : bool, optional
            Whether to run a stub test, by default False.

        """

        # Adds the velocity and acceleration data to the NWB file
        self.add_continuous_behavior(nwbfile=nwbfile, metadata=metadata)
        # Adds the binary behavior events (licking, light, air puff, reward) to the NWB file
        self.add_events(nwbfile=nwbfile, metadata=metadata)
        # Adds the movement events (accelerations, decelerations) to the NWB file
        self.add_wheel_events(nwbfile=nwbfile, metadata=metadata)
        # Adds the transient peaks to the NWB file
        self.add_analysis(nwbfile=nwbfile)
        # Adds the DFF traces to the NWB file
        self.add_delta_f_over_f_traces(
            nwbfile=nwbfile,
            metadata=metadata,
            channel_name_to_photometry_series_name_mapping=channel_name_to_photometry_series_name_mapping,
            stub_test=stub_test,
        )
