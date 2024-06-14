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

from dombeck_lab_to_nwb.azcorra2023.photometry_utils import add_fiber_photometry_series


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
        crop_point = processed_photometry_data["cropStart"]
        # If the crop point is a list, it means that the end of the recording was cropped as well
        self._crop_start = crop_point[0] if isinstance(crop_point, np.ndarray) else crop_point

    def get_starting_time(self) -> float:
        """
        Return the starting time of the processed photometry data.
        If the start of the picoscope recording had artefacts, the corrupted segment was cut off manually and the cropping point
        was saved as "cropStart". We are using this value to align the starting time of the processed data with the
        picoscope data.
        """
        if self._crop_start == 1:
            return 0.0
        return self._crop_start / self._sampling_frequency

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
        processed_photometry_data = read_mat(filename=str(self.file_path))["data6"]["data"]
        num_frames = len(processed_photometry_data["chMov"])
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

        timestamps = self.get_timestamps()

        velocity_ts = TimeSeries(
            data=velocity,
            rate=self._sampling_frequency,
            starting_time=timestamps[0],
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
            starting_time=timestamps[0],
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
        trace_name_to_channel_id_mapping: dict,
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
        trace_name_to_channel_id_mapping : dict
            A dictionary that maps the DF/F trace name to the channel ids. (e.g. {"DfOverFFiberPhotometryResponseSeries": ["chRed", "chGreen"]})
        stub_test : bool, optional
            Whether to run a stub test, by default False.

        """
        ophys_module = get_module(nwbfile=nwbfile, name="ophys", description=f"Processed fiber photometry data.")

        timestamps = self.get_timestamps(stub_test=stub_test)

        for series_ind, (series_name, channel_names) in enumerate(trace_name_to_channel_id_mapping.items()):
            if series_name in ophys_module.data_interfaces:
                raise ValueError(f"The DF/F series {series_name} already exists in the NWBfile.")

            data_to_add = []
            for channel_name in channel_names:
                if channel_name not in self._processed_photometry_data:
                    print(f"Channel {channel_name} not found in the processed photometry data.")
                    continue

                data = self._processed_photometry_data[channel_name]
                data_to_add.append(data if not stub_test else data[:6000])

            squeeze = False
            if len(channel_names) == 1:
                table_region = [series_ind]
                squeeze = True
            elif len(channel_names) == 2:
                table_region_ind = series_ind * len(trace_name_to_channel_id_mapping.keys())
                table_region = [table_region_ind, table_region_ind + 1]
            else:
                raise ValueError(f"Expected 1 or 2 channel names, found {len(channel_names)}.")

            raw_series_name = series_name.replace("DfOverF", "")

            fiber_data = np.column_stack(data_to_add)
            if raw_series_name in nwbfile.acquisition:
                # Retrieve references to the raw photometry data
                raw_response_series = nwbfile.acquisition[raw_series_name]
                raw_response_series_description = raw_response_series.description
                description = raw_response_series_description.replace("Raw", "DF/F calculated from")

                fiber_photometry_table_region = raw_response_series.fiber_photometry_table_region

                response_series = FiberPhotometryResponseSeries(
                    name=series_name,
                    description=description,
                    data=fiber_data if not squeeze else fiber_data.squeeze(axis=1),
                    unit="n.a.",
                    rate=self._sampling_frequency,
                    starting_time=timestamps[0],
                    fiber_photometry_table_region=fiber_photometry_table_region,
                )

                ophys_module.add(response_series)

            else:
                # Create references for the fiber photometry table
                traces_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"][series_ind]
                # Override name and description for the DF/F series
                traces_metadata["name"] = series_name
                traces_metadata["description"] = traces_metadata["description"].replace("Raw", "DF/F calculated from")
                add_fiber_photometry_series(
                    nwbfile=nwbfile,
                    metadata=metadata,
                    data=fiber_data if not squeeze else fiber_data.squeeze(axis=1),
                    timestamps=timestamps,
                    fiber_photometry_series_name=series_name,
                    table_region=table_region,
                    parent_container="processing/ophys",
                )

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
        )

        for event_name in reward_events.keys():
            binary_event_data = self._processed_photometry_data[event_name]
            start_times, end_times = self._get_start_end_times(binary_event_data)
            if not len(start_times):
                continue
            events_start_times.extend(start_times)
            events_end_times.extend(end_times)
            events_types.extend(["Reward"] * len(start_times))

            event_tag = reward_events[event_name]
            events_tags.extend([event_tag] * len(start_times))

        if not len(events_start_times):
            return

        df = pd.DataFrame(
            {
                "start_time": events_start_times,
                "stop_time": events_end_times,
                "event_type": events_types,
                "tags": events_tags,
            }
        )
        df = df.sort_values(by="start_time")

        # Find duplicates based on specific columns
        duplicates = df.duplicated(subset=["start_time", "stop_time", "event_type"], keep=False)
        # Filter the DataFrame to get only the duplicated rows
        duplicated_df = df[duplicates]
        if not duplicated_df.empty:
            # Find duplicated events that have the same start and stop time and merges their tags
            df = (
                df.groupby(["start_time", "stop_time", "event_type"])
                .agg({"tags": lambda x: list(set(sum(x, [])))})
                .reset_index()
            )

        df = df.reset_index(drop=True)
        for row_ind, row in df.iterrows():
            event_type = row["event_type"]
            time_series_name = "Velocity" if event_type == "MovOnOff" else event_type
            events.add_interval(
                **row,
                timeseries=nwbfile.acquisition[time_series_name],
                id=row_ind,
            )

        behavior = get_module(nwbfile, name="behavior")
        behavior.add(events)

    def add_wheel_events(self, nwbfile, metadata):
        events_metadata = metadata["Behavior"]["WheelEvents"]

        behavior = get_module(nwbfile, name="behavior")
        event_types_table = EventTypesTable(**events_metadata["EventTypesTable"])

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

        if not len(wheel_events_dfs):
            return

        wheel_events_to_add = pd.concat(wheel_events_dfs, ignore_index=True)
        wheel_events_to_add["event_type"] = wheel_events_to_add["event_type"].astype(np.uint8)
        wheel_events_to_add = wheel_events_to_add.sort_values("timestamp")

        for row_index, row in wheel_events_to_add.reset_index(drop=True).iterrows():
            events_table.add_row(
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                check_ragged=False,
                id=row_index,
            )
        behavior.add(event_types_table)
        behavior.add(events_table)

    def add_analysis(self, nwbfile: NWBFile) -> None:
        event_types_table = EventTypesTable(
            name="PeakFluorescenceEventTypes",
            description="Contains the type of events.",
        )

        event_names_mapping = dict(
            peaksG="Large transient peaks for Fiber 1 fluorescence",
            peaksR="Large transient peaks for Fiber 2 fluorescence",
            peaksGRun="Large transient peaks occurring during running periods for Fiber 1 fluorescence",
            peaksRRun="Large transient peaks occurring during running periods for Fiber 2 fluorescence",
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
            name="PeakFluorescenceEvents",
            description="Contains the onset times of large fluorescence peaks.",
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

        for row_index, row in peak_events_to_add.reset_index(drop=True).iterrows():
            events.add_row(
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                peak_fluorescence=row["peak_fluorescence"],
                check_ragged=False,
                id=row_index,
            )

        nwbfile.add_analysis(events)
        nwbfile.add_analysis(event_types_table)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        trace_name_to_channel_id_mapping: dict,
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
        trace_name_to_channel_id_mapping : dict
            A dictionary that maps the DF/F trace name to the channel ids. (e.g. {"DfOverFFiberPhotometryResponseSeries": ["chRed", "chGreen"]})
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
            trace_name_to_channel_id_mapping=trace_name_to_channel_id_mapping,
            stub_test=stub_test,
        )
