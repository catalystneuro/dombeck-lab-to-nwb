"""Primary NWBConverter class for this dataset."""
from neuroconv import NWBConverter

from dombeck_lab_to_nwb.he_embargo_2024.interfaces import (
    AxonBinaryTimeSeriesInterface,
    HeEmbargo2024OptogeneticStimulationInterface,
    AxonBinaryTtlInterface,
    HeEmbargo2024FiberPhotometryInterface,
)


class HeEmbargo2024NWBConverter(NWBConverter):
    """Primary conversion class for the Fiber Photometry experiment from Elena He from Dombeck lab."""

    data_interface_classes = dict(
        AxonBinaryTimeSeries=AxonBinaryTimeSeriesInterface,
        OptogeneticStimulation=HeEmbargo2024OptogeneticStimulationInterface,
        TTL=AxonBinaryTtlInterface,
        FiberPhotometry=HeEmbargo2024FiberPhotometryInterface,
    )
