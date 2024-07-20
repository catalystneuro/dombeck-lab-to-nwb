import numpy as np
import pandas as pd
from ndx_events import TtlTypesTable, TtlsTable
from neuroconv import BaseDataInterface
from neuroconv.tools.signal_processing import get_falling_frames_from_ttl, get_rising_frames_from_ttl
from neuroconv.utils import FilePathType
from pynwb import NWBFile, TimeSeries


class AxonBinaryInterface(BaseDataInterface):
    """
    Base class for data interfaces for converting Axon Binary Format (ABF) files.
    """

    def __init__(
        self,
        file_path: FilePathType,
        verbose: bool = True,
    ):
        """
        Load and prepare raw data and corresponding metadata from the ABF files.

        Parameters
        ----------
        file_path: FilePathType
            The path to the ABF file.
        verbose: bool, default: True
            controls verbosity.
        """
        from pyabf import ABF

        if not file_path.endswith(".abf"):
            raise IOError(f"The file '{file_path}' is not an ABF file.")

        super().__init__(verbose=verbose, file_path=file_path)

        self.reader = ABF(abfFilePath=file_path, loadData=True)
        self._sampling_frequency = self.reader.dataRate

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            session_start_time=self.reader.abfDateTime,
            session_id=self.reader.abfID.replace("_", "-"),
        )
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, **conversion_options):
        raise NotImplementedError("This method should be implemented in the child class.")


class AxonBinaryTimeSeriesInterface(AxonBinaryInterface):
    """
    Data interface class for converting Axon Binary Format (ABF) files.
    """

    display_name = "Axon Binary Format Time Series Interface"
    associated_suffixes = ".abf"
    info = "Interface for writing Axon Binary Format (ABF) acquisition signals as TimeSeries to NWB."

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["AxonBinaryTimeSeries"] = dict(
            Fluorescence=dict(
                name="Fluorescence",
                description=f"The fluorescence traces collected at {self._sampling_frequency} Hz by Axon Instruments.",
                unit="Volts",
            ),
            Velocity=dict(
                name="Velocity",
                description=f"Velocity from treadmill at {self._sampling_frequency} Hz by Axon Instruments.",
                unit="Volts",
            ),
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_id_to_time_series_name_mapping: dict,
        stub_test: bool = False,
    ) -> None:
        end_frame = 2000 if stub_test else None

        axon_binary_time_series_metadata = metadata["AxonBinaryTimeSeries"]

        assert all(
            [channel_id in self.reader.adcNames for channel_id in channel_id_to_time_series_name_mapping.keys()]
        ), "Some channel ids are not present in the ABF file."

        # Create TimeSeries for each data channel
        for channel_id, time_series_name in channel_id_to_time_series_name_mapping.items():
            if time_series_name not in axon_binary_time_series_metadata:
                raise ValueError(f"Time series '{time_series_name}' not found in metadata.")

            time_series_metadata = axon_binary_time_series_metadata[time_series_name]

            channel_index = self.reader.adcNames.index(channel_id)

            axon_binary_time_series = TimeSeries(
                name=time_series_name,
                data=self.reader.data[channel_index, :end_frame],
                rate=float(self._sampling_frequency),
                description=time_series_metadata["description"],
                unit=time_series_metadata["unit"],
            )

            nwbfile.add_acquisition(axon_binary_time_series)


class AxonBinaryTtlInterface(AxonBinaryInterface):
    """
    Data interface class for converting Axon Binary Format (ABF) files.
    """

    display_name = "Axon Binary Format TTL Interface"
    associated_suffixes = ".abf"
    info = "Interface for writing Axon Binary Format (ABF) TTL signals as TTLEvents to NWB."

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        metadata["Events"] = dict(
            TtlTypesTable=dict(
                description="Contains the TTL event types.",
            ),
            TtlsTable=dict(
                description="Contains the 405 nm and 470 nm illumination onset times.",
            ),
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        stub_test: bool = False,
    ) -> None:
        end_frame = 2000 if stub_test else None
        events_metadata = metadata["Events"]
        ttls_table_name = "TtlsTable"

        assert ttls_table_name not in nwbfile.acquisition, f"The {ttls_table_name} is already in nwbfile."

        ttl_types_table = TtlTypesTable(**events_metadata["TtlTypesTable"])
        ttl_types_table.add_column(name="duration", description="The duration of the TTL pulse.")

        ttl_types_table.add_row(
            event_name="Ch405",
            event_type_description="The times when the 405 nm LED was on.",
            pulse_value=np.uint8(1),
            duration=0.005,
        )
        ttl_types_table.add_row(
            event_name="Ch470",
            event_type_description="The times when the 470 nm LED was on.",
            pulse_value=np.uint8(1),
            duration=0.005,
        )

        ttls_table = TtlsTable(**events_metadata["TtlsTable"], target_tables={"ttl_type": ttl_types_table})

        channel_index = self.reader.adcNames.index("fxn_gen")
        traces = self.reader.data[channel_index, :end_frame]

        ttls_dfs = []
        ch405_event_times = get_falling_frames_from_ttl(traces)
        times = np.arange(traces.shape[0]) / self._sampling_frequency
        ch405_timestamps = times[ch405_event_times] if not stub_test else times[ch405_event_times]

        ttls_dfs.append(
            pd.DataFrame(
                {
                    "timestamp": ch405_timestamps,
                    "ttl_type": [0] * len(ch405_timestamps),
                    # NOT the pulse value, but a row index into the ttl_types_table
                    "duration": [0.005] * len(ch405_timestamps),
                }
            )
        )

        ch470_event_times = get_rising_frames_from_ttl(traces)
        ch470_timestamps = times[ch470_event_times] if not stub_test else times[ch470_event_times]

        ttls_dfs.append(
            pd.DataFrame(
                {
                    "timestamp": ch470_timestamps,
                    "ttl_type": [1] * len(ch470_timestamps),
                    # NOT the pulse value, but a row index into the ttl_types_table
                    "duration": [0.005] * len(ch470_timestamps),
                }
            )
        )

        ttls_to_add = pd.concat(ttls_dfs, ignore_index=True)
        ttls_to_add["ttl_type"] = ttls_to_add["ttl_type"].astype(np.uint8)
        ttls_to_add = ttls_to_add.sort_values("timestamp")

        for row_index, row in ttls_to_add.reset_index(drop=True).iterrows():
            ttls_table.add_row(
                timestamp=row["timestamp"],
                ttl_type=row["ttl_type"],
                check_ragged=False,
                id=row_index,
            )
        nwbfile.add_acquisition(ttl_types_table)
        nwbfile.add_acquisition(ttls_table)
