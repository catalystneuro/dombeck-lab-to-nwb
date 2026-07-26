"""Raw ABF events interface for Chen et al. 2026 (LRRK2 dataset).

Reads two TTL channels from the raw ABF file and writes them as
``pynwb.event.EventsTable`` objects in ``nwbfile.events``:

  CameraFrameTrigger  — rising edges of the camera frame-sync TTL
      (ABF channel 'camera', 100 Hz, point events)
      Each timestamp is the onset of one camera frame and the shared time base
      for all 100 Hz processed signals in the companion *_data.mat file.

  OptoPulse           — individual optogenetic pulses from the raw TTL
      (ABF channel 'opto_TTL', 2000 Hz, interval events)
      Pulse-level events complementing the train-level OptogeneticEpochsTable.
      Both halves of the session are detectable at 2 kHz (threshold 0.01 V):
        epochs 0-31  (~1.2 V): 32 pulses per train, 9 ms on / 1 ms off
        epochs 32-63 (~0.05 V): 32 pulses per train, 8 ms on / 8 ms off
"""

from pathlib import Path

import numpy as np
from neuroconv.datainterfaces.events.baseeventsinterface import BaseEventsInterface, _EventsData


_CAMERA_THRESHOLD_V = 1.0  # V — rising-edge threshold for camera TTL
_OPTO_THRESHOLD_V = 0.01  # V — threshold for opto_TTL (catches both ~1.2 V and ~0.05 V trains)
_SAMPLE_RATE = 2000.0  # Hz — ABF acquisition rate


class Chen2026ABFEventsInterface(BaseEventsInterface):
    """Camera frame-trigger and opto pulse events from the raw ABF file.

    Writes two ``EventsTable`` objects in ``nwbfile.events``:

    * ``CameraFrameTrigger`` — ~129 k timestamp-only point events (one per frame).
    * ``OptoPulse``          — ~2048 interval events (onset + duration for each
      individual optogenetic pulse; 32 pulses × 64 trains).
    """

    display_name = "Chen2026 ABF Events (camera trigger + opto pulses)"
    associated_suffixes = (".abf",)
    info = "Interface for camera frame-trigger and optogenetic pulse events from the ABF file."

    metadata_key = "ABFEvents"

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata.setdefault("Events", {})[self.metadata_key] = {
            "event_types": {
                "camera_trigger": {
                    "event_name": "CameraFrameTrigger",
                    "event_description": ("Rising edge of the camera frame-sync TTL."),
                },
                "opto_pulse": {
                    "event_name": "OptoTTL",
                    "event_description": (
                        "Individual optogenetic pulse from the raw ABF opto_TTL channel (2000 Hz, "
                        "threshold 0.01 V). Each row is one TTL-high pulse; start_time is the rising "
                        "edge and duration is the pulse width. Complements the train-level "
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

        # ── camera frame trigger (point events) ──────────────────────────────
        cam_idx = channel_names.index("camera")
        cam = abf.data[cam_idx]
        above_cam = cam > _CAMERA_THRESHOLD_V
        cam_rising = np.where(np.diff(above_cam.astype(np.int8)) == 1)[0]
        cam_timestamps = cam_rising / _SAMPLE_RATE

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

        opto_timestamps = rising / _SAMPLE_RATE
        opto_durations = (falling - rising) / _SAMPLE_RATE

        self._events_data_dict = {
            "camera_trigger": _EventsData(
                event_type_source_id="camera_trigger",
                timestamps=cam_timestamps,
            ),
            "opto_pulse": _EventsData(
                event_type_source_id="opto_pulse",
                timestamps=opto_timestamps,
                durations=opto_durations,
            ),
        }
        return self._events_data_dict
