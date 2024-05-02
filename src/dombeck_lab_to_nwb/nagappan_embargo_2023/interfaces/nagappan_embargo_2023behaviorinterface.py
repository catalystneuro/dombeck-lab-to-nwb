from pathlib import Path

import numpy as np
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.tools.signal_processing import get_rising_frames_from_ttl
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
        daq_dat_file_path: FilePathType,
        mat_file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Interface for writing behavior data from .dat file.

        Parameters
        ----------
        dat_file_path : FilePathType
            The path to the .dat file.
        daq_dat_file_path : FilePathType
            The path to the .dat file containing the DAQ data.
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
        if ".dat" not in daq_dat_file_path.suffixes:
            raise IOError(f"The file '{daq_dat_file_path.stem}' is not a .dat file.")

        super().__init__(
            file_path=file_path, daq_file_path=daq_dat_file_path, mat_file_path=mat_file_path, verbose=verbose
        )

        self._vars = self._read_mat_data()
        self._sampling_frequency = self._vars["daq"]["sampleRate"]
        self._num_daq_channels = self._vars["si"]["licks"]

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

    def _read_daq_data(self):
        with open(self.source_data["daq_file_path"], "rb") as f:
            file_data = f.read()

        # Initialize empty array to hold individual bits
        bits = np.zeros(len(file_data) * 8, dtype=np.uint8)

        # Loop over each byte
        for i, byte in enumerate(file_data):
            # Loop over each bit in the byte
            for j in range(8):
                # Extract bit from byte
                bit = (byte >> j) & 1
                # Store bit in the array
                bits[i * 8 + j] = bit

        num_bits = bits.shape[0]
        data_bits = bits[: num_bits - num_bits % self._num_daq_channels]
        num_bits = data_bits.shape[0]
        data_bits = data_bits.reshape((num_bits // self._num_daq_channels, self._num_daq_channels))
        return data_bits

    def get_aligned_times_from_ttl(self) -> [np.ndarray, np.ndarray]:
        """Returns the aligned imaging and camera times based on the TTL pulses."""

        events_data = self._read_data()
        # time elapsed per loop based on CPU clock (logged every ~30ms)
        times_from_cpu_clock = events_data[:, 0]
        # time elapsed per loop based on DAQ clock (logged every ~30ms)
        times_from_daq_clock = np.cumsum(events_data[:, 1]) / self._sampling_frequency

        daq_data = self._read_daq_data()
        num_daq_samples = daq_data[:, 0].shape[0]
        times_from_daq = (np.arange(1, num_daq_samples + 1) / self._sampling_frequency) - (
            times_from_daq_clock[0] - times_from_cpu_clock[0]
        )

        rising_frames_from_imaging = np.where((daq_data[1:, 1] > 0.8) & (daq_data[:-1, 1] < 0.1))[0]
        rising_frames_from_imaging = rising_frames_from_imaging + 1  # first high point of imaging pulse

        # get frame times
        frame_times = times_from_daq[rising_frames_from_imaging]  # time of first point of the high pulse
        # correct frame_times to center of imaging frame rather than the beginning
        dt = np.mean(np.diff(frame_times))
        imaging_times = frame_times + dt / 2

        rising_frames_from_camera = get_rising_frames_from_ttl(
            trace=daq_data[:, 2],
        )
        camera_times = times_from_daq[rising_frames_from_camera]

        return imaging_times, camera_times

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
                    start_time=timestamps[start_index],
                    stop_time=timestamps[end_index],
                    brake_value=brake_value,
                )

        behavior.add(intervals)
