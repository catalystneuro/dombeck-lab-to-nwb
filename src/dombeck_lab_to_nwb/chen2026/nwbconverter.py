from neuroconv import NWBConverter

from .interfaces import Chen2026RawFiberPhotometryInterface


class Chen2026NWBConverter(NWBConverter):
    """
    NWB converter for Chen et al. 2026 (LRRK2 fiber photometry dataset).

    Raw interfaces (always present):
      RawSignal          — 470 nm demultiplexed from ABF
      IsosbesticControl  — 405 nm demultiplexed from ABF

    """

    data_interface_classes = dict(
        RawSignal=Chen2026RawFiberPhotometryInterface,
        IsosbesticControl=Chen2026RawFiberPhotometryInterface,
    )
