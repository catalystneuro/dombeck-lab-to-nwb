"""Raw ABF events interface for Chen et al. 2026 (LRRK2 dataset).

Reads the opto_TTL channel from the raw ABF file and writes individual
optogenetic pulses as an ``OptoPulse`` ``EventsTable`` in ``nwbfile.events``.

  OptoPulse — individual optogenetic pulses (interval events)
      (ABF channel 'opto_TTL', 2000 Hz)
      Pulse-level events complementing the train-level OptogeneticEpochsTable.
      Both halves of the session are detectable at 2 kHz (threshold 0.01 V):
        epochs 0-31  (~1.2 V): 32 pulses per train, 9 ms on / 1 ms off
        epochs 32-63 (~0.05 V): 32 pulses per train, 8 ms on / 8 ms off

Note: camera frame trigger times are not stored as a separate EventsTable because
they are already the explicit timestamps of every 100 Hz processed series
(corrected FP, ΔF/F, velocity, acceleration) and duplicating ~129k rows would
add significant write time without new information.
"""

from pathlib import Path

import numpy as np
from neuroconv.datainterfaces.events.baseeventsinterface import BaseEventsInterface, _EventsData


_OPTO_THRESHOLD_V = 0.01  # V — threshold for opto_TTL (catches both ~1.2 V and ~0.05 V trains)
_SAMPLE_RATE = 2000.0  # Hz — ABF acquisition rate


class Chen2026ABFEventsInterface(BaseEventsInterface):
    """Individual optogenetic pulse events from the raw ABF opto_TTL channel.

    Writes one ``EventsTable`` in ``nwbfile.events``:

    * ``OptoPulse`` — ~2048 interval events (onset + duration per pulse;
      32 pulses × 64 trains). Complements the train-level
      ``OptogeneticEpochsTable`` in ``nwbfile.intervals``.
    """

    display_name = "Chen2026 ABF Events (opto pulses)"
    associated_suffixes = (".abf",)
    info = "Interface for individual optogenetic pulse events from the ABF opto_TTL channel."

    metadata_key = "ABFEvents"

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata.setdefault("Events", {})[self.metadata_key] = {
            "event_types": {
                "opto_pulse": {
                    "event_name": "OptoTTL",
                    "event_description": (
                        "Individual optogenetic pulse from the raw ABF opto_TTL channel (2000 Hz, "
                        "threshold 0.01 V). Each row is one TTL-high pulse; timestamp is the rising "
                        "edge and duration is the pulse width in seconds. Complements the train-level "
                        "OptogeneticEpochsTable: epochs 0-31 (~1.2 V) have 32 pulses at ~9 ms each; "
                        "epochs 32-63 (~0.05 V) have 32 pulses at ~8 ms each."
                    ),
                },
            }
        }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        if self._events_data_dict is not None:
            return self._events_data_dict

        import pyabf

        abf = pyabf.ABF(self.source_data["file_path"], loadData=True)
        channel_names = [abf.adcNames[i].strip() for i in range(abf.channelCount)]

        # ── opto pulse (interval events) ─────────────────────────────────────
        opto_idx = channel_names.index("opto_TTL")
        opto = abf.data[opto_idx]
        above_opto = opto > _OPTO_THRESHOLD_V
        diff_opto = np.diff(above_opto.astype(np.int8))
        rising = np.where(diff_opto == 1)[0]
        falling = np.where(diff_opto == -1)[0]

        # Align rising/falling pairs: discard an unpaired leading falling edge
        if len(falling) and len(rising) and falling[0] < rising[0]:
            falling = falling[1:]
        n_pulses = min(len(rising), len(falling))
        rising = rising[:n_pulses]
        falling = falling[:n_pulses]

        self._events_data_dict = {
            "opto_pulse": _EventsData(
                event_type_source_id="opto_pulse",
                timestamps=rising / _SAMPLE_RATE,
                durations=(falling - rising) / _SAMPLE_RATE,
            ),
        }
        return self._events_data_dict
