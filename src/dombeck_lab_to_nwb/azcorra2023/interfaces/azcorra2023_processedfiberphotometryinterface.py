from pathlib import Path

import numpy as np
from neuroconv import BaseDataInterface
from neuroconv.tools import get_module
from neuroconv.utils import FilePathType
from pymatreader import read_mat
from pynwb import TimeSeries


class Azcorra2023ProcessedFiberPhotometryInterface(BaseDataInterface):
    """Data interface for Azcorra2023 fiber photometry data conversion."""

    display_name = "Azcorra2023ProcessedPhotometry"
    associated_suffixes = ".mat"
    info = "Interface for processed fiber photometry data."  # TBD

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePathType
            The path that points to the .mat file containing the processed photometry data.
        """

        file_path = Path(file_path)
        assert file_path.exists(), f"File {file_path} does not exist."
        self.file_path = file_path
        self.verbose = verbose
        processed_photometry_data = read_mat(filename=str(self.file_path))["data6"]
        self.fiber_depth = dict(chGreen=processed_photometry_data["depthG"])

        # Not all sessions have dual fiber photometry data
        if not np.isnan(processed_photometry_data["depthR"]):
            self.fiber_depth.update(
                chRed=processed_photometry_data["depthR"],
            )
        self.subject_metadata = dict(
            experiment_type=processed_photometry_data["Exp"],
            mouse=processed_photometry_data["Mouse"],
            sex=processed_photometry_data["Gen"],
        )
        assert "data" in processed_photometry_data, f"Processed photometry data not found in {self.file_path}."
        self._processed_photometry_data = processed_photometry_data["data"]

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        metadata["Subject"].update(
            subject_id=self.subject_metadata["mouse"],
            sex=self.subject_metadata["sex"].upper(),
        )

        metadata["Behavior"].update(
            dict(
                Velocity=dict(
                    name="Velocity", description="The velocity from rotary encoder converted to m/s.", unit="m/s"
                ),
                Acceleration=dict(
                    name="Acceleration", description="The acceleration measured in the unit of m/s2.", unit="m/s2"
                ),
            ),
        )

        return metadata

    def add_behavior_data(self, nwbfile, metadata):

        behavior_metadata = metadata["Behavior"]

        assert (
            "chMov" in self._processed_photometry_data
        ), f"Velocity data not found in {self.source_data['file_path']}."
        velocity = self._processed_photometry_data["chMov"]
        velocity_metadata = behavior_metadata["Velocity"]
        velocity_ts = TimeSeries(
            data=velocity,
            rate=100.0,
            **velocity_metadata,
        )

        assert (
            "Acceleration" in self._processed_photometry_data
        ), f"Acceleration data not found in {self.source_data['file_path']}."
        acceleration = self._processed_photometry_data["Acceleration"]
        acceleration_ts = TimeSeries(
            data=acceleration,
            rate=100.0,
            **behavior_metadata["Acceleration"],
        )

        behavior_module = get_module(
            nwbfile,
            name="behavior",
            description="Contains velocity and acceleration measured over time.",
        )

        behavior_module.add(velocity_ts)
        behavior_module.add(acceleration_ts)

    def add_to_nwbfile(self, nwbfile, metadata, stub_test: bool = False):
        self.add_behavior_data(nwbfile=nwbfile, metadata=metadata)
