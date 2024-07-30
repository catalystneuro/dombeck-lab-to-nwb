from copy import deepcopy
from pathlib import Path

import numpy as np
from ndx_fiber_photometry import FiberPhotometryResponseSeries
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.tools.signal_processing import get_rising_frames_from_ttl
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import NWBFile, TimeSeries

from dombeck_lab_to_nwb.he_embargo_2024.photometry_utils import add_fiber_photometry_series


class HeEmbargo2024FiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Data interface for HeEmbargo2024 fiber photometry data conversion."""

    display_name = "HeEmbargo2024OptogeneticStimulation"
    associated_suffixes = ".mat"
    info = "Interface for adding fiber photometry recordings."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        session_id: str,
        verbose: bool = False,
    ):
        """
        Initialize the HeEmbargo2024FiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePathType
            The path to the .mat file containing the fiber photometry data.
        session_id : str
            The identifier of the session.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        super().__init__(file_path=file_path, verbose=verbose)
        column_names, processed_data = self._read_data()
        self.column_names = column_names
        self._processed_data = processed_data

        filenames = processed_data[column_names.index("filename")]
        session_ids = [filename.split(".")[0] for filename in filenames]
        assert session_id in session_ids, f"Expected session_id '{session_id}', found {session_ids}."
        self._session_index = session_ids.index(session_id)
        self._sampling_frequency = None
        self._timestamps = None

    def _read_data(self):
        """Returns the column names and the processed data from the .mat file."""
        file_path = str(self.source_data["file_path"])
        processed_data = read_mat(filename=file_path)
        if "#subsystem#" not in processed_data:
            raise ValueError(f"Expected '#subsystem#' key in {file_path}.")
        column_names = processed_data["#subsystem#"]["MCOS"][7]
        data_values = processed_data["#subsystem#"]["MCOS"][2]
        return column_names, data_values

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
            ),
        )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        column_names, processed_data = self._read_data()
        velocity_index = column_names.index("velocity")
        velocity_data = processed_data[velocity_index][self._session_index]
        num_frames = velocity_data.shape[0]
        return np.arange(num_frames) / self._sampling_frequency

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        if stub_test:
            return timestamps[:6000]
        return timestamps

    def add_continuous_behavior(self, nwbfile: NWBFile, metadata: dict):
        """
        Add continuous behavior data (velocity, acceleration) to the NWB file.
        """
        behavior_metadata = metadata["Behavior"]

        timestamps = self.get_timestamps()

        behavior_module = get_module(
            nwbfile,
            name="behavior",
            description="Contains velocity and acceleration measured over time.",
        )

        if "velocity" in self.column_names:
            velocity_index = self.column_names.index("velocity")
            velocity = self._processed_data[velocity_index][self._session_index]

            velocity_metadata = behavior_metadata["Velocity"]

            velocity_ts = TimeSeries(
                data=velocity,
                rate=self._sampling_frequency,
                starting_time=timestamps[0],
                **velocity_metadata,
            )
            behavior_module.add(velocity_ts)

        if "acceleration" in self.column_names:
            acceleration_index = self.column_names.index("acceleration")
            acceleration = self._processed_data[acceleration_index][self._session_index]

            acceleration_metadata = behavior_metadata["Acceleration"]
            acceleration_ts = TimeSeries(
                data=acceleration,
                rate=self._sampling_frequency,
                starting_time=timestamps[0],
                **acceleration_metadata,
            )

            behavior_module.add(acceleration_ts)

    def add_fiber_photometry_series(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False):
        pass

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.array(aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        sampling_frequency: float,
        stub_test: bool = False,
    ) -> None:
        self._sampling_frequency = float(sampling_frequency)
        end_frame = 2000 if stub_test else None
        self.add_continuous_behavior(nwbfile=nwbfile, metadata=metadata)

        ophys_module = get_module(
            nwbfile,
            name="ophys",
            description="Contains the processed fiber photometry data.",
        )

        timestamps = self.get_timestamps(stub_test=stub_test)

        for channel_ind, channel_name in enumerate(["corrected470", "corrected405"]):
            column_index = self.column_names.index(channel_name)
            fiber_data = self._processed_data[column_index][self._session_index]

            series_name = (
                "FiberPhotometryResponseSeries"
                if channel_name == "corrected470"
                else "FiberPhotometryResponseSeriesIsosbestic"
            )
            add_fiber_photometry_series(
                nwbfile=nwbfile,
                metadata=metadata,
                data=fiber_data[:end_frame],
                timestamps=timestamps,
                fiber_photometry_series_name=series_name,
                table_region=[channel_ind],
                parent_container="acquisition",
            )

        for channel_ind, channel_name in enumerate(["dff470", "dff405"]):
            column_index = self.column_names.index(channel_name)
            fiber_data = self._processed_data[column_index][self._session_index]
            # Create references for the fiber photometry table
            traces_metadata = deepcopy(
                metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"][channel_ind]
            )
            raw_series_name = traces_metadata["name"]
            # Override name and description for the DF/F series
            updated_name = "DfOverF" + raw_series_name
            traces_metadata["name"] = updated_name
            traces_metadata["description"] = traces_metadata["description"].replace("Raw", "DF/F calculated from")

            raw_response_series = nwbfile.acquisition[raw_series_name]
            raw_response_series_description = raw_response_series.description
            description = raw_response_series_description.replace("Raw", "DF/F calculated from")

            fiber_photometry_table_region = raw_response_series.fiber_photometry_table_region

            response_series = FiberPhotometryResponseSeries(
                name=updated_name,
                description=description,
                data=fiber_data[:end_frame],
                unit="n.a.",
                rate=self._sampling_frequency,
                starting_time=timestamps[0],
                fiber_photometry_table_region=fiber_photometry_table_region,
            )
            ophys_module.add(response_series)
