from pathlib import Path

import numpy as np
from ndx_events import TtlTypesTable, TtlsTable
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools.signal_processing import get_rising_frames_from_ttl
from neuroconv.utils import FilePathType
from pynwb import NWBFile


class NagappanEmbargoTtlInterface(BaseTemporalAlignmentInterface):
    """Data interface for TTL data from the Two photon experiment."""

    display_name = "NagappanEmbargoTTL"
    associated_suffixes = ".dat"
    info = "Interface for handling data from .dat files."

    _timestamps = None

    def __init__(
        self,
        dat_file_path: FilePathType,
        mat_file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Interface for writing TTL data from .dat file.

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

        self._vars = self._read_mat_data()
        self._sampling_frequency = self._vars["daq"]["sampleRate"]
        self._num_daq_channels = self._vars["si"]["licks"]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["Events"] = dict(
            TtlTypesTable=dict(
                description="Contains the type of TTL events (imaging, camera).",  # todo update description
            ),
            TtlsTable=dict(
                description="Contains the imaging and camera pulses.",
            ),
        )

        return metadata

    def _read_mat_data(self):
        """Read the data from the .mat file."""
        from pymatreader import read_mat

        mat = read_mat(self.source_data["mat_file_path"])
        if "vars" not in mat:
            raise ValueError("The .mat file does not contain the 'vars' key.")
        return mat["vars"]

    def _read_data(self):
        with open(self.source_data["file_path"], "rb") as f:
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

    def get_original_timestamps(self) -> np.ndarray:
        data = self._read_data()
        num_frames = data[:, 0].shape[0]
        cumsum_frames = np.cumsum(np.ones(num_frames) / self._sampling_frequency)

        timestamps = cumsum_frames - cumsum_frames[0]
        return timestamps

    def get_timestamps(self) -> np.ndarray:
        return self.get_original_timestamps() if self._timestamps is None else self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = aligned_timestamps

    def get_event_times_from_ttl(self, channel_index: int = 0) -> np.ndarray:
        """
        Return the start of event times from the rising part of TTL pulses on one of the DAQ channels.

        Parameters
        ----------
        channel_index : int
            The index of the DAQ channel in the .dat file.

        Returns
        -------
        rising_times : numpy.ndarray
            The times of the rising TTL pulses.
        """
        # TODO: consider RAM cost of these operations and implement safer buffering version
        data = self._read_data()
        rising_frames = get_rising_frames_from_ttl(
            trace=data[:, channel_index],
        )

        timestamps = self.get_timestamps()
        rising_times = timestamps[rising_frames]

        return rising_times

    def add_to_nwbfile(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, channel_name_to_daq_input_mapping: dict = None
    ) -> None:

        channel_name_to_daq_input_mapping = channel_name_to_daq_input_mapping or dict(imaging=1, camera=2)

        events_metadata = metadata["Events"]
        ttl_types_table = TtlTypesTable(**events_metadata["TtlTypesTable"])

        for channel_name, daq_input_value in channel_name_to_daq_input_mapping.items():
            ttl_types_table.add_row(
                event_name=channel_name,
                event_type_description=f"The times when the {channel_name} TTL was on.",
                pulse_value=daq_input_value,
            )

        ttls_table = TtlsTable(**events_metadata["TtlsTable"], target_tables={"ttl_type": ttl_types_table})

        for ttl_ind, (channel_name, daq_input_value) in enumerate(channel_name_to_daq_input_mapping.items()):

            event_times = self.get_event_times_from_ttl(channel_index=daq_input_value)
            for timestamp in event_times:
                ttls_table.add_row(
                    timestamp=timestamp,
                    ttl_type=ttl_ind,  # NOT the pulse value, but a row index into the ttl_types_table
                )

        nwbfile.add_acquisition(ttl_types_table)
        nwbfile.add_acquisition(ttls_table)
