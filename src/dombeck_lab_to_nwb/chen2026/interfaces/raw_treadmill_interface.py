"""Raw treadmill analog interface for Chen et al. 2026 (LRRK2 dataset).

Stores the raw rotary-encoder voltage from the ABF 'treadmill' channel as a
TimeSeries in nwb.acquisition for data provenance.  Velocity and acceleration
derived from this signal are in nwb.processing['behavior'].

Shares the module-level _DEMUX_CACHE with Chen2026RawFiberPhotometryInterface,
so the ABF file is only read once regardless of instantiation order.
"""

from pathlib import Path

from neuroconv import BaseDataInterface


class Chen2026RawTreadmillInterface(BaseDataInterface):
    """Raw rotary-encoder voltage from the ABF treadmill channel (Chen et al. 2026)."""

    display_name = "Chen2026 Raw Treadmill Voltage (ABF)"
    associated_suffixes = (".abf",)
    info = "Interface for raw treadmill analog voltage from Axon Binary Format files."

    SERIES_NAME = "RawTreadmillVoltage"

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def add_to_nwbfile(self, nwbfile, metadata, **conversion_options):
        from pynwb.base import TimeSeries

        from .raw_fiber_photometry_interface import _load_and_demux

        if self.SERIES_NAME in nwbfile.acquisition:
            return

        cache = _load_and_demux(self.source_data["file_path"])
        data, timestamps = cache["treadmill"]

        treadmill_series = TimeSeries(
            name=self.SERIES_NAME,
            data=data,
            timestamps=timestamps,
            metadata=metadata,
            unit="V",
        )
        nwbfile.add_acquisition(treadmill_series)
