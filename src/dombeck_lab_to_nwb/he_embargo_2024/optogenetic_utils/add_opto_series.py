import numpy as np
from neuroconv.tools.roiextractors import add_devices
from pymatreader import read_mat
from pynwb import NWBFile
from pynwb.ogen import OptogeneticSeries


def get_stimulation_parameters_from_mat_file(mat_file_path: str, session_id: str):
    """
    Returns a dictionary with the stimulation parameters extracted from the .mat file.
    e.g. {'power_in_W': 0.4, 'duration_in_s': 5.0, 'frequency_in_Hz': 6.0, 'pulse_width_in_s': 0.008}

    Parameters
    ----------
    mat_file_path : str
        The path to the .mat file containing the stimulation parameters.
    session_id : str
        The identifier of the session.
    """
    stimulation_parameters_mat = read_mat(mat_file_path)
    values = stimulation_parameters_mat["#subsystem#"]["MCOS"][2]
    column_names = stimulation_parameters_mat["#subsystem#"]["MCOS"][7]
    filenames = values[column_names.index("filename")]
    session_ids = [filename.split(".")[0] for filename in filenames]
    assert session_id in session_ids, f"Expected session_id '{session_id}', found {session_ids}."
    session_index = session_ids.index(session_id)
    power_stim_index = column_names.index("power_stim")
    power_in_mW = values[power_stim_index][session_index]

    length_stim_index = column_names.index("length_stim")
    duration_in_ms = values[length_stim_index][session_index]

    has_opto = power_in_mW != 0

    if not has_opto:
        return None

    type_stim_index = column_names.index("type_stim")
    type_stim = values[type_stim_index][session_index]
    frequency_str, pulse_width_str = type_stim.split("-")
    frequency_in_Hz = float(frequency_str.replace("Hz", ""))
    pulse_width_in_ms = float(pulse_width_str.replace("ms", ""))
    pulse_width_in_s = pulse_width_in_ms / 1000

    stimulation_parameters = dict(
        power_in_W=power_in_mW / 1000,
        duration_in_s=duration_in_ms / 1000,
        frequency_in_Hz=frequency_in_Hz,
        pulse_width_in_s=pulse_width_in_s,
    )

    return stimulation_parameters


def add_optogenetic_stimulus_site(nwbfile: NWBFile, metadata: dict, ogen_site_name: str):
    """
    Add an OptogeneticStimulusSite using the corresponding metadata to the NWBFile.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile object where OptogeneticStimulusSite will be added.
    metadata : dict
        The metadata dictionary containing the information about the OptogeneticStimulusSite.
    ogen_site_name : str
        The name of the OptogeneticStimulusSite to add.
    """

    ogen_sites_metadata = metadata["Ophys"]["OptogeneticStimulusSite"]

    ogen_site_metadata = next(
        (ogen_site for ogen_site in ogen_sites_metadata if ogen_site["name"] == ogen_site_name),
        None,
    )
    if ogen_site_metadata is None:
        raise ValueError(f"The metadata for the OptogeneticStimulusSite '{ogen_site_name}' is not found.")

    if ogen_site_name in nwbfile.ogen_sites:
        return nwbfile.ogen_sites[ogen_site_name]

    add_devices(nwbfile, metadata)
    device_name = ogen_site_metadata.pop("device")

    ogen_site = nwbfile.create_ogen_site(
        device=nwbfile.devices[device_name],
        **ogen_site_metadata,
    )

    return ogen_site


def add_optogenetic_series(
    nwbfile: NWBFile,
    metadata: dict,
    optogenetic_series_name: str,
    data: np.ndarray,
    timestamps: np.ndarray,
):
    """
    Add an OptogeneticSeries using the corresponding metadata to the NWBFile.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile object where OptogeneticSeries will be added.
    metadata : dict
        The metadata dictionary containing the information about the OptogeneticSeries.
    optogenetic_series_name : str
        The name of the OptogeneticSeries.
    data : np.ndarray
        The data array of the OptogeneticSeries.
    timestamps : np.ndarray
        The timestamps array of the OptogeneticSeries.
    """

    ogen_metadata = metadata["Ophys"]["OptogeneticSeries"]
    ogen_series_metadata = next(
        (ogen_series for ogen_series in ogen_metadata if ogen_series["name"] == optogenetic_series_name),
        None,
    )
    if ogen_series_metadata is None:
        raise ValueError(f"The metadata for the OptogeneticSeries '{optogenetic_series_name}' is not found.")
    if optogenetic_series_name in nwbfile.stimulus:
        raise ValueError(f"The optogenetic series '{optogenetic_series_name}' already exists in the NWBfile.")

    ogen_site = add_optogenetic_stimulus_site(
        nwbfile=nwbfile,
        metadata=metadata,
        ogen_site_name=ogen_series_metadata["site"],
    )

    ogen_series = OptogeneticSeries(
        name=optogenetic_series_name,
        site=ogen_site,
        data=data,
        timestamps=timestamps,
        description=ogen_series_metadata["description"],
    )
    nwbfile.add_stimulus(ogen_series)
