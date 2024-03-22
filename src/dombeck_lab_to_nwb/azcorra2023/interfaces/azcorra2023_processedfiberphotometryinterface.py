from pathlib import Path

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
        self.fiber_depth = dict(
            chGreen=processed_photometry_data["depthG"],
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

        # Add Subject metadata
        subject_id = f"{self.subject_metadata['experiment_type']}-{self.subject_metadata['mouse']}"
        metadata["Subject"].update(
            subject_id=subject_id,
            sex=self.subject_metadata["sex"].upper(),
            species="Mus musculus",
            age="P8W/P16W",  # 2–4 months old
        )

        # Mouse strains - C57BL6 background, used as adults 2-5 months old:
        # 1. Aldh1a1-2A-iCre (new line)
        # 2. Anxa1-iCre (new line)
        # 3. Calb1-IRES2-Cre, The Jackson Laboratory Strain #:028532,RRID:IMSR_JAX:028532
        # 4. VGlut2-IRES-Cre, The Jackson Laboratory Strain #:016963RRID:IMSR_JAX:016963
        # 5. DAT-CRE, The Jackson Laboratory Strain #:020080,RRID:IMSR_JAX:020080
        # 6. Th-2A-Flpo, from Poulin et al., 2018
        # 7. DAT-PF-tTA, The Jackson Laboratory Strain#:027178,RRID:IMSR_JAX:027178
        # 8. Ai93D (TITL-GCaMP6f), The Jackson Laboratory Strain #:024107,RRID:IMSR_JAX:024107
        # 9. CAG-Sun1/sfGFP, The Jackson Laboratory Strain #:021039,RRID:IMSR_JAX:021039

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
