from pathlib import Path

import numpy as np
from ndx_events import EventsTable, EventTypesTable, Task
from ndx_photometry import FiberPhotometryResponseSeries
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import TimeSeries, NWBFile


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
                    EventTypesTable=dict(
                        name="event_types",
                        description="Contains the type of events (reward, air puff, light, and licking).",
                    ),
                    EventsTable=dict(
                        name="Events",
                        description="Contains the onset times of reward, air puff, light, and licking.",
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
        df_over_f_metadata = metadata["Ophys"]["DfOverF"]

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
            fiber_ref = nwbfile.acquisition[raw_series_name].fibers
            excitation_ref = nwbfile.acquisition[raw_series_name].excitation_sources
            photodetector_ref = nwbfile.acquisition[raw_series_name].photodetectors
            fluorophore_ref = nwbfile.acquisition[raw_series_name].fluorophores

            description = photometry_response_series_metadata["description"]

            data = self._processed_photometry_data[channel_name]
            response_series = FiberPhotometryResponseSeries(
                name=series_name,
                description=description,
                data=data if not stub_test else data[:6000],
                unit="n.a.",
                rate=self._sampling_frequency,
                fibers=fiber_ref,
                excitation_sources=excitation_ref,
                photodetectors=photodetector_ref,
                fluorophores=fluorophore_ref,
            )

            ophys_module.add(response_series)

    def add_binary_behavior(self, nwbfile, metadata):

        if (
            self._experiment_type == "run"
        ):  # whether the mouse was only running ('run') or received stimuli (reward, air puff, light... - 'rew')
            return

        events_metadata = metadata["Behavior"]["Events"]
        events_table_name = events_metadata["EventsTable"]["name"]

        behavior_module = get_module(nwbfile, name="behavior")
        assert (
            events_table_name not in behavior_module.data_interfaces
        ), f"The {events_table_name} is already in nwbfile."

        event_types_table = EventTypesTable(**events_metadata["EventTypesTable"])

        event_names_mapping = dict(
            Light="Light stimulus trigger",
            Reward="Reward delivery trigger",
            Licking="Licking sensor output",
            AirPuff="Airpuff delivery trigger",
            # RewardLong="Long reward delivery trigger",
            # RewardShort="Short reward delivery trigger",
            # RewardRest="Reward delivery trigger during rest",
            # RewardLongRest="Long reward delivery trigger during rest",
            # RewardShortRest="Short reward delivery trigger during rest",
            # AirPuffRest="Airpuff delivery trigger during rest",
            # LightRest="Light stimulus trigger during rest",
        )

        for event_name in event_names_mapping.values():
            event_types_table.add_row(
                event_name=event_name,
                event_type_description=f"The onset times of the {event_name} event.",
            )

        task = Task()
        task.event_types = event_types_table
        nwbfile.add_lab_meta_data(task)

        events = EventsTable(
            **events_metadata["EventsTable"],
            target_tables={"event_type": event_types_table},  # sets the dynamic table region link
        )

        for event_id, (event_name, renamed_event_name) in enumerate(event_names_mapping.items()):
            event_onset = self._processed_photometry_data[event_name]
            if isinstance(event_onset, dict):
                event_indices = event_onset["ir"] if "ir" in event_onset else []
            else:
                event_indices = np.where(event_onset)[0]
            if not len(event_indices):
                continue
            for timestamp in self.get_timestamps()[event_indices]:
                events.add_row(
                    event_type=event_id,
                    timestamp=timestamp,
                )

        behavior_module.add(events)

    def add_movement_events(self, nwbfile, metadata):
        events_metadata = metadata["Behavior"]["Events"]
        events_table_name = events_metadata["EventsTable"]["name"]

        behavior_module = get_module(nwbfile, name="behavior")
        if events_table_name in behavior_module.data_interfaces:
            events_table = behavior_module.data_interfaces[events_table_name]
            event_types_table = nwbfile.lab_meta_data["task"].event_types
        else:
            event_types_table = EventTypesTable(**events_metadata["EventTypesTable"])
            task = Task()
            task.event_types = event_types_table
            nwbfile.add_lab_meta_data(task)

            events_table = EventsTable(
                **events_metadata["EventsTable"],
                target_tables={"event_type": event_types_table},  # sets the dynamic table region link
            )
            behavior_module.add(events_table)

        event_names_mapping = dict(
            AccOn="Acceleration onset",
            DecOn="Deceleration onset",
            MovOn="Movement onset",
            MovOff="Movement offset",
        )

        for event_name in event_names_mapping.values():
            event_types_table.add_row(
                event_name=event_name,
                event_type_description=f"The times of the {event_name} event.",
            )

        for event_id, (event_name, renamed_event_name) in enumerate(event_names_mapping.items()):
            event_onset = self._processed_photometry_data[event_name]
            if isinstance(event_onset, dict):
                event_indices = event_onset["ir"] if "ir" in event_onset else []
            else:
                event_indices = np.where(event_onset)[0]
            if not len(event_indices):
                continue
            for timestamp in self.get_timestamps()[event_indices]:
                events_table.add_row(
                    event_type=event_id,
                    timestamp=timestamp,
                )

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
        for event_id, event_name in enumerate(event_types_table["event_name"][:]):
            peaks = self._processed_photometry_data[event_name]
            peak_indices = np.where(peaks)[0]
            for timestamp, peak in zip(timestamps[peak_indices], peaks[peak_indices]):
                events.add_row(
                    event_type=event_id,
                    timestamp=timestamp,
                    peak_fluorescence=peak,
                )

        nwbfile.add_analysis(events)
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
        self.add_binary_behavior(nwbfile=nwbfile, metadata=metadata)
        # Adds the movement events (accelerations, decelerations, movement onsets, movement offsets) to the NWB file
        self.add_movement_events(nwbfile=nwbfile, metadata=metadata)
        # Adds the transient peaks to the NWB file
        self.add_analysis(nwbfile=nwbfile)
        # Adds the DFF traces to the NWB file
        self.add_delta_f_over_f_traces(
            nwbfile=nwbfile,
            metadata=metadata,
            channel_name_to_photometry_series_name_mapping=channel_name_to_photometry_series_name_mapping,
            stub_test=stub_test,
        )
