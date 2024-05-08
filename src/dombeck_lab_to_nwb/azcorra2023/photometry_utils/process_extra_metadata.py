from copy import deepcopy
from pathlib import Path

import numpy as np
from neuroconv.utils import FilePathType, DeepDict
from pymatreader import read_mat


def process_extra_metadata(file_path: FilePathType, metadata: DeepDict):
    """
    Process the extra metadata from the processed photometry data ("data6").

    Parameters
    ----------
    file_path : FilePathType
        The path to the processed photometry data file.
    metadata : DeepDict
        The metadata dictionary to update with the extra metadata.
    """

    extra_metadata = deepcopy(metadata)

    assert Path(file_path).exists(), f"File {file_path} does not exist."
    processed_photometry_data = read_mat(filename=str(file_path))
    assert "data6" in processed_photometry_data, f"'data6' not found in {file_path}."
    processed_photometry_data = processed_photometry_data["data6"]

    extra_metadata["Subject"].update(
        subject_id=processed_photometry_data["Mouse"].replace("_", "-"),
        sex=processed_photometry_data["Gen"].upper(),
    )

    fiber_photometry_metadata = extra_metadata["Ophys"]["FiberPhotometry"]

    fibers_metadata = fiber_photometry_metadata["OpticalFibers"]

    fiber_depth_in_mm = processed_photometry_data["depthG"]
    # Update the metadata for the green fiber
    fibers_metadata[0].update(
        coordinates=processed_photometry_data["RecLocGmm"],
        depth=fiber_depth_in_mm,
        location="SNc" if fiber_depth_in_mm > 3.0 else "Str",
    )

    if np.isnan(processed_photometry_data["depthR"]):
        # For single fiber experiment the red fiber depth is NaN
        return extra_metadata

    fiber_red_depth_in_mm = processed_photometry_data["depthG"]
    fibers_metadata[1].update(
        coordinates=processed_photometry_data["RecLocRmm"],
        depth=fiber_red_depth_in_mm,
        location="SNc" if fiber_red_depth_in_mm > 3.0 else "Str",
    )

    return extra_metadata
