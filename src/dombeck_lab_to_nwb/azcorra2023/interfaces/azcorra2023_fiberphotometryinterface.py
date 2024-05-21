from pathlib import Path
from typing import Optional

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import NWBFile

from dombeck_lab_to_nwb.azcorra2023.photometry_utils.add_fiber_photometry import add_fiber_photometry_series


class Azcorra2023FiberPhotometryInterface(BaseDataInterface):
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

        depth_ids = binned_photometry_data["#subsystem#"]["MCOS"][5]
        depth_ids = [depth_ids] if isinstance(depth_ids, str) else depth_ids
        depth_index = [i for i, depth_id in enumerate(depth_ids) if session_id in depth_id]
        assert len(depth_index), f"Expected match for session_id '{session_id}', found 0 in {depth_ids}."
        depth_index = depth_index[0]

        self.depth_ids = depth_ids
        self.depth_index = depth_index

        self.column_names = binned_photometry_data["#subsystem#"]["MCOS"][7]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_name_to_photometry_series_name_mapping: dict,
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
        channel_name_to_photometry_series_name_mapping: dict
            A dictionary that maps the channel names in the .mat file to the names of the photometry response series.
        stub_test : bool, optional
            Whether to run the conversion as a stub test by writing 1-minute of data, by default False.
        """

        channel_names = list(channel_name_to_photometry_series_name_mapping.keys())
        assert all(
            channel_name in self.column_names for channel_name in channel_names
        ), f"Not all channel names are in {self.source_data['file_path']}."

        for series_ind, (channel_name, series_name) in enumerate(
            channel_name_to_photometry_series_name_mapping.items()
        ):
            if series_name in nwbfile.acquisition:
                raise ValueError(f"The fiber photometry series {series_name} already exists in the NWBfile.")

            channel_index = self.column_names.index(channel_name)

            data = self._photometry_data[channel_index]
            if len(self.depth_ids) > 1:
                data = data[self.depth_index]

            add_fiber_photometry_series(
                nwbfile=nwbfile,
                metadata=metadata,
                data=data if not stub_test else data[:6000],
                rate=100.0,
                fiber_photometry_series_name=series_name,
                table_region_ind=series_ind,
                parent_container="acquisition",
            )
