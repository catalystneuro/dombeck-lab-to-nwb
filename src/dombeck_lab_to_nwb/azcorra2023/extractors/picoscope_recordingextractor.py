from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from spikeinterface import BaseRecording, BaseRecordingSegment


class PicoscopeRecordingExtractor(BaseRecording):
    extractor_name = "PicoscopeRecording"
    mode = "file"
    name = "picoscope"

    def __init__(self, file_path: FilePathType, channel_names: Optional[list] = None):
        """
        Parameters
        ----------

        file_path : FilePathType
            The MAT file from PicoScope.
        channel_names : list, optional
            The names of the channels in the MAT file, by default None.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"The file {file_path} does not exist."

        mat_data = read_mat(file_path)

        channel_names = channel_names or ["A", "B", "C", "D", "E", "F", "G", "H"]
        assert all(
            key in mat_data for key in channel_names
        ), f"The file {file_path} does not contain all the expected keys."

        assert "Tinterval" in mat_data, f"The file {file_path} does not contain a 'Tinterval' key."
        sampling_frequency = 1 / mat_data["Tinterval"]

        data = np.concatenate([mat_data[key][:, np.newaxis] for key in channel_names], axis=1)
        dtype = data.dtype

        super().__init__(sampling_frequency, channel_names, dtype)

        rec_segment = PicoscopeRecordingSegment(sampling_frequency=sampling_frequency, data=data)
        self.add_recording_segment(rec_segment)


class PicoscopeRecordingSegment(BaseRecordingSegment):
    def __init__(self, sampling_frequency: float, t_start: Optional[float] = None, data=None):
        super().__init__(sampling_frequency=sampling_frequency, t_start=t_start)

        self._data = data
        self.num_channels = self._data.shape[1]
        self.num_samples = self._data.shape[0]

    def get_traces(self, start_frame=None, end_frame=None, channel_indices=None):
        if start_frame is None:
            start_frame = 0
        if end_frame is None:
            end_frame = self._data.shape[0]
        if channel_indices is None:
            channel_indices = slice(None)

        return self._data[start_frame:end_frame, channel_indices]

    def get_num_samples(self) -> int:
        return self.num_samples
