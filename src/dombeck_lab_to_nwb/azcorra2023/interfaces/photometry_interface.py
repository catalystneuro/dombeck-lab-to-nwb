from pathlib import Path
from typing import Optional

import numpy as np
from hdmf.common import DynamicTableRegion
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils import FilePathType, load_dict_from_file, dict_deep_update
from pymatreader import read_mat
from pynwb import NWBFile


class Azcorra2023BinnedPhotometryInterface(BaseDataInterface):
    """Data interface for Azcorra2023 fiber photometry data conversion."""

    display_name = "Azcorra2023BinnedPhotometry"
    associated_suffixes = ".mat"
    info = "Interface for fiber photometry data."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = False,
        channel_name_mapping: Optional[dict] = None,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            The path that points to the .mat file containing the binned photometry data.
        """
        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.file_path = file_path
        self.verbose = verbose
        binned_photometry_data = read_mat(filename=str(self.file_path))

        # Blue excitation light (470-nm LED, Thorlabs, M70F3)
        # and purple excitation light (for the isosbestic control) (405-nm LED, Thorlabs, M405FP1)
        # were coupled into the optic fiber such that a power of 0.75 mW emanated from the fiber tip.
        # Then, 470-nm and 405-nm excitation were alternated at 100 Hz using a waveform generator,
        # each filtered with a corresponding filter (Semrock, FF01-406/15-25 and Semrock, FF02-472/30-25)
        # and combined with a dichroic mirror (Chroma Technology, T425lpxr)

        # Green fluorescence was separated from the excitation light by a dichroic mirror (
        # Chroma Technology, T505lpxr) and further filtered (Semrock, FF01-540/50-25) before
        # collection using a GaAsP PMT (H10770PA-40, Hamamatsu; signal amplified using
        # Stanford Research Systems SR570 preamplifier). A PicoScope data acquisition system was
        # used to record and synchronize fluorescence and treadmill velocity at a sampling rate of 4 kHz.

        column_names = binned_photometry_data["#subsystem#"]["MCOS"][7]
        self.column_names = column_names

        channel_names = channel_name_mapping.keys()
        self.channel_name_mapping = channel_name_mapping
        assert all(
            channel_name in column_names for channel_name in channel_names
        ), f"The channel names {channel_names} are not in the file {file_path}."

        self._photometry_data = binned_photometry_data["#subsystem#"]["MCOS"][2]

        assert "Depth" in column_names, f"The column 'Depth' is not in the file {file_path}."
        depth_index = column_names.index("Depth")
        self.depths = self._photometry_data[depth_index]
        self.depth_ids = binned_photometry_data["#subsystem#"]["MCOS"][5]

        # E.g. 'VGlut-A997-20200205-0001'
        # Identifies which row to load from the binned photometry data
        # session_ids_from_photometry = binned_photometry_data["#subsystem#"]["MCOS"][5]
        # session_id = session_id or session_ids_from_photometry[0]
        # assert session_id in session_ids_from_photometry, f"The session identifier ({session_id}) is not in the file {file_path}."
        #
        # photometry_values = binned_photometry_data["#subsystem#"]["MCOS"][2]
        # channel_index = column_names.index(channel_name)
        # row_index = session_ids_from_photometry.index(session_id)
        # self._photometry_data = photometry_values[channel_index][row_index]
        #
        # assert "Depth" in column_names, f"The column 'Depth' is not in the file {file_path}."
        # depth_index = column_names.index("Depth")
        # self._depth = photometry_values[depth_index][row_index]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
    ) -> None:
        """
        Add the binned photometry data to the NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the binned photometry data to.
        metadata : dict
            The metadata for the binned photometry data.
        """
        from ndx_photometry import (
            ExcitationSourcesTable,
            PhotodetectorsTable,
            FluorophoresTable,
            FibersTable,
            FiberPhotometry,
            FiberPhotometryResponseSeries,
        )

        fiber_photometry_metadata = metadata["FiberPhotometry"]

        excitation_sources_metadata = fiber_photometry_metadata["ExcitationSources"]
        excitation_sources_table = ExcitationSourcesTable(description="excitation sources table")
        for excitation_source_metadata in excitation_sources_metadata:
            excitation_source_metadata.pop("name")
            excitation_sources_table.add_row(**excitation_source_metadata)

        photodetectors_metadata = fiber_photometry_metadata["Photodetectors"]
        photodetectors_table = PhotodetectorsTable(description="photodetectors table")
        for photodetector_metadata in photodetectors_metadata:
            photodetector_metadata.pop("name")
            photodetectors_table.add_row(**photodetector_metadata)

        # Create a Fibers table, and add one (or many) fiber
        fibers_metadata = fiber_photometry_metadata["Fibers"]
        fibers_table = FibersTable(description="fibers table")
        for fiber_metadata in fibers_metadata:
            fiber_metadata.pop("name")
            fibers_table.add_row(
                **fiber_metadata,
                location="SNc" if self.depths[0] > 3.0 else "striatum",  # TBD
            )

        # Create a Fluorophores table, and add one (or many) fluorophore
        fluorophores_table = FluorophoresTable(description="fluorophores")
        fluorophores_table.add_row(
            label="AAV-GCaMP6f",
            location="SNc",
        )

        # Here we add the metadata tables to the metadata section
        nwbfile.add_lab_meta_data(
            FiberPhotometry(
                fibers=fibers_table,
                excitation_sources=excitation_sources_table,
                photodetectors=photodetectors_table,
                fluorophores=fluorophores_table,
            )
        )

        for channel_name, series_name in self.channel_name_mapping.items():
            photometry_response_series_metadata = next(
                fiber
                for fiber in fiber_photometry_metadata["FiberPhotometryResponseSeries"]
                if fiber["name"] == series_name
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
                name="fluorophore", description="fluorophore", data=[0], table=fluorophores_table
            )

            channel_index = self.column_names.index(channel_name)
            for depth_index, depth in enumerate(self.depths):
                depth_id = self.depth_ids[depth_index].split("-")[-1]

                description = photometry_response_series_metadata["description"]
                description += " at depth " + str(np.round(depth / 100, 2)) + " meters."

                response_series = FiberPhotometryResponseSeries(
                    name=series_name + depth_id,
                    description=description,
                    data=self._photometry_data[channel_index][depth_index],
                    unit="a.u.",
                    rate=100.0,
                    fiber=fiber_ref,
                    excitation_source=excitation_ref,
                    photodetector=photodetector_ref,
                    fluorophore=fluorophore_ref,
                )

                nwbfile.add_acquisition(response_series)


#
# interface = Azcorra2023BinnedPhotometryInterface(
#     file_path="/Volumes/LaCie/CN_GCP/Dombeck/2020-02-26 Vglut2/VGlut-A997/T_Binned405_VGlut-A997-20200205.mat",
#     channel_name_mapping=dict(
#         chGreen="FiberPhotometryResponseSeriesGreen",
#         chGreen405="FiberPhotometryResponseSeriesGreenIsosbestic",
#         chRed="FiberPhotometryResponseSeriesRed",
#         chRed405="FiberPhotometryResponseSeriesRedIsosbestic",
#     ),
# )
# metadata = interface.get_metadata()
# editable = load_dict_from_file(Path(__file__).parent.parent / "metadata" / "fiber_photometry_metadata.yaml")
# metadata = dict_deep_update(metadata, editable)
# metadata["NWBFile"]["session_start_time"] = "2020-02-05T12:00:00-06:00"
# interface.run_conversion(metadata=metadata, nwbfile_path="test2.nwb", overwrite=True)
