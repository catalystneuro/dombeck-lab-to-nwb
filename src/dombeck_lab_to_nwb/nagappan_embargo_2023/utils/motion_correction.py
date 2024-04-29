import numpy as np
import pymatreader
from neuroconv.tools import get_module
from pynwb import NWBFile, TimeSeries
from pynwb.ophys import MotionCorrection, CorrectedImageStack, TwoPhotonSeries


def add_motion_correction(
    nwbfile: NWBFile,
    corrected: np.ndarray,
    xy_shifts: np.ndarray,
    corrected_image_stack_name: str,
) -> None:
    """Add motion correction data to the NWBFile.

    Parameters
    ----------
    nwbfile: NWBFile
        The NWBFile where the motion correction time series will be added to.
    corrected: numpy.ndarray
        The corrected imaging data.
    xy_shifts: numpy.ndarray
        The x, y shifts for the imaging data.
    corrected_image_stack_name: str
        The name of the corrected image stack to be added to the MotionCorrection container.
    """

    name_suffix = corrected_image_stack_name.replace("CorrectedImageStack", "")
    original_two_photon_series_name = f"TwoPhotonSeries{name_suffix}"
    assert (
        original_two_photon_series_name in nwbfile.acquisition
    ), f"The two photon series '{original_two_photon_series_name}' does not exist in the NWBFile."

    original_two_photon_series = nwbfile.acquisition[original_two_photon_series_name]

    timestamps = original_two_photon_series.timestamps
    assert timestamps is not None, "The timestamps for the original two photon series must be set."
    assert len(xy_shifts) == len(timestamps), "The length of the xy shifts must match the length of the timestamps."
    xy_translation = TimeSeries(
        name="xy_translation",  # name must be 'xy_translation'
        data=xy_shifts,
        description=f"The x, y shifts for the {original_two_photon_series_name} imaging data.",
        unit="px",
        timestamps=timestamps,
    )

    corrected_two_photon_series = TwoPhotonSeries(
        name="corrected",  # name must be 'corrected'
        data=corrected,
        imaging_plane=original_two_photon_series.imaging_plane,
        timestamps=timestamps,
        unit="n.a.",
    )

    corrected_image_stack = CorrectedImageStack(
        name=corrected_image_stack_name,
        corrected=corrected_two_photon_series,
        original=original_two_photon_series,
        xy_translation=xy_translation,
    )

    ophys = get_module(nwbfile, "ophys")
    if "MotionCorrection" not in ophys.data_interfaces:
        motion_correction = MotionCorrection(name="MotionCorrection")
        ophys.add(motion_correction)
    else:
        motion_correction = ophys.data_interfaces["MotionCorrection"]

    motion_correction.add_corrected_image_stack(corrected_image_stack)


def get_xy_shifts(file_path: str) -> np.ndarray:
    """Get the x, y (column, row) shifts from the motion correction file.

    Parameters
    ----------
    file_path: str
        The path to the motion correction file.

    Returns
    -------
    motion_correction: numpy.ndarray
        The first column is the x shifts. The second column is the y shifts.
    """
    xy_shifts_data = pymatreader.read_mat(file_path)
    xy_translation = np.column_stack((xy_shifts_data["xshifts"], xy_shifts_data["yshifts"]))
    return xy_translation
