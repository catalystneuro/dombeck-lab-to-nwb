"""Primary NWBConverter class for this dataset."""
from typing import Optional

from neuroconv import NWBConverter
from neuroconv.tools.nwb_helpers import get_default_backend_configuration, configure_backend
from pynwb import NWBFile

from dombeck_lab_to_nwb.azcorra2023.interfaces import (
    PicoscopeTimeSeriesInterface,
    PicoscopeEventInterface,
    Azcorra2023FiberPhotometryInterface,
    Azcorra2023ProcessedFiberPhotometryInterface,
)


class Azcorra2023NWBConverter(NWBConverter):
    """Primary conversion class for the Azcorra2023 Fiber photometry dataset."""

    data_interface_classes = dict(
        PicoScopeTimeSeries=PicoscopeTimeSeriesInterface,
        Events=PicoscopeEventInterface,
        FiberPhotometry=Azcorra2023FiberPhotometryInterface,
        ProcessedFiberPhotometry=Azcorra2023ProcessedFiberPhotometryInterface,
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:

        fiber_depth = self.data_interface_objects["ProcessedFiberPhotometry"].fiber_depth
        # If single fiber experiment, override interfaces to exclude red channel (empty)
        if "chRed" not in fiber_depth:
            conversion_options["FiberPhotometry"]["channel_name_to_photometry_series_name_mapping"].pop("chRed")
            conversion_options["FiberPhotometry"]["channel_name_to_photometry_series_name_mapping"].pop("chRed405")
            conversion_options["ProcessedFiberPhotometry"]["channel_name_to_photometry_series_name_mapping"].pop(
                "chRed"
            )
            conversion_options["ProcessedFiberPhotometry"]["channel_name_to_photometry_series_name_mapping"].pop(
                "chRed405"
            )
            conversion_options["PicoScopeTimeSeries"]["channel_id_to_time_series_name_mapping"].pop("B")

        # Set fiber depth from processed fiber photometry data
        conversion_options["FiberPhotometry"].update(
            fiber_depth_mapping=fiber_depth,
        )

        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)
