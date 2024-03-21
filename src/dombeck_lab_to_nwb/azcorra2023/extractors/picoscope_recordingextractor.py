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

    def __init__(self, file_path: FilePathType, channel_ids: list):
        """
        Recording extractor for analog signals from PicoScope.

        Parameters
        ----------

        file_path : FilePathType
            The MAT file from PicoScope.
        channel_ids : list
            The channels to load from the MAT file.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"The file {file_path} does not exist."

        mat_data = read_mat(file_path)

        # The channel names are single letter variables in the MAT file
        assert all(
            [chan in list(mat_data.keys()) for chan in channel_ids]
        ), "The provided 'channel_ids' are not all present in the MAT file."
        data = np.concatenate([mat_data[chan][:, np.newaxis] for chan in channel_ids], axis=1)

        assert "Tinterval" in mat_data, f"The file {file_path} does not contain a 'Tinterval' key."
        sampling_frequency = 1 / mat_data["Tinterval"]

        dtype = data.dtype

        super().__init__(sampling_frequency, channel_ids, dtype)

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
