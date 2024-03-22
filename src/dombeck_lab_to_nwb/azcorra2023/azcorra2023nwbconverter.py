"""Primary NWBConverter class for this dataset."""
from typing import Optional

from neuroconv import NWBConverter
from neuroconv.tools.nwb_helpers import get_default_backend_configuration, configure_backend
from pynwb import NWBFile

from dombeck_lab_to_nwb.azcorra2023.interfaces import (
    PicoscopeTimeSeriesInterface,
    PicoscopeEventInterface,
    Azcorra2023FiberPhotometryInterface,
)


class Azcorra2023NWBConverter(NWBConverter):
    """Primary conversion class for the Azcorra2023 Fiber photometry dataset."""

    data_interface_classes = dict(
        PicoScopeTimeSeries=PicoscopeTimeSeriesInterface,
        Events=PicoscopeEventInterface,
        FiberPhotometry=Azcorra2023FiberPhotometryInterface,
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)
