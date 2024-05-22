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

    subject_gender = processed_photometry_data["Gen"].upper()
    subject_gender = subject_gender if subject_gender in ["M", "F"] else "U"
    extra_metadata["Subject"].update(sex=subject_gender)

    location_fiber_1 = processed_photometry_data["chG"].lower()
    location_fiber_2 = processed_photometry_data["chR"].lower()
    allen_location_fiber_1 = allen_location_mapping.get(location_fiber_1, None)
    allen_location_fiber_2 = allen_location_mapping.get(location_fiber_2, None)

    # Update the metadata for the first fiber
    fiber_photometry_metadata = extra_metadata["Ophys"]["FiberPhotometry"]
    fibers_metadata = fiber_photometry_metadata["OpticalFibers"]

    if allen_location_fiber_1 is not None:
        fiber_description = fibers_metadata[0]["description"]
        fiber_description += f"from the {allen_location_fiber_1} brain region."
        fibers_metadata[0].update(
            description=fiber_description,
            coordinates=processed_photometry_data["RecLocGmm"],
            fiber_depth_in_mm=processed_photometry_data["depthG"],
            location=allen_location_fiber_1,
            label="chGreen",  # the name of the channel in the .mat file
        )

    if allen_location_fiber_2 is not None:
        fiber_2_description = fibers_metadata[1]["description"]
        fiber_2_description += f" from the {allen_location_fiber_2} brain region."
        fibers_metadata[1].update(
            description=fiber_2_description,
            coordinates=processed_photometry_data["RecLocRmm"],
            fiber_depth_in_mm=processed_photometry_data["depthR"],
            location=allen_location_fiber_2,
            label="chRed",  # the name of the channel in the .mat file
        )

    # keep only those fibers metadata that have location information
    updated_fibers_metadata = [fiber for fiber in fibers_metadata if "location" in fiber]
    if not len(updated_fibers_metadata):
        raise ValueError("No fiber metadata with location information found.")
    fiber_photometry_metadata["OpticalFibers"] = updated_fibers_metadata

    return extra_metadata
