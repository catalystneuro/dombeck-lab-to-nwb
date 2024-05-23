from copy import deepcopy
from pathlib import Path

from neuroconv.utils import FilePathType, DeepDict
from pymatreader import read_mat


def process_extra_metadata(
    file_path: FilePathType,
    metadata: DeepDict,
    allen_location_mapping: dict,
):
    """
    Process the extra metadata from the processed photometry data ("data6").

    Parameters
    ----------
    file_path : FilePathType
        The path to the processed photometry data file.
    metadata : DeepDict
        The metadata dictionary to update with the extra metadata.
    allen_location_mapping : dict
        A mapping of the location names in the processed photometry data to the Allen Brain Atlas location names.
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

    location_fiber_1 = processed_photometry_data["chG"].lower()
    location_fiber_2 = processed_photometry_data["chR"].lower()
    allen_location_fiber_1 = allen_location_mapping.get(location_fiber_1, None)
    if allen_location_fiber_1 is None:
        raise ValueError(
            f"The location of the first fiber ({location_fiber_1}) is not recognized. Please update it using the allen_location_mapping argument."
        )
    allen_location_fiber_2 = allen_location_mapping.get(location_fiber_2, None)

    # Update the metadata for the first fiber
    fiber_photometry_metadata = extra_metadata["Ophys"]["FiberPhotometry"]
    fibers_metadata = fiber_photometry_metadata["OpticalFibers"]
    fiber_description = fibers_metadata[0]["description"]
    fiber_description += f"from the {allen_location_fiber_1} brain region."
    fibers_metadata[0].update(
        description=fiber_description,
        coordinates=processed_photometry_data["RecLocGmm"],
        fiber_depth_in_mm=processed_photometry_data["depthG"],
        location=allen_location_fiber_1,
    )

    if allen_location_fiber_2 is None:
        fibers_metadata.pop(1)
        return extra_metadata

    # Update the metadata for the second fiber
    fiber_2_description = fibers_metadata[1]["description"]
    fiber_2_description += f" from the {allen_location_fiber_2} brain region."
    fibers_metadata[1].update(
        description=fiber_2_description,
        coordinates=processed_photometry_data["RecLocRmm"],
        fiber_depth_in_mm=processed_photometry_data["depthR"],
        location=allen_location_fiber_2,
    )

    return extra_metadata
