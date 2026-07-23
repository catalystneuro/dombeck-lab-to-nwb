"""Raw fiber photometry interface for Chen et al. 2026 (LRRK2 dataset).

Reads the multiplexed fluorescence signal from an Axon Binary Format (.abf) file
and exposes one demultiplexed stream — either 470 nm (functional) or 405 nm
(isosbestic) — as a single-column FiberPhotometryResponseSeries.

The 520sig channel contains both excitation wavelengths interleaved at 100 Hz.
The fxn_gen channel (LED switching square wave) is used as a demultiplexing key:
samples where fxn_gen > 1 V correspond to 470 nm excitation; samples where
fxn_gen < 1 V correspond to 405 nm excitation. Transition samples at LED switch
edges are discarded to avoid contamination.

Instantiate once with stream_names=["470nm"] for the raw signal series and
once with stream_names=["405nm"] for the isosbestic control series. Both
instances that share the same file_path reuse a module-level demux cache so
the ABF is only read once.
"""

from pathlib import Path

import numpy as np
from neuroconv.datainterfaces.fiber_photometry.basefiberphotometryinterface import (
    BaseFiberPhotometryInterface,
)

# Module-level cache: file_path → {stream_name: (data, timestamps), "_datetime": abfDateTime}
_DEMUX_CACHE: dict[str, dict] = {}


def _load_and_demux(file_path: str, threshold_v: float = 1.0) -> dict:
    """Read one ABF and return demuxed streams (cached by file_path)."""
    if file_path in _DEMUX_CACHE:
        return _DEMUX_CACHE[file_path]

    import pyabf

    abf = pyabf.ABF(file_path, loadData=True)
    channel_names = [abf.adcNames[i].strip() for i in range(abf.channelCount)]

    sig_idx = channel_names.index("520sig")
    fxn_idx = channel_names.index("fxn_gen")

    sig520 = abf.data[sig_idx]
    fxn = abf.data[fxn_idx]

    n = len(sig520)
    timestamps = np.arange(n, dtype=np.float64) / abf.dataRate

    # Mirror the MATLAB border-detection logic:
    #   border405 = [0; abs(diff(wave405))]
    #   border470 = [abs(diff(wave470)); 1]   ← last sample always a border
    wave470 = fxn > threshold_v
    wave405 = ~wave470

    border405 = np.concatenate([[0], np.abs(np.diff(wave405.astype(np.float32)))])
    border470 = np.concatenate([np.abs(np.diff(wave470.astype(np.float32))), [1]])
    border = (border405 + border470) > 0

    from zoneinfo import ZoneInfo

    abf_dt = abf.abfDateTime
    if abf_dt.tzinfo is None:
        # ABF stores wall-clock time without timezone; lab is at Northwestern University (Chicago).
        abf_dt = abf_dt.replace(tzinfo=ZoneInfo("America/Chicago"))

    result = {
        "470nm": (sig520[wave470 & ~border], timestamps[wave470 & ~border]),
        "405nm": (sig520[wave405 & ~border], timestamps[wave405 & ~border]),
        "_datetime": abf_dt,
    }
    _DEMUX_CACHE[file_path] = result
    return result


class Chen2026RawFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Raw demultiplexed fiber photometry from ABF file (Chen et al. 2026).

    Each instance writes one single-column FiberPhotometryResponseSeries.
    Use stream_names=["470nm"] for the functional dopamine signal series
    (FiberPhotometryResponseSeriesRawSignal) and stream_names=["405nm"] for
    the isosbestic control series (FiberPhotometryResponseSeriesIsosbesticControl).

    Pass metadata_key matching an entry in fiber_photometry.yaml:
      "raw_signal_anxa" / "isosbestic_anxa"   — Anxa-LRRK2 animals (DLS)
      "raw_signal_calb" / "isosbestic_calb"   — Calb-LRRK2 animals (DMS)
    """

    display_name = "Chen2026 Raw Fiber Photometry (ABF)"
    associated_suffixes = (".abf",)
    info = "Interface for raw demultiplexed fiber photometry from Axon Binary Format files."

    STREAM_470 = "470nm"
    STREAM_405 = "405nm"
    FXN_THRESHOLD_V = 1.0

    @classmethod
    def get_available_streams(cls, file_path: str | Path) -> list[str]:
        return [cls.STREAM_470, cls.STREAM_405]

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
            Path to the .abf file.
        stream_names : list of str
            Which stream(s) to include. Pass ["470nm"] for the signal series or
            ["405nm"] for the isosbestic control series.
        metadata_key : str, optional
            Key into metadata["FiberPhotometry"] for this series entry.
            Must match an entry in fiber_photometry.yaml.
        verbose : bool, default: False
        """
        super().__init__(
            stream_names=stream_names,
            metadata_key=metadata_key,
            file_path=str(file_path),
            verbose=verbose,
        )

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        cache = _load_and_demux(self.source_data["file_path"], self.FXN_THRESHOLD_V)
        return cache[stream_name][0]

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        cache = _load_and_demux(self.source_data["file_path"], self.FXN_THRESHOLD_V)
        return cache[stream_name][1]

    def get_metadata(self) -> dict:
        from neuroconv.utils import dict_deep_update

        metadata = super().get_metadata()
        cache = _load_and_demux(self.source_data["file_path"], self.FXN_THRESHOLD_V)
        return dict_deep_update(
            metadata,
            {"NWBFile": {"session_start_time": cache["_datetime"]}},
        )
