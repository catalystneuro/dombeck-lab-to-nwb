"""Primary NWBConverter class for this dataset."""
from typing import Optional

from neuroconv import NWBConverter
from neuroconv.tools.nwb_helpers import get_default_backend_configuration, configure_backend
from pynwb import NWBFile

from dombeck_lab_to_nwb.azcorra2023.interfaces import (
    PicoscopeTimeSeriesInterface,
    PicoscopeTtlInterface,
    Azcorra2023FiberPhotometryInterface,
    Azcorra2023ProcessedFiberPhotometryInterface,
)


class Azcorra2023NWBConverter(NWBConverter):
    """Primary conversion class for the Azcorra2023 Fiber photometry dataset."""

    data_interface_classes = dict(
        PicoScopeTimeSeries=PicoscopeTimeSeriesInterface,
        PicoScopeTTLs=PicoscopeTtlInterface,
        FiberPhotometry=Azcorra2023FiberPhotometryInterface,
        ProcessedFiberPhotometry=Azcorra2023ProcessedFiberPhotometryInterface,
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    def temporally_align_data_interfaces(self):
        """
        Align the starting time of processed fiber photometry data after cropping.
        """
        processed_interface = self.data_interface_objects["ProcessedFiberPhotometry"]
        aligned_starting_time = processed_interface.get_starting_time()
        processed_interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)
