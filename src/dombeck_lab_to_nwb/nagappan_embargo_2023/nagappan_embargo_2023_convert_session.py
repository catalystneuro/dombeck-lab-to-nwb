"""Primary script to run to convert an entire session for of data using the NWBConverter."""
from pathlib import Path
from typing import Union

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update

from dombeck_lab_to_nwb.nagappan_embargo_2023 import NagappanEmbargo2023NWBConverter


def session_to_nwb(
    scanimage_folder_path: Union[str, Path],
    nwbfile_path: Union[str, Path],
    stub_test: bool = False,
):
    """
    Convert a session of data to NWB format.

    Parameters
    ----------
    scanimage_folder_path : Union[str, Path]
        The folder containing the ScanImage data (.tif files).
    nwbfile_path : Union[str, Path]
        The path to the NWB file to be created.
    stub_test : bool, optional
        Whether to run a stub test, by default False.

    """
    scanimage_folder_path = Path(scanimage_folder_path)
    nwbfile_path = Path(nwbfile_path)

    source_data = dict()
    conversion_options = dict()

    # Add ScanImage data
    source_data.update(dict(Imaging=dict(folder_path=str(scanimage_folder_path))))
    conversion_options.update(dict(Imaging=dict(stub_test=stub_test)))

    converter = NagappanEmbargo2023NWBConverter(source_data=source_data)

    # Add datetime to conversion
    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    tzinfo = tz.gettz("US/Central")
    metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))

    # Update default metadata with the editable in the corresponding yaml file
    editable_metadata_path = Path(__file__).parent / "nagappan_embargo_2023_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    session_id = scanimage_folder_path.parent.name.replace("_", "-")
    metadata["NWBFile"].update(session_id=session_id)

    # Run conversion
    converter.run_conversion(metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options)


if __name__ == "__main__":

    # Parameters for conversion
    scanimage_folder_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/2620749R2_231211/231211_data")
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/2620749R2_231211.nwb")
    stub_test = False

    session_to_nwb(
        scanimage_folder_path=scanimage_folder_path,
        nwbfile_path=nwbfile_path,
        stub_test=stub_test,
    )
