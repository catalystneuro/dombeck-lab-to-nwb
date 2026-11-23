"""Raw trigger channels interface for Chen et al. 2026 (LRRK2 dataset).

Stores the 'opto_TTL' and 'camera' channels of the ABF file as TimeSeries in
nwb.acquisition, so that the stimulation onsets and the 100 Hz binning of the
processed series can be recomputed from the raw recording.

Shares the module-level _DEMUX_CACHE with Chen2026RawFiberPhotometryInterface,
so the ABF file is only read once regardless of instantiation order.
"""

from pathlib import Path

from neuroconv import BaseDataInterface


class Chen2026RawTriggersInterface(BaseDataInterface):
    """Raw optogenetic stimulation and camera trigger voltages from the ABF file (Chen et al. 2026)."""

    display_name = "Chen2026 Raw Trigger Voltages (ABF)"
    associated_suffixes = (".abf",)
    info = "Interface for the raw opto_TTL and camera channels of Axon Binary Format files."

    # ABF channel name → (series name, description)
    SERIES = {
        "opto_TTL": (
            "RawOptoStimulationVoltage",
            "Raw 'opto_TTL' channel of the ABF file acquired at 2000 Hz, which marks the pulses of the 635 nm "
            "optogenetic stimulation. The pulse amplitude increases with the commanded light power, from about "
            "0.05 to 0.15 V at 0.1 mW to about 2.45 V at 4 mW. The pulse parameters in OptogeneticEpochsTable "
            "are measured from this signal with a threshold of 0.01 V.",
        ),
        "camera": (
            "RawCameraTriggerVoltage",
            "Raw 'camera' channel of the ABF file acquired at 2000 Hz. Each rising edge (threshold 1 V) is one "
            "camera trigger. The processed 100 Hz series (corrected fluorescence, dF/F, treadmill velocity and "
            "acceleration) are binned on these triggers and use their times as timestamps.",
        ),
    }

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def add_to_nwbfile(self, nwbfile, metadata, **conversion_options):
        from pynwb.base import TimeSeries

        from neuroconv.utils.checks import calculate_regular_series_rate

        from .raw_fiber_photometry_interface import _load_and_demux

        cache = _load_and_demux(self.source_data["file_path"])
        for channel_name, (series_name, description) in self.SERIES.items():
            data, timestamps = cache[channel_name]
            rate = calculate_regular_series_rate(timestamps)
            nwbfile.add_acquisition(
                TimeSeries(
                    name=series_name,
                    data=data,
                    description=description,
                    starting_time=float(timestamps[0]),
                    rate=rate,
                    unit="V",
                )
            )
