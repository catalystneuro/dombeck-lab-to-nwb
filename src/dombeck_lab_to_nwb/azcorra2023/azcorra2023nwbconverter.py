"""Primary NWBConverter class for this dataset."""
from neuroconv import NWBConverter

from dombeck_lab_to_nwb.azcorra2023.interfaces import PicoscopeRecordingInterface, PicoscopeEventInterface


class Azcorra2023NWBConverter(NWBConverter):
    """Primary conversion class for the Azcorra2023 Fiber photometry dataset."""

    data_interface_classes = dict(
        VelocityRecording=PicoscopeRecordingInterface,
        FluorescenceRedRecording=PicoscopeRecordingInterface,
        FluorescenceGreenRecording=PicoscopeRecordingInterface,
        Events=PicoscopeEventInterface,
    )
