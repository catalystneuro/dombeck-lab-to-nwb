from pathlib import Path

from neuroconv import NWBConverter
from neuroconv.utils import load_dict_from_file

from .external_resources import add_external_resources
from .interfaces import (
    Chen2026BehaviorInterface,
    Chen2026OptogeneticsInterface,
    Chen2026ProcessedFiberPhotometryInterface,
    Chen2026RawFiberPhotometryInterface,
    Chen2026RawTreadmillInterface,
    Chen2026RawTriggersInterface,
)
from .value_meanings import add_value_meanings


class Chen2026NWBConverter(NWBConverter):
    """
    NWB converter for Chen et al. 2026 (LRRK2 fiber photometry dataset).

    Raw interfaces (always present):
      RawSignal              — 470 nm demultiplexed from ABF
      IsosbesticControl      — 405 nm demultiplexed from ABF
      RawTreadmill           — raw rotary-encoder voltage from ABF treadmill channel
      RawTriggers            — raw opto_TTL and camera trigger voltages from ABF

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
        RawTreadmill=Chen2026RawTreadmillInterface,
        RawTriggers=Chen2026RawTriggersInterface,
        CorrectedSignal=Chen2026ProcessedFiberPhotometryInterface,
        CorrectedIsosbestic=Chen2026ProcessedFiberPhotometryInterface,
        DfOverF=Chen2026ProcessedFiberPhotometryInterface,
        DfOverFIsosbestic=Chen2026ProcessedFiberPhotometryInterface,
        Behavior=Chen2026BehaviorInterface,
        Optogenetics=Chen2026OptogeneticsInterface,
    )

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options=None):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        terms = load_dict_from_file(Path(__file__).parent / "metadata" / "external_resources.yaml")
        add_external_resources(nwbfile=nwbfile, terms=terms["ExternalResources"])
        annotations = load_dict_from_file(Path(__file__).parent / "metadata" / "value_meanings.yaml")
        add_value_meanings(nwbfile=nwbfile, annotations=annotations)
