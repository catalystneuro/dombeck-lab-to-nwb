from pathlib import Path
from typing import Optional

from neuroconv.utils import FilePathType
from pymatreader import read_mat
from spikeinterface import BaseRecording, BaseRecordingSegment


class PicoscopeRecordingExtractor(BaseRecording):
    extractor_name = "PicoscopeRecording"
    mode = "file"
    name = "picoscope"

    def __init__(self, file_path: FilePathType, channel_name: str):
        """
        Recording extractor for analog signals from PicoScope.

        Parameters
        ----------

        file_path : FilePathType
            The MAT file from PicoScope.
        channel_name : str
            The channel to load from the MAT file.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"The file {file_path} does not exist."

        mat_data = read_mat(file_path)

        # The channel names are single letter variables in the MAT file
        assert channel_name in list(mat_data.keys()), f"The provided '{channel_name}' is not in the MAT file."

        data = mat_data[channel_name]
        assert "Tinterval" in mat_data, f"The file {file_path} does not contain a 'Tinterval' key."
        sampling_frequency = 1 / mat_data["Tinterval"]

        dtype = data.dtype
        channel_ids = [channel_name]

        super().__init__(sampling_frequency, channel_ids, dtype)

        rec_segment = PicoscopeRecordingSegment(sampling_frequency=sampling_frequency, data=data)
        self.add_recording_segment(rec_segment)


class PicoscopeRecordingSegment(BaseRecordingSegment):
    def __init__(self, sampling_frequency: float, t_start: Optional[float] = None, data=None):
        super().__init__(sampling_frequency=sampling_frequency, t_start=t_start)

        self._data = data
        self.num_channels = 1
        self.num_samples = len(self._data)

    def get_traces(self, start_frame=None, end_frame=None, channel_indices=None):
        if start_frame is None:
            start_frame = 0
        if end_frame is None:
            end_frame = self._data.shape[0]

        return self._data[start_frame:end_frame]

    def get_num_samples(self) -> int:
        return self.num_samples
