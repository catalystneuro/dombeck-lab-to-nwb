from pathlib import Path

import numpy as np
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pynwb import NWBFile, TimeSeries
from pynwb.epoch import TimeIntervals


class NagappanEmbargoBehaviorInterface(BaseTemporalAlignmentInterface):
    """Data interface for custom behavior data from the Two photon experiment."""

    display_name = "NagappanEmbargoBehavior"
    associated_suffixes = (".dat", ".mat")
    info = "Interface for handling data from .dat files."

    _timestamps = None

    def __init__(
        self,
        dat_file_path: FilePathType,
        mat_file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Interface for writing behavior data from .dat file.

        Parameters
        ----------
        dat_file_path : FilePathType
            The path to the .dat file.
        mat_file_path: FilePathType
            The path to the .mat file.
        verbose: bool, default: True
            controls verbosity.
        """

        file_path = Path(dat_file_path)
        if ".dat" not in file_path.suffixes:
            raise IOError(f"The file '{file_path.stem}' is not a .dat file.")
        mat_file_path = Path(mat_file_path)
        if ".mat" not in mat_file_path.suffixes:
            raise IOError(f"The file '{mat_file_path.stem}' is not a .mat file.")

        super().__init__(file_path=file_path, mat_file_path=mat_file_path, verbose=verbose)

    def _read_mat_data(self):
        """Read the data from the .mat file."""
        from pymatreader import read_mat

        mat = read_mat(self.source_data["mat_file_path"])
        if "vars" not in mat:
            raise ValueError("The .mat file does not contain the 'vars' key.")
        return mat["vars"]

    def _read_data(self):
        # Read the data from the .dat file
        mat_data = self._read_mat_data()
        if "si" not in mat_data:
            raise ValueError("The .mat file does not contain the 'si' key.")
        daq_inputs = mat_data["si"]
        with open(self.source_data["file_path"], "rb") as fid:
            data = np.fromfile(fid, dtype=np.float64)

        num_frames = data.shape[0]
        num_inputs = len(daq_inputs) - 1  # last variable (licks) is not included because it is empty.

        data = data[: num_frames - num_frames % num_inputs]
        num_frames = data.shape[0]
        data = data.reshape((num_frames // num_inputs, num_inputs))
        return data

    def get_original_timestamps(self) -> np.ndarray:
        return self._read_data()[:, 0]

    def get_timestamps(self) -> np.ndarray:
        return self.get_original_timestamps() if self._timestamps is None else self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False) -> None:

        data = self._read_data()
        timestamps = self.get_timestamps()

        velocity = data[:, 3]
        velocity_ts = TimeSeries(
            name="Velocity",
            description="The velocity of the animal running on the treadmill.",
            data=velocity if not stub_test else velocity[:1000],
            unit="m/s",
            timestamps=timestamps,
        )
        behavior = get_module(nwbfile, "behavior")
        behavior.add(velocity_ts)

        brakes = data[:, 4]
        unique_brake_values = np.unique(brakes)
        unique_brake_values = unique_brake_values[unique_brake_values != 0]

        intervals = TimeIntervals(name="Brakes", description="The time intervals when the brakes were applied.")
        intervals.add_column(name="brake_value", description="The value of the brake applied.")

        for brake_value in unique_brake_values:
            brake_indices = np.where(brakes == brake_value)[0]
            # Calculate the difference between subsequent elements
            diff = np.diff(brake_indices)

            # Find the indices where the difference is not 1 (breaks in continuity)
            breaks = np.where(diff != 1)[0]

            # The start of each interval is after a break and the end is before a break
            starts = np.insert(brake_indices[breaks + 1], 0, brake_indices[0])
            ends = np.append(brake_indices[breaks], brake_indices[-1])

            # Now you have the start and end of each continuous interval

            for start_index, end_index in zip(starts, ends):
                intervals.add_interval(
                    start=timestamps[start_index],
                    end=timestamps[end_index],
                    brake_value=brake_value,
                )

        behavior.add(intervals)
