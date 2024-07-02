"""Primary NWBConverter class for this dataset."""
from typing import Optional
from pynwb import NWBFile
from neuroconv import NWBConverter
from neuroconv.tools.nwb_helpers import get_default_backend_configuration, configure_backend

from dombeck_lab_to_nwb.he_embargo_2024.interfaces import AxonBinaryTimeSeriesInterface


class HeEmbargo2023NWBConverter(NWBConverter):
    """Primary conversion class for the Fiber Photometry experiment from Elena He from Dombeck lab."""

    data_interface_classes = dict(
        AxonBinaryTimeSeries=AxonBinaryTimeSeriesInterface,
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)
