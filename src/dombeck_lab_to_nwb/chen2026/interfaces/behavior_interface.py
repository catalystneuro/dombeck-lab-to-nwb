"""Behavior interface for Chen et al. 2026 (LRRK2 dataset).

Reads treadmill velocity and acceleration from the per-animal *_data.mat file
(100 Hz, camera-trigger-aligned binning) and writes them to processing/behavior
as a BehavioralTimeSeries containing two TimeSeries:

  - treadmill_velocity     (m/s)
  - treadmill_acceleration (m/s²)
"""

from pathlib import Path

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools import get_module
from pynwb import NWBFile, TimeSeries
from pynwb.behavior import BehavioralTimeSeries

from .processed_fiber_photometry_interface import _read_mat


class Chen2026BehaviorInterface(BaseDataInterface):
    """Behavior interface for Chen et al. 2026 (LRRK2 dataset).

    Reads treadmill velocity (m/s) and acceleration (m/s²) from the 100 Hz
    binned columns in the per-animal *_data.mat file and writes them to
    processing/behavior as a BehavioralTimeSeries.
    """

    display_name = "Chen2026 Behavior (*_data.mat velocity/acceleration)"
    associated_suffixes = (".mat",)
    info = "Interface for treadmill velocity and acceleration from *_data.mat."

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
    ) -> None:
        mat = _read_mat(self.source_data["file_path"])

        velocity = mat["velocity"]
        acceleration = mat["acceleration"]
        timestamps = mat["camera_trigger_times"]

        if stub_test:
            velocity = velocity[:100]
            acceleration = acceleration[:100]
            timestamps = timestamps[:100]

        velocity_ts = TimeSeries(
            name="treadmill_velocity",
            description=(
                "Treadmill velocity at 100 Hz (camera-trigger-aligned binning). "
                "Derived from rotary encoder voltage using calibration factor 1.3532 m/s per V. "
                "Positive values indicate forward locomotion. "
            ),
            data=velocity,
            unit="m/s",
            timestamps=timestamps,
        )

        acceleration_ts = TimeSeries(
            name="treadmill_acceleration",
            description="Treadmill acceleration at 100 Hz (camera-trigger-aligned binning).",
            data=acceleration,
            unit="m/s^2",
            timestamps=timestamps,
        )

        behavioral_ts = BehavioralTimeSeries(
            name="BehavioralTimeSeries",
            time_series=[velocity_ts, acceleration_ts],
        )

        behavior_module = get_module(nwbfile, name="behavior", description="Processed behavioral data.")
        behavior_module.add(behavioral_ts)
