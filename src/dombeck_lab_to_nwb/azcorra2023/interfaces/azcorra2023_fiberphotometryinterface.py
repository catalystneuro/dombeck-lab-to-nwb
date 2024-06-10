from pathlib import Path
from typing import Optional

import numpy as np
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import NWBFile

from dombeck_lab_to_nwb.azcorra2023.photometry_utils.add_fiber_photometry import add_fiber_photometry_series


class Azcorra2023FiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """Data interface for Azcorra2023 fiber photometry data conversion."""

    display_name = "Azcorra2023BinnedPhotometry"
    associated_suffixes = ".mat"
    info = "Interface for fiber photometry data."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        session_id: str,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            The path that points to the .mat file containing the binned photometry data.
        session_id : str
            The session id to extract from the .mat file.
        """
        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.file_path = file_path
        self.verbose = verbose
        binned_photometry_data = read_mat(filename=str(self.file_path))
        self._photometry_data = binned_photometry_data["#subsystem#"]["MCOS"][2]
        self._sampling_frequency = 100.0
        self._timestamps = None

        depth_ids = binned_photometry_data["#subsystem#"]["MCOS"][5]
        depth_ids = [depth_ids] if isinstance(depth_ids, str) else depth_ids
        depth_index = [i for i, depth_id in enumerate(depth_ids) if session_id in depth_id]
        assert len(depth_index), f"Expected match for session_id '{session_id}', found 0 in {depth_ids}."
        depth_index = depth_index[0]

        self.depth_ids = depth_ids
        self.depth_index = depth_index

        self.column_names = binned_photometry_data["#subsystem#"]["MCOS"][7]

    def get_original_timestamps(self) -> np.ndarray:
        binned_photometry_data = read_mat(filename=str(self.file_path))["#subsystem#"]["MCOS"][2]
        channel_index = self.column_names.index("chMov")
        data = binned_photometry_data[channel_index]
        if len(self.depth_ids) > 1:
            data = data[self.depth_index]
        num_frames = len(data)
        return np.arange(num_frames) / self._sampling_frequency

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        if stub_test:
            return timestamps[:6000]
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.array(aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        trace_name_to_channel_id_mapping: dict,
        stub_test: Optional[bool] = False,
    ) -> None:
        """
        Add the raw fiber photometry data to the NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the raw photometry data to.
        metadata : dict
            The metadata for the photometry data.
        trace_name_to_channel_id_mapping: dict
            A dictionary that maps the trace name to the channel ids. (e.g. {"FiberPhotometryResponseSeries": ["chRed", "chGreen"]})
        stub_test : bool, optional
            Whether to run the conversion as a stub test by writing 1-minute of data, by default False.
        """

        for series_ind, (series_name, channel_names) in enumerate(trace_name_to_channel_id_mapping.items()):
            assert all(
                channel_name in self.column_names for channel_name in channel_names
            ), f"Not all channel names are in {self.source_data['file_path']}."

            if series_name in nwbfile.acquisition:
                raise ValueError(f"The fiber photometry series '{series_name}' already exists in the NWBfile.")

            squeeze = False
            if len(channel_names) == 1:
                table_region = [series_ind]
                squeeze = True
            elif len(channel_names) == 2:
                table_region_ind = series_ind * len(trace_name_to_channel_id_mapping.keys())
                table_region = [table_region_ind, table_region_ind + 1]
            else:
                raise ValueError(f"Expected 1 or 2 channel names, found {len(channel_names)}.")

            data_to_add = []
            for channel_name in channel_names:
                channel_index = self.column_names.index(channel_name)
                data = self._photometry_data[channel_index]
                if len(self.depth_ids) > 1:
                    data = data[self.depth_index]
                data_to_add.append(data if not stub_test else data[:6000])

            fiber_data = np.column_stack(data_to_add)
            timestamps = self.get_timestamps(stub_test=stub_test)
            add_fiber_photometry_series(
                nwbfile=nwbfile,
                metadata=metadata,
                data=fiber_data if not squeeze else fiber_data.squeeze(axis=1),
                timestamps=timestamps,
                fiber_photometry_series_name=series_name,
                table_region=table_region,
                parent_container="acquisition",
            )
