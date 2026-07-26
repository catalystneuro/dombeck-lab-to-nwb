from neuroconv import NWBConverter

from .interfaces import (
    Chen2026ABFEventsInterface,
    Chen2026BehaviorInterface,
    Chen2026OptogeneticsInterface,
    Chen2026ProcessedFiberPhotometryInterface,
    Chen2026RawFiberPhotometryInterface,
)


class Chen2026NWBConverter(NWBConverter):
    """
    NWB converter for Chen et al. 2026 (LRRK2 fiber photometry dataset).

    Raw interfaces (always present):
      RawSignal              — 470 nm demultiplexed from ABF
      IsosbesticControl      — 405 nm demultiplexed from ABF
      ABFEvents              — camera frame-trigger + opto pulses (EventsTable)

    Processed interfaces (present when a *_data.mat file is provided):
      CorrectedSignal        — baseline-corrected 470 nm (corrected470, 100 Hz)
      CorrectedIsosbestic    — baseline-corrected 405 nm (corrected405, 100 Hz)
      DfOverF                — % ΔF/F 470 nm, smoothed (dff470, 100 Hz)
      DfOverFIsosbestic      — % ΔF/F 405 nm, smoothed (dff405, 100 Hz)
      Behavior               — treadmill velocity (m/s) and acceleration (m/s²)
      Optogenetics           — stimulation epochs from TTL column
    """

    data_interface_classes = dict(
        RawSignal=Chen2026RawFiberPhotometryInterface,
        IsosbesticControl=Chen2026RawFiberPhotometryInterface,
        ABFEvents=Chen2026ABFEventsInterface,
        CorrectedSignal=Chen2026ProcessedFiberPhotometryInterface,
        CorrectedIsosbestic=Chen2026ProcessedFiberPhotometryInterface,
        DfOverF=Chen2026ProcessedFiberPhotometryInterface,
        DfOverFIsosbestic=Chen2026ProcessedFiberPhotometryInterface,
        Behavior=Chen2026BehaviorInterface,
        Optogenetics=Chen2026OptogeneticsInterface,
    )
