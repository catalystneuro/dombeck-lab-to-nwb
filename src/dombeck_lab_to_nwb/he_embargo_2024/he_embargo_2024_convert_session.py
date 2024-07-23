"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from pathlib import Path
from typing import Union

from dateutil import tz
from neuroconv.utils import load_dict_from_file, dict_deep_update

from dombeck_lab_to_nwb.he_embargo_2024 import HeEmbargo2024NWBConverter
from dombeck_lab_to_nwb.he_embargo_2024.optogenetic_utils import get_stimulation_parameters_from_mat_file


def session_to_nwb(
    abf_file_path: Union[str, Path],
    optogenetic_stimulation_file_path: Union[str, Path],
    stimulation_parameters_file_path: Union[str, Path],
    nwbfile_path: Union[str, Path],
    stub_test: bool = False,
):
    """
    Convert a session of data to NWB format.

    Parameters
    ----------
    abf_file_path : Union[str, Path]
        The path to the Axon Binary Format (.abf) file.
    optogenetic_stimulation_file_path : Union[str, Path]
        The path to the .mat file containing the optogenetic stimulation data "opto".
    stimulation_parameters_file_path : Union[str, Path]
        The path to the .mat file containing the stimulation parameters (e.g., power, duration, frequency, pulse width).
    nwbfile_path : Union[str, Path]
        The path to the NWB file to be created.
    stub_test : bool, optional
        Whether to run a stub test, by default False.

    """
    abf_file_path = Path(abf_file_path)
    nwbfile_path = Path(nwbfile_path)

    source_data = dict()
    conversion_options = dict()

    # Add ABF data
    source_data.update(
        dict(
            AxonBinaryTimeSeries=dict(file_path=str(abf_file_path)),
            TTL=dict(file_path=str(abf_file_path)),
        )
    )

    session_id = abf_file_path.stem

    stimulation_parameters = get_stimulation_parameters_from_mat_file(
        mat_file_path=stimulation_parameters_file_path,
        session_id=session_id,
    )

    # Add optogenetic stimulation data
    if stimulation_parameters is not None:
        source_data.update(
            dict(
                OptogeneticStimulation=dict(file_path=str(optogenetic_stimulation_file_path), session_id=session_id),
            )
        )

    converter = HeEmbargo2024NWBConverter(source_data=source_data)

    # Add datetime to conversion
    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    tzinfo = tz.gettz("US/Central")
    metadata["NWBFile"].update(
        session_start_time=session_start_time.replace(tzinfo=tzinfo),
    )

    # Update default metadata with the editable in the corresponding yaml file
    editable_metadata_path = Path(__file__).parent / "metadata" / "he_embargo_2024_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Update ophys metadata
    ophys_metadata_path = Path(__file__).parent / "metadata" / "he_embargo_2024_ophys_metadata.yaml"
    ophys_metadata = load_dict_from_file(ophys_metadata_path)
    metadata = dict_deep_update(metadata, ophys_metadata)

    # Update conversion options
    conversion_options.update(
        dict(
            AxonBinaryTimeSeries=dict(
                channel_id_to_time_series_name_mapping={"520sig": "Fluorescence", "treadmill": "Velocity"},
                stub_test=stub_test,
            ),
            TTL=dict(stub_test=stub_test),
        )
    )
    if stimulation_parameters is not None:
        conversion_options.update(
            dict(
                OptogeneticStimulation=dict(
                    optogenetic_series_name="OptogeneticSeries",
                    sampling_frequency=100.0,
                    stimulation_parameters=stimulation_parameters,
                    stub_test=stub_test,
                ),
            ),
        )

    # Run conversion
    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )


if __name__ == "__main__":
    # Parameters for conversion
    abf_file_path = "/Volumes/LaCie/CN_GCP/Dombeck/sample_data/AnT60/stimulation/2024_01_09_0003.abf"

    # The path to the opto file
    opto_file_path = "/Volumes/LaCie/CN_GCP/Dombeck/sample_data/AnT60/stimulation/processed/AnT60_data4-new.mat"
    stimulation_parameters_file_path = (
        "/Volumes/LaCie/CN_GCP/Dombeck/sample_data/AnT60/stimulation/processed/AnT60-new.mat"
    )

    # The path to the NWB file to be created.
    nwbfile_path = Path("/Volumes/LaCie/CN_GCP/Dombeck/nwbfiles/AnT60-2024-01-09-0003.nwb")

    stub_test = False

    session_to_nwb(
        abf_file_path=abf_file_path,
        optogenetic_stimulation_file_path=opto_file_path,
        stimulation_parameters_file_path=stimulation_parameters_file_path,
        nwbfile_path=nwbfile_path,
        stub_test=stub_test,
    )
