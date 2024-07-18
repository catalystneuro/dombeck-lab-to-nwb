from neuroconv import BaseDataInterface
from neuroconv.utils import FilePathType
from pynwb import NWBFile, TimeSeries


class AxonBinaryTimeSeriesInterface(BaseDataInterface):
    """
    Data interface class for converting Axon Binary Format (ABF) files.
    """

    display_name = "Axon Binary Format Time Series Interface"
    associated_suffixes = ".abf"
    info = "Interface for writing Axon Binary Format (ABF) acquisition signals as TimeSeries to NWB."

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

        axon_binary_time_series_metadata = metadata["AxonBinaryTimeSeries"]

        end_frame = 2000 if stub_test else None

        assert all(
            [channel_id in self.reader.adcNames for channel_id in channel_id_to_time_series_name_mapping.keys()]
        ), "Some channel ids are not present in the ABF file."

        # Create TimeSeries for each data channel
        for channel_id, time_series_name in channel_id_to_time_series_name_mapping.items():
            channel_index = self.reader.adcNames.index(channel_id)
            time_series_metadata = axon_binary_time_series_metadata[time_series_name]

            axon_binary_time_series = TimeSeries(
                name=time_series_name,
                data=self.reader.data[channel_index, :end_frame].T,
                rate=float(self._sampling_frequency),
                description=time_series_metadata["description"],
                unit=time_series_metadata["unit"],
            )

            nwbfile.add_acquisition(axon_binary_time_series)
