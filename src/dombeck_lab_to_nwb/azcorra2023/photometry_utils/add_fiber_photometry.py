from collections import defaultdict
from typing import Literal

import numpy as np
from hdmf.common import DynamicTableRegion
from neuroconv.tools import get_module
from pynwb import NWBFile
from ndx_fiber_photometry import (
    FiberPhotometryTable,
    OpticalFiber,
    Indicator,
    ExcitationSource,
    Photodetector,
    DichroicMirror,
    BandOpticalFilter,
    FiberPhotometryResponseSeries,
    FiberPhotometry,
)


def add_photometry_device(nwbfile: NWBFile, device_metadata: dict, device_type: str):
    """Add a photometry device to an NWBFile object."""

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        return

    photometry_device = defaultdict(
        OpticalFiber=OpticalFiber,
        Indicator=Indicator,
        ExcitationSource=ExcitationSource,
        Photodetector=Photodetector,
        DichroicMirror=DichroicMirror,
        BandOpticalFilter=BandOpticalFilter,
    )[device_type](**device_metadata)

    nwbfile.add_device(photometry_device)


def add_fiber_photometry_series(
    nwbfile: NWBFile,
    metadata: dict,
    data: np.ndarray,
    rate: float,
    fiber_photometry_series_name: str,
    table_region_ind: int = 0,
    unit: str = "F",
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
):
    fiber_photometry_metadata = metadata["Ophys"]["FiberPhotometry"]
    traces_metadata = fiber_photometry_metadata["FiberPhotometryResponseSeries"]

    trace_metadata = next(
        (trace for trace in traces_metadata if trace["name"] == fiber_photometry_series_name),
        None,
    )
    if trace_metadata is None:
        raise ValueError(f"Trace metadata for '{fiber_photometry_series_name}' not found.")

    if "FiberPhotometry" not in nwbfile.lab_meta_data:
        fiber_photometry_table_metadata = fiber_photometry_metadata["FiberPhotometryTable"]
        fiber_photometry_table = FiberPhotometryTable(**fiber_photometry_table_metadata)
        fiber_photometry_table.add_column(
            name="fiber_depth_in_mm", description="The depth of the optical fiber in the unit of millimeters."
        )
        fiber_photometry_lab_meta_data = FiberPhotometry(
            name="FiberPhotometry",
            fiber_photometry_table=fiber_photometry_table,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_lab_meta_data)

    fiber_photometry_table = nwbfile.lab_meta_data["FiberPhotometry"].fiber_photometry_table

    fiber_to_add = trace_metadata["optical_fiber"]
    fiber_metadata = next(
        (fiber for fiber in fiber_photometry_metadata["OpticalFibers"] if fiber["name"] == fiber_to_add),
        None,
    )
    if fiber_metadata is None:
        raise ValueError(f"Fiber metadata for '{fiber_to_add}' not found.")

    location = fiber_metadata["location"]
    coordinates = fiber_metadata["coordinates"]
    fiber_depth_in_mm = fiber_metadata["fiber_depth_in_mm"]

    trace_description = trace_metadata["description"]
    trace_description += f" from {location} region at {fiber_depth_in_mm / 1000} meters depth."
    trace_metadata["description"] = trace_description

    fiber_metadata = {
        k: v for k, v in fiber_metadata.items() if k not in ["location", "coordinates", "fiber_depth_in_mm", "label"]
    }
    add_photometry_device(nwbfile, device_metadata=fiber_metadata, device_type="OpticalFiber")

    indicator_to_add = trace_metadata["indicator"]
    indicator_metadata = next(
        (indicator for indicator in fiber_photometry_metadata["Indicator"] if indicator["name"] == indicator_to_add),
        None,
    )
    if indicator_metadata is None:
        raise ValueError(f"Indicator metadata for '{indicator_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=indicator_metadata, device_type="Indicator")

    excitation_source_to_add = trace_metadata["excitation_source"]
    excitation_source_metadata = next(
        (
            source
            for source in fiber_photometry_metadata["ExcitationSources"]
            if source["name"] == excitation_source_to_add
        ),
        None,
    )
    if excitation_source_metadata is None:
        raise ValueError(f"Excitation source metadata for '{excitation_source_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=excitation_source_metadata, device_type="ExcitationSource")

    photodetector_to_add = trace_metadata["photodetector"]
    photodetector_metadata = next(
        (
            detector
            for detector in fiber_photometry_metadata["Photodetectors"]
            if detector["name"] == photodetector_to_add
        ),
        None,
    )
    if photodetector_metadata is None:
        raise ValueError(f"Photodetector metadata for '{photodetector_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=photodetector_metadata, device_type="Photodetector")

    dichroic_mirror_to_add = trace_metadata["dichroic_mirror"]
    dichroic_mirror_metadata = next(
        (mirror for mirror in fiber_photometry_metadata["DichroicMirrors"] if mirror["name"] == dichroic_mirror_to_add),
        None,
    )
    if dichroic_mirror_metadata is None:
        raise ValueError(f"Dichroic mirror metadata for '{dichroic_mirror_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=dichroic_mirror_metadata, device_type="DichroicMirror")

    optical_filter_to_add = trace_metadata["excitation_filter"]
    optical_filter_metadata = next(
        (
            filter
            for filter in fiber_photometry_metadata["BandOpticalFilters"]
            if filter["name"] == optical_filter_to_add
        ),
        None,
    )
    if optical_filter_metadata is None:
        raise ValueError(f"Optical filter metadata for '{optical_filter_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=optical_filter_metadata, device_type="BandOpticalFilter")

    emission_filter_to_add = trace_metadata["emission_filter"]
    emission_filter_metadata = next(
        (
            filter
            for filter in fiber_photometry_metadata["BandOpticalFilters"]
            if filter["name"] == emission_filter_to_add
        ),
        None,
    )
    if emission_filter_metadata is None:
        raise ValueError(f"Emission filter metadata for '{emission_filter_to_add}' not found.")
    add_photometry_device(nwbfile, device_metadata=emission_filter_metadata, device_type="BandOpticalFilter")

    fiber_photometry_table.add_row(
        location=location,
        coordinates=coordinates,
        fiber_depth_in_mm=fiber_depth_in_mm,
        indicator=nwbfile.devices[indicator_to_add],
        optical_fiber=nwbfile.devices[fiber_to_add],
        excitation_source=nwbfile.devices[excitation_source_to_add],
        photodetector=nwbfile.devices[photodetector_to_add],
        dichroic_mirror=nwbfile.devices[dichroic_mirror_to_add],
        excitation_filter=nwbfile.devices[optical_filter_to_add],
        emission_filter=nwbfile.devices[emission_filter_to_add],
    )

    fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
        region=[table_region_ind], description="source fibers"
    )

    fiber_photometry_response_series = FiberPhotometryResponseSeries(
        name=trace_metadata["name"],
        description=trace_metadata["description"],
        data=data,
        unit=unit,
        rate=rate,
        fiber_photometry_table_region=fiber_photometry_table_region,
    )

    if parent_container == "acquisition":
        nwbfile.add_acquisition(fiber_photometry_response_series)
    elif parent_container == "processing/ophys":
        ophys = get_module(nwbfile, "ophys", description="Contains the processed fiber photometry data.")
        ophys.add(fiber_photometry_response_series)
    else:
        raise ValueError(f"Invalid parent container '{parent_container}'.")
