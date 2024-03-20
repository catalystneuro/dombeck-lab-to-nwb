from pathlib import Path
from typing import Optional

from hdmf.backends.hdf5 import H5DataIO
from hdmf.common import DynamicTableRegion
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.ophys import Fluorescence


class Azcorra2023FiberPhotometryInterface(BaseDataInterface):
    """Data interface for Azcorra2023 fiber photometry data conversion."""

    display_name = "Azcorra2023BinnedPhotometry"
    associated_suffixes = ".mat"
    info = "Interface for fiber photometry data."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        session_id: str,
        fiber_depth_red: Optional[float] = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            The path that points to the .mat file containing the binned photometry data.
        session_id : str
            The session id to extract from the .mat file.
        fiber_depth_red : float, optional
            The depth of the red fiber in the unit of millimeters, by default None.
        """
        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.file_path = file_path
        self.verbose = verbose
        binned_photometry_data = read_mat(filename=str(self.file_path))
        self._photometry_data = binned_photometry_data["#subsystem#"]["MCOS"][2]

        depth_ids = binned_photometry_data["#subsystem#"]["MCOS"][5]
        assert session_id in depth_ids, f"{session_id} is not in the file {file_path}."
        depth_index = depth_ids.index(session_id)
        self.depth_index = depth_index

        self.column_names = binned_photometry_data["#subsystem#"]["MCOS"][7]

        # Record the depth of the fiber
        # The script that used to create the concatenated and binned photometry data only
        # records the depth of the green fiber.
        assert "Depth" in self.column_names, f"The column 'Depth' is not in the file {file_path}."
        fiber_depth_green_in_mm = self._photometry_data[self.column_names.index("Depth")][depth_index]
        self.fiber_depth = dict(chGreen=fiber_depth_green_in_mm)
        if fiber_depth_red is not None:
            self.fiber_depth.update(chRed=fiber_depth_red)

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
        from ndx_photometry import (
            ExcitationSourcesTable,
            PhotodetectorsTable,
            FluorophoresTable,
            FibersTable,
            FiberPhotometry,
            FiberPhotometryResponseSeries,
        )

        channel_names = list(channel_name_to_photometry_series_name_mapping.keys())
        assert all(
            channel_name in self.column_names for channel_name in channel_names
        ), f"Not all channel names are in {self.source_data['file_path']}."

        fiber_photometry_metadata = metadata["FiberPhotometry"]

        excitation_sources_metadata = fiber_photometry_metadata["ExcitationSources"]
        excitation_sources_description = excitation_sources_metadata.pop("description")
        excitation_sources_table = ExcitationSourcesTable(description=excitation_sources_description)
        for excitation_source_metadata in excitation_sources_metadata.values():
            excitation_sources_table.add_row(**excitation_source_metadata)

        photodetectors_metadata = fiber_photometry_metadata["Photodetectors"]
        photodetectors_description = photodetectors_metadata.pop("description")
        photodetectors_table = PhotodetectorsTable(description=photodetectors_description)
        for photodetector_metadata in photodetectors_metadata.values():
            photodetectors_table.add_row(**photodetector_metadata)

        fibers_metadata = fiber_photometry_metadata["Fibers"]
        fibers_description = fibers_metadata.pop("description")
        fibers_table = FibersTable(description=fibers_description)
        fibers_table.add_column(name="depth", description="The depth of fiber in the unit of meters.")

        for fiber_name, fiber_metadata in fibers_metadata.items():
            if fiber_name in self.column_names:
                fiber_depth_in_mm = self.fiber_depth[fiber_name]
                location = "SNc" if fiber_depth_in_mm > 3.0 else "striatum"
                fibers_table.add_row(
                    **fiber_metadata,
                    depth=fiber_depth_in_mm / 1000,
                    location=location,
                )

        fluorophores_metadata = fiber_photometry_metadata["Fluorophores"]
        fluorophores_description = fluorophores_metadata.pop("description")
        fluorophores_table = FluorophoresTable(description=fluorophores_description)
        for fluorophore_metadata in fluorophores_metadata.values():
            fluorophores_table.add_row(**fluorophore_metadata)

        # Here we add the metadata tables to the metadata section
        nwbfile.add_lab_meta_data(
            FiberPhotometry(
                fibers=fibers_table,
                excitation_sources=excitation_sources_table,
                photodetectors=photodetectors_table,
                fluorophores=fluorophores_table,
            )
        )

        ophys_module = get_module(
            nwbfile=nwbfile,
            name="ophys",
            description=f"Fiber photometry data from {location}.",
        )

        for channel_name, series_name in channel_name_to_photometry_series_name_mapping.items():
            # Get photometry response series metadata
            photometry_response_series_metadata = next(
                series_metadata
                for series_metadata in fiber_photometry_metadata["FiberPhotometryResponseSeries"]
                if series_metadata["name"] == series_name
            )

            fiber_ref = DynamicTableRegion(
                name="fiber",
                description="source fiber",
                data=[photometry_response_series_metadata["fiber"]],
                table=fibers_table,
            )
            excitation_ref = DynamicTableRegion(
                name="excitation_source",
                description="excitation sources",
                data=[photometry_response_series_metadata["excitation_source"]],
                table=excitation_sources_table,
            )
            photodetector_ref = DynamicTableRegion(
                name="photodetector", description="photodetector", data=[0], table=excitation_sources_table
            )
            fluorophore_ref = DynamicTableRegion(
                name="fluorophore",
                description="fluorophore",
                data=[photometry_response_series_metadata["fluorophore"]],
                table=fluorophores_table,
            )

            channel_index = self.column_names.index(channel_name)
            description = photometry_response_series_metadata["description"]
            # add more information about the fiber depth
            # could be changed to reference name instead
            fiber_name = list(fibers_metadata.keys())[photometry_response_series_metadata["fiber"]]
            fiber_depth_in_mm = self.fiber_depth[fiber_name]
            description += f" obtained at {fiber_depth_in_mm / 1000} meters depth."

            data = self._photometry_data[channel_index][self.depth_index]
            response_series = FiberPhotometryResponseSeries(
                name=series_name,
                description=description,
                data=H5DataIO(data, compression=True) if not stub_test else data[:6000],
                unit="Volts",  # TODO: double check units
                rate=100.0,
                fiber=fiber_ref,
                excitation_source=excitation_ref,
                photodetector=photodetector_ref,
                fluorophore=fluorophore_ref,
            )

            ophys_module.add(response_series)
