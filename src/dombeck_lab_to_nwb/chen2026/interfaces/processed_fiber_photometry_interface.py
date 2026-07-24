"""Processed fiber photometry interface for Chen et al. 2026 (LRRK2 dataset).

Reads one of four baseline-corrected / ΔF/F streams from the per-animal
*_data.mat file produced by LRRK2_binning_and_processing.m:

  "corrected470"  — baseline-subtracted 470 nm signal (baselineCorrect)
  "corrected405"  — baseline-subtracted 405 nm isosbestic signal
  "dff470"        — % ΔF/F of the corrected 470 nm trace (smoothed, 20-sample moving mean)
  "dff405"        — % ΔF/F of the corrected 405 nm trace (smoothed, 20-sample moving mean)

All four streams are at 100 Hz (camera-trigger-aligned binning). The *_data.mat
file is a MATLAB v7.3 HDF5 file containing a table class object; it is read
directly with h5py via the reference-chain structure documented below.

Column order in the MATLAB table (g-ref index → column name):
  0 filename, 1 corrected470, 2 corrected405, 3 dff470, 4 dff405,
  5 TTL, 6 velocity, 7 acceleration, 8 camera, 9 stim_sequence
"""

from pathlib import Path

import numpy as np
from neuroconv.datainterfaces.fiber_photometry.basefiberphotometryinterface import (
    BaseFiberPhotometryInterface,
)

_COLUMNS = [
    "filename",
    "corrected470",
    "corrected405",
    "dff470",
    "dff405",
    "TTL",
    "velocity",
    "acceleration",
    "camera",
    "stim_sequence",
]

# Module-level cache keyed by file_path
_MAT_CACHE: dict[str, dict] = {}


_CAMERA_SAMPLE_RATE = 2000.0  # Hz — raw ABF / camera-channel sampling rate
_CAMERA_TRIGGER_THRESHOLD = 1.0  # V — threshold for camera trigger detection


def _read_mat(file_path: str) -> dict:
    """Read *_data.mat and return {column_name: np.ndarray} (cached).

    In addition to the named columns, the returned dict contains:
      "camera_trigger_times" — timestamps (in seconds, ABF clock) of each
          camera trigger rising edge. These are the actual sample times for
          all 100 Hz columns and are used as explicit timestamps in NWB to
          align processed data with the raw ABF recording.
    """
    if file_path in _MAT_CACHE:
        return _MAT_CACHE[file_path]

    import h5py

    result: dict = {}
    with h5py.File(file_path, "r") as f:
        g_ds = f["#refs#"]["g"]  # 10-element ref array, one per column

        for col_idx, col_name in enumerate(_COLUMNS):
            outer_ref = g_ds[col_idx, 0]
            outer = f[outer_ref]

            if not (isinstance(outer, h5py.Dataset) and outer.dtype == object):
                continue

            inner_ref = outer[0, 0]
            inner = f[inner_ref]

            if not isinstance(inner, h5py.Dataset):
                continue

            raw = inner[()]
            if raw.dtype == np.uint16:
                result[col_name] = "".join(chr(c) for c in raw.flatten())
            elif raw.dtype in (np.float64, np.float32):
                result[col_name] = raw.flatten().astype(np.float64)
            elif raw.dtype == np.uint8:
                result[col_name] = raw.flatten()
            # stim_sequence (object/uint32 MCOS) left unread

    # Derive camera trigger timestamps from the 2 kHz camera TTL channel.
    # The processed 100 Hz columns are binned on camera trigger rising edges;
    # using these times as explicit timestamps aligns the processed data to
    # the ABF recording clock.
    if "camera" in result:
        cam = result.pop("camera")  # discard raw 2 kHz signal after processing
        above = cam > _CAMERA_TRIGGER_THRESHOLD
        rising_indices = np.where(np.diff(above.astype(np.int8)) == 1)[0]
        result["camera_trigger_times"] = rising_indices / _CAMERA_SAMPLE_RATE

    _MAT_CACHE[file_path] = result
    return result


class Chen2026ProcessedFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Processed fiber photometry from *_data.mat file (Chen et al. 2026).

    Each instance writes one FiberPhotometryResponseSeries at 100 Hz.
    Instantiate with one of the four processed stream names:

      stream_names=["corrected470"]  → FiberPhotometryResponseSeriesCorrectedSignal
      stream_names=["corrected405"]  → FiberPhotometryResponseSeriesCorrectedIsosbesticControl
      stream_names=["dff470"]        → FiberPhotometryResponseSeriesDfOverF
      stream_names=["dff405"]        → FiberPhotometryResponseSeriesDfOverFIsosbesticControl

    Pass ``metadata_key`` matching an entry in ``fiber_photometry.yaml``:
      "corrected_signal_{anxa|calb}", "corrected_isosbestic_{anxa|calb}",
      "dff_{anxa|calb}", "dff_isosbestic_{anxa|calb}"
    """

    display_name = "Chen2026 Processed Fiber Photometry (_data.mat)"
    associated_suffixes = (".mat",)
    info = "Interface for processed fiber photometry from MATLAB _data.mat files."

    PROCESSED_STREAMS = ("corrected470", "corrected405", "dff470", "dff405")
    SAMPLING_RATE = 100.0

    @classmethod
    def get_available_streams(cls, file_path: str | Path) -> list[str]:
        return list(cls.PROCESSED_STREAMS)

    def __init__(
        self,
        *,
        file_path: str | Path,
        stream_names: list[str],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : str | Path
            Path to the *_data.mat file.
        stream_names : list of str
            Which processed stream to expose. One of "corrected470",
            "corrected405", "dff470", "dff405".
        metadata_key : str | None
            Key into metadata["FiberPhotometry"] for this series entry.
            Must match an entry in fiber_photometry.yaml.
        verbose : bool
        """
        super().__init__(
            stream_names=stream_names,
            metadata_key=metadata_key,
            file_path=str(file_path),
            verbose=verbose,
        )

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        return _read_mat(self.source_data["file_path"])[stream_name]

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        return _read_mat(self.source_data["file_path"])["camera_trigger_times"]

    # TODO: this should be fixed in BaseFiberPhotometryInterface
    """
     The ophys imaging interface already uses parent_container: Literal["acquisition", "processing/ophys"].
     That's the exact pattern needed for BaseFiberPhotometryInterface. The PR to neuroconv would be straightforward:
     1. Add parent_container: Literal["acquisition", "processing/ophys"] = "acquisition" to BaseFiberPhotometryInterface.add_to_nwbfile
    2. Replace the hardcoded nwbfile.add_acquisition(response_series) with the same conditional logic the ophys interface uses
    """

    def add_to_nwbfile(self, nwbfile, metadata, **conversion_options):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

        series_name = metadata["FiberPhotometry"][self.metadata_key]["name"]
        series = nwbfile.acquisition[series_name]
        del nwbfile.acquisition[series_name]

        if "ophys" not in nwbfile.processing:
            nwbfile.create_processing_module("ophys", "Processed optical physiology data.")
        nwbfile.processing["ophys"].add(series)
