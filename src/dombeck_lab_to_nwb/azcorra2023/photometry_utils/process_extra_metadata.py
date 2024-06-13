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
    extra_metadata["experiment_type"] = processed_photometry_data["RunRew"]

    subject_gender = processed_photometry_data["Gen"].upper()
    subject_gender = subject_gender if subject_gender in ["M", "F"] else "U"
    extra_metadata["Subject"].update(sex=subject_gender)

    location_fiber_1 = processed_photometry_data["chG"].lower()
    location_fiber_2 = processed_photometry_data["chR"].lower()
    allen_location_fiber_1 = allen_location_mapping.get(location_fiber_1, None)
    allen_location_fiber_2 = allen_location_mapping.get(location_fiber_2, None)
    is_dual_fiber = allen_location_fiber_1 is not None and allen_location_fiber_2 is not None

    # Update the metadata for the first fiber
    fiber_photometry_metadata = extra_metadata["Ophys"]["FiberPhotometry"]
    fibers_metadata = fiber_photometry_metadata["OpticalFibers"]

    recording_target_type_mapping = {1: "axons in striatum", 0: "cell bodies in SNc"}

    if allen_location_fiber_1 is not None:
        fiber_description = fibers_metadata[0]["description"]
        fiber_description += f" from the {allen_location_fiber_1} brain region."

        recording_target_type = recording_target_type_mapping.get(processed_photometry_data["exStr"][0], "unknown")

        fibers_metadata[0].update(
            description=fiber_description,
            coordinates=processed_photometry_data["RecLocGmm"],
            fiber_depth_in_mm=processed_photometry_data["depthG"],
            location=allen_location_fiber_1,
            label="chGreen",  # the name of the channel in the .mat file
            recording_target_type=recording_target_type,
            baseline_fluorescence=processed_photometry_data["base"][0]
            if is_dual_fiber
            else processed_photometry_data["base"],
            normalized_fluorescence=processed_photometry_data["norm"][0]
            if is_dual_fiber
            else processed_photometry_data["norm"],
            signal_to_noise_ratio=processed_photometry_data["sig2noise"][0],
            cross_correlation_with_acceleration=processed_photometry_data["Acc405"][0],
        )

    if allen_location_fiber_2 is not None:
        fiber_2_description = fibers_metadata[1]["description"]
        fiber_2_description += f" from the {allen_location_fiber_2} brain region."

        recording_target_type = recording_target_type_mapping.get(processed_photometry_data["exStr"][1], "unknown")

        fibers_metadata[1].update(
            description=fiber_2_description,
            coordinates=processed_photometry_data["RecLocRmm"],
            fiber_depth_in_mm=processed_photometry_data["depthR"],
            location=allen_location_fiber_2,
            label="chRed",  # the name of the channel in the .mat file
            recording_target_type=recording_target_type,
            baseline_fluorescence=processed_photometry_data["base"][1]
            if is_dual_fiber
            else processed_photometry_data["base"],
            normalized_fluorescence=processed_photometry_data["norm"][1]
            if is_dual_fiber
            else processed_photometry_data["norm"],
            signal_to_noise_ratio=processed_photometry_data["sig2noise"][1],
            cross_correlation_with_acceleration=processed_photometry_data["Acc405"][1],
        )

    # keep only those fibers metadata that have location information
    updated_fibers_metadata = [fiber for fiber in fibers_metadata if "location" in fiber]
    if not len(updated_fibers_metadata):
        raise ValueError("No fiber metadata with location information found.")
    fiber_photometry_metadata["OpticalFibers"] = updated_fibers_metadata
    for trace_metadata in fiber_photometry_metadata["FiberPhotometryResponseSeries"]:
        trace_metadata["optical_fiber"] = [fiber["name"] for fiber in updated_fibers_metadata]

    return extra_metadata
