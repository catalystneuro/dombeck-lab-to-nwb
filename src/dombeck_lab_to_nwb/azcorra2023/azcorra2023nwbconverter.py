"""Primary NWBConverter class for this dataset."""
from neuroconv import NWBConverter

from dombeck_lab_to_nwb.azcorra2023.interfaces.picoscope_recordinginterface import PicoscopeRecordingInterface


class Azcorra2023NWBConverter(NWBConverter):
    """Primary conversion class for the Azcorra2023 Fiber photometry dataset."""

    data_interface_classes = dict(
        Recording=PicoscopeRecordingInterface,
    )
