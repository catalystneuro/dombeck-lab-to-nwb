import numpy as np
from neuroconv.tools.roiextractors import add_devices
from pynwb import NWBFile
from pynwb.ogen import OptogeneticSeries


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
