"""Primary NWBConverter class for this dataset."""
from neuroconv import NWBConverter
from neuroconv.datainterfaces import ScanImageImagingInterface, Suite2pSegmentationInterface


class NagappanEmbargo2023NWBConverter(NWBConverter):
    """Primary conversion class for the Two Photon experiment from Shiva Nagappan."""

    data_interface_classes = dict(
        Imaging=ScanImageImagingInterface,
        Segmentation=Suite2pSegmentationInterface,
    )
