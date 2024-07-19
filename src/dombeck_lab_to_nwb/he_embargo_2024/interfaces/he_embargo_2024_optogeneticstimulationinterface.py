from pathlib import Path

import numpy as np
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools.optogenetics import create_optogenetic_stimulation_timeseries
from neuroconv.tools.signal_processing import get_rising_frames_from_ttl
from neuroconv.utils import FilePathType, DeepDict
from pymatreader import read_mat
from pynwb import NWBFile

from dombeck_lab_to_nwb.he_embargo_2024.optogenetic_utils import add_optogenetic_series


class HeEmbargo2024OptogeneticStimulationInterface(BaseTemporalAlignmentInterface):
    """Data interface for HeEmbargo2024 fiber photometry data conversion."""

    display_name = "HeEmbargo2024OptogeneticStimulation"
    associated_suffixes = ".mat"
    info = "Interface for optogenetic stimuliation."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        session_id: str,
        verbose: bool = False,
    ):
        """
        Initialize the HeEmbargo2024OptogeneticStimulationInterface.

        Parameters
        ----------
        file_path : FilePathType
            The path to the .mat file containing the optogenetic stimulation data.
        session_id : str
            The identifier of the session.
        """
        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.verbose = verbose
        processed_data = read_mat(filename=str(file_path))
        if "#subsystem#" not in processed_data:
            raise ValueError(f"Expected '#subsystem#' key in {file_path}.")
        self._processed_data = processed_data["#subsystem#"]["MCOS"][2]
        column_names = processed_data["#subsystem#"]["MCOS"][7]

        filenames = self._processed_data[column_names.index("filename")]
        session_ids = [filename.split(".")[0] for filename in filenames]
        assert session_id in session_ids, f"Expected session_id '{session_id}', found {session_ids}."
        self._session_index = session_ids.index(session_id)
        self._opto_column_index = column_names.index("opto")

        duration_in_ms = self._processed_data[column_names.index("length_stim")][self._session_index]
        self._duration_in_s = duration_in_ms / 1000
        power_in_mW = self._processed_data[column_names.index("power_stim")][self._session_index]
        power_in_W = power_in_mW / 1000
        self._power_in_W = power_in_W
        type_stim = self._processed_data[column_names.index("type_stim")][self._session_index]
        frequency_str, pulse_width_str = type_stim.split("-")
        self._frequency_in_Hz = float(frequency_str.replace("Hz", ""))
        pulse_width_ms = float(pulse_width_str.replace("ms", ""))
        self._pulse_width_in_s = pulse_width_ms / 1000

        self._sampling_frequency = None
        self._timestamps = None

        super().__init__(verbose=verbose, file_path=file_path, session_id=session_id)

    def get_original_timestamps(self) -> np.ndarray:
        opto_stimuli = self._processed_data[self._opto_column_index][self._session_index]
        rising_frames = get_rising_frames_from_ttl(opto_stimuli)
        times = np.arange(opto_stimuli.shape[0]) / self._sampling_frequency
        return times[rising_frames]

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.array(aligned_timestamps)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        # Define default metadata
        metadata["Ophys"]["OptogeneticStimulusSite"] = [
            dict(
                name="OptogeneticStimulusSite",
                device="Laser",
                excitation_lambda=np.nan,
                description="Optogenetic stimulation using a laser.",
            )
        ]
        metadata["Ophys"]["OptogeneticSeries"] = [
            dict(
                name="OptogeneticSeries",
                site="OptogeneticStimulusSite",
                description="The optogenetic series.",
            )
        ]
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        sampling_frequency: float,
        optogenetic_series_name: str = "OptogeneticSeries",
        stub_test: bool = False,
    ) -> None:
        end_frame = 2000 if stub_test else None
        self._sampling_frequency = sampling_frequency
        stimulation_onset_times = self.get_timestamps()
        timestamps, data = create_optogenetic_stimulation_timeseries(
            stimulation_onset_times=stimulation_onset_times,
            duration=self._duration_in_s,  # in seconds
            frequency=self._frequency_in_Hz,  # in Hz
            pulse_width=self._pulse_width_in_s,  # in seconds
            power=self._power_in_W,  # in W
        )
        add_optogenetic_series(
            nwbfile=nwbfile,
            metadata=metadata,
            optogenetic_series_name=optogenetic_series_name,
            data=data[:end_frame],
            timestamps=timestamps[:end_frame],
        )
