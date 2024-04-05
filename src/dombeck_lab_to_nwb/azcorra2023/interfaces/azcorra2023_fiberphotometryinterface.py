from pathlib import Path
from typing import Optional

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import NWBFile


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
        assert session_id in depth_ids, f"{session_id} is not in the file {file_path}."
        depth_index = depth_ids.index(session_id)
        self.depth_index = depth_index

        self.column_names = binned_photometry_data["#subsystem#"]["MCOS"][7]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_name_to_photometry_series_name_mapping: dict,
        fiber_depth_mapping: Optional[dict] = None,
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
        fiber_depth_mapping: dict
            A dictionary that maps the fiber names to the depths in mm.
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

        fiber_photometry_metadata = metadata["Ophys"]["FiberPhotometry"]
        traces_metadata = fiber_photometry_metadata["FiberPhotometryResponseSeries"]
        traces_metadata_to_add = [
            trace
            for trace in traces_metadata
            if trace["name"] in channel_name_to_photometry_series_name_mapping.values()
        ]

        excitation_sources_metadata = fiber_photometry_metadata["ExcitationSources"]
        excitation_source_ind = set([trace["excitation_source"] for trace in traces_metadata_to_add])
        excitation_sources_to_add = [excitation_sources_metadata[ind] for ind in excitation_source_ind]

        excitation_sources_description = (
            "Blue excitation light (470 nm LED, Thorlabs, M70F3) and purple excitation light (for the isosbestic "
            "control) (405 nm LED, Thorlabs, M405FP1) were coupled into the optic fiber such that a power of 0.75 mW "
            "emanated from the fiber tip. Then, 470 nm and 405 nm excitation were alternated at 100 Hz using a "
            "waveform generator, each filtered with a corresponding filter (Semrock, FF01-406/15-25 and Semrock, "
            "FF02-472/30-25) and combined with a dichroic mirror (Chroma Technology, T425lpxr)."
        )
        excitation_sources_table = ExcitationSourcesTable(description=excitation_sources_description)
        for excitation_source_metadata in excitation_sources_to_add:
            excitation_source_metadata.pop("name")
            excitation_sources_table.add_row(**excitation_source_metadata)

        photodetectors_metadata = fiber_photometry_metadata["Photodetectors"]
        photodetectors_description = (
            "Green fluorescence was separated from the excitation light by a dichroic mirror (Chroma Technology, "
            "T505lpxr) and further filtered (Semrock, FF01-540/50-25) before collection using a GaAsP PMT "
            "(H10770PA-40, Hamamatsu; signal amplified using Stanford Research Systems SR570 preamplifier)."
        )
        photodetectors_table = PhotodetectorsTable(description=photodetectors_description)
        for photodetector_metadata in photodetectors_metadata:
            photodetector_metadata.pop("name")
            photodetectors_table.add_row(**photodetector_metadata)

        fibers_metadata = fiber_photometry_metadata["Fibers"]
        fibers_ind = set([trace["fiber"] for trace in traces_metadata_to_add])
        fibers_to_add = [fibers_metadata[ind] for ind in fibers_ind]
        fiber_names = [fiber_metadata["name"] for fiber_metadata in fibers_to_add]
        fibers_description = (
            "One or two optical fibers (200-μm diameter, 0.57 NA, Doric MFP_200/230/900-0.57_1.5m_FC-FLT_LAF) were "
            "lowered slowly (5 μm s−1) using a micromanipulator (Sutter Instrument, MP285) into the brain to various "
            "depths measured from the dura surface. In the striatum, recording depths ranged from 1.6 mm to 4.1 mm; "
            "in SNc, depths ranged from 3.5 mm to 4.5 mm. Recordings started at 1.6 mm in striatum and 3.5 mm in SNc, "
            "but if no ΔF/F transients were detected at those depths, the fiber was moved down in increments of"
            "0.25–0.5 mm in striatum or 0.15–0.2 mm in SNc, until transients were detected."
        )
        fibers_table = FibersTable(description=fibers_description)
        fibers_table.add_column(name="depth", description="The depth of fiber in the unit of meters.")

        for fiber_metadata in fibers_to_add:
            fiber_name = fiber_metadata.pop("name")
            if fiber_name in self.column_names:
                fiber_depth_in_mm = fiber_depth_mapping[fiber_name]
                location = "SNc" if fiber_depth_in_mm > 3.0 else "Str"  # striatum
                fibers_table.add_row(
                    **fiber_metadata,
                    depth=fiber_depth_in_mm / 1000,
                    location=location,
                )

        fluorophores_metadata = fiber_photometry_metadata["Fluorophores"]
        fluorophores_ind = set([trace["fluorophore"] for trace in traces_metadata_to_add])
        fluorophores_to_add = [fluorophores_metadata[ind] for ind in fluorophores_ind]

        fluorophores_description = (
            "GCaMP6f was used as the fluorophore in SNc (3.25 mm caudal, +1.55 mm lateral) at four "
            "depths (−3.8, −4.1, −4.4 and −4.7 mm) ventral from dura surface, 0.1 μl per depth)."
        )
        fluorophores_table = FluorophoresTable(description=fluorophores_description)
        for fluorophore_metadata in fluorophores_to_add:
            fluorophore_metadata.pop("name")
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

        for channel_name, series_name in channel_name_to_photometry_series_name_mapping.items():
            if series_name in nwbfile.acquisition:
                raise ValueError(f"The fiber photometry series {series_name} already exists in the NWBfile.")

            # Get photometry response series metadata
            photometry_response_series_metadata = next(
                series_metadata for series_metadata in traces_metadata_to_add if series_metadata["name"] == series_name
            )

            # Create DynamicTableRegion referencing the correct rows for each table
            fiber_ref = fibers_table.create_fiber_region(
                region=[photometry_response_series_metadata["fiber"]],
                description="source fiber",
            )
            excitation_ref = excitation_sources_table.create_excitation_source_region(
                region=[photometry_response_series_metadata["excitation_source"]],
                description="excitation sources",
            )
            photodetector_ref = photodetectors_table.create_photodetector_region(
                region=[0],
                description="photodetector",
            )
            fluorophore_ref = fluorophores_table.create_fluorophore_region(
                region=[photometry_response_series_metadata["fluorophore"]],
                description="fluorophore",
            )

            description = photometry_response_series_metadata["description"]
            # Add more information about the fiber depth
            fiber_name = fiber_names[photometry_response_series_metadata["fiber"]]
            fiber_depth_in_mm = fiber_depth_mapping[fiber_name]
            description += f" obtained at {fiber_depth_in_mm / 1000} meters depth."

            channel_index = self.column_names.index(channel_name)
            data = self._photometry_data[channel_index][self.depth_index]
            response_series = FiberPhotometryResponseSeries(
                name=series_name,
                description=description,
                data=data if not stub_test else data[:6000],
                unit="F",
                rate=100.0,
                fibers=fiber_ref,
                excitation_sources=excitation_ref,
                photodetectors=photodetector_ref,
                fluorophores=fluorophore_ref,
            )

            # Add raw fiber photometry series to acquisition module
            nwbfile.add_acquisition(response_series)
