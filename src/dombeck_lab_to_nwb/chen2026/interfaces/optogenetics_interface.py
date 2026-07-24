"""Optogenetics interface for Chen et al. 2026 (LRRK2 dataset).

Reads the binary TTL column from the per-animal *_data.mat file (100 Hz,
camera-trigger-aligned binning) and writes:

  - ``OptogeneticExperimentMetadata`` (lab_meta_data): LED, fiber, virus, injection, effector
  - ``OptogeneticEpochsTable`` (intervals): one row per contiguous TTL-on epoch

Confirmed stim parameters (from manuscript):
  - pulse_length_in_ms = 8.0 ms, period_in_ms = 16.0 ms (8 ms on / 8 ms off)
  - ~31 pulses per 500 ms train; trains spaced ≥ 20 s apart; 8 reps per power level
  - Powers (pseudorandom order): 0.1, 0.5, 1.0, 4.0 mW — varies per epoch; leave as NaN
    until per-epoch power can be read from stim_sequence data.
"""

import math
from pathlib import Path

import numpy as np
from neuroconv.basedatainterface import BaseDataInterface
from pynwb import NWBFile

from .processed_fiber_photometry_interface import _read_mat


class Chen2026OptogeneticsInterface(BaseDataInterface):
    """Optogenetics interface for Chen et al. 2026 (LRRK2 dataset).

    Reads the 100 Hz binary TTL column from the per-animal *_data.mat file and
    writes an ``OptogeneticEpochsTable`` (one row per contiguous stimulation epoch)
    plus full ``OptogeneticExperimentMetadata`` (LED, fiber, virus, effector).
    """

    display_name = "Chen2026 Optogenetics (*_data.mat TTL)"
    associated_suffixes = (".mat",)
    info = "Interface for optogenetic stimulation epochs from the TTL column of *_data.mat."

    def __init__(self, *, file_path: str | Path, verbose: bool = False):
        super().__init__(file_path=str(file_path), verbose=verbose)

    def _get_ttl(self) -> np.ndarray:
        return _read_mat(self.source_data["file_path"])["TTL"]

    @staticmethod
    def _extract_epochs(ttl: np.ndarray, trigger_times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (start_times_s, stop_times_s) for each contiguous block of TTL=1.

        Uses actual camera trigger timestamps so epoch times are aligned to the
        ABF recording clock (same reference as the raw FP acquisition).
        """
        padded = np.concatenate([[0], ttl.astype(np.int8), [0]])
        diff = np.diff(padded)
        # diff[k]==1  → ttl transitions 0→1 at index k  → trigger_times[k]
        # diff[k]==-1 → ttl transitions 1→0 after index k-1; stop = trigger_times[k]
        #   (or last trigger + 1 sample if k == len(trigger_times))
        start_indices = np.where(diff == 1)[0]
        stop_indices = np.where(diff == -1)[0]
        n = len(trigger_times)
        dt = trigger_times[-1] - trigger_times[-2] if n >= 2 else 0.01
        start_times = trigger_times[start_indices]
        stop_times = np.array([trigger_times[k] if k < n else trigger_times[-1] + dt for k in stop_indices])
        return start_times, stop_times

    def _add_optogenetics_metadata(self, nwbfile: NWBFile, opto_meta: dict, power_in_mW: float):
        """Build all device + provenance objects and add OptogeneticExperimentMetadata.

        Returns the populated ``OptogeneticSitesTable`` for use in ``OptogeneticEpochsTable``.
        """
        from ndx_ophys_devices import Effector, FiberInsertion, ViralVector, ViralVectorInjection
        from ndx_optogenetics import (
            ExcitationSource,
            ExcitationSourceModel,
            OpticalFiber,
            OpticalFiberModel,
            OptogeneticEffectors,
            OptogeneticExperimentMetadata,
            OptogeneticSitesTable,
            OptogeneticViruses,
            OptogeneticVirusInjections,
        )

        # ExcitationSourceModel
        esm_meta = opto_meta.get("ExcitationSourceModel", {})
        laser_model_kwargs = dict(
            name=esm_meta["name"],
            source_type=esm_meta.get("source_type"),
            excitation_mode=esm_meta.get("excitation_mode"),
            wavelength_range_in_nm=esm_meta.get("wavelength_range_in_nm"),
        )
        if esm_meta.get("manufacturer"):
            laser_model_kwargs["manufacturer"] = esm_meta["manufacturer"]
        if esm_meta.get("model_number"):
            laser_model_kwargs["model_number"] = esm_meta["model_number"]
        laser_model = ExcitationSourceModel(**laser_model_kwargs)
        nwbfile.add_device_model(laser_model)

        # ExcitationSource
        es_meta = opto_meta.get("ExcitationSource", {})
        laser_kwargs = dict(
            name=es_meta["name"],
            description=es_meta.get("description", ""),
            model=laser_model,
        )
        if not math.isnan(power_in_mW):
            laser_kwargs["power_in_W"] = power_in_mW / 1000.0
        laser = ExcitationSource(**laser_kwargs)
        nwbfile.add_device(laser)

        # OpticalFiberModel
        ofm_meta = opto_meta.get("OpticalFiberModel", {})
        fiber_model = OpticalFiberModel(
            name=ofm_meta["name"],
            description=ofm_meta.get("description", ""),
            manufacturer=ofm_meta.get("manufacturer"),
            model_number=ofm_meta.get("model_number"),
            numerical_aperture=float(ofm_meta["numerical_aperture"]),
            core_diameter_in_um=float(ofm_meta["core_diameter_in_um"]),
            ferrule_name=ofm_meta.get("ferrule_name"),
            ferrule_diameter_in_mm=float(ofm_meta["ferrule_diameter_in_mm"])
            if ofm_meta.get("ferrule_diameter_in_mm")
            else None,
        )
        nwbfile.add_device_model(fiber_model)

        # OpticalFiber instances
        fiber_objects: dict[str, OpticalFiber] = {}
        for spec in opto_meta.get("OpticalFibers", []):
            insertion = FiberInsertion(
                name="fiber_insertion",
                insertion_position_ap_in_mm=spec.get("insertion_position_ap_in_mm"),
                insertion_position_ml_in_mm=spec.get("insertion_position_ml_in_mm"),
                insertion_position_dv_in_mm=spec.get("insertion_position_dv_in_mm"),
                position_reference=spec.get("position_reference"),
                hemisphere=spec.get("hemisphere"),
            )
            fiber = OpticalFiber(
                name=spec["name"],
                description=spec.get("description", ""),
                model=fiber_model,
                fiber_insertion=insertion,
            )
            nwbfile.add_device(fiber)
            fiber_objects[spec["name"]] = fiber

        # ViralVector
        vv_meta = opto_meta.get("ViralVector", {})
        virus = ViralVector(
            name=vv_meta["name"],
            construct_name=vv_meta["construct_name"],
            manufacturer=vv_meta.get("manufacturer"),
            titer_in_vg_per_ml=float(vv_meta["titer_in_vg_per_ml"]),
            description=vv_meta.get("description", ""),
        )

        # VirusInjections
        injection_objects: dict[str, ViralVectorInjection] = {}
        hemisphere_to_injection: dict[str, str] = {}
        for spec in opto_meta.get("VirusInjections", []):
            inj = ViralVectorInjection(
                name=spec["name"],
                location=spec["location"],
                hemisphere=spec["hemisphere"],
                reference=spec.get("reference"),
                ap_in_mm=spec["ap_in_mm"],
                ml_in_mm=spec["ml_in_mm"],
                dv_in_mm=spec["dv_in_mm"],
                volume_in_uL=spec["volume_in_uL"],
                viral_vector=virus,
                description=spec.get("description", ""),
            )
            injection_objects[spec["name"]] = inj
            hemisphere_to_injection[spec["hemisphere"]] = spec["name"]

        # Effectors
        effector_objects: list[Effector] = []
        for spec in opto_meta.get("Effectors", []):
            hemi = spec.get("hemisphere", "right")
            inj_obj = injection_objects.get(hemisphere_to_injection.get(hemi))
            effector = Effector(
                name=spec["name"],
                label=spec["label"],
                description=spec.get("description", ""),
                manufacturer=spec.get("manufacturer"),
                viral_vector_injection=inj_obj,
            )
            effector_objects.append(effector)

        # OptogeneticSitesTable
        sites_meta = opto_meta.get("OptogeneticSitesTable", {})
        sites_table = OptogeneticSitesTable(description=sites_meta.get("description", "Optogenetic stimulation sites."))
        fiber_names = list(fiber_objects.keys())
        for i, fiber_name in enumerate(fiber_names):
            effector = effector_objects[i] if i < len(effector_objects) else effector_objects[0]
            sites_table.add_row(
                excitation_source=laser,
                optical_fiber=fiber_objects[fiber_name],
                effector=effector,
            )

        # OptogeneticExperimentMetadata
        opto_experiment = OptogeneticExperimentMetadata(
            stimulation_software=opto_meta.get("stimulation_software", "unknown"),
            optogenetic_sites_table=sites_table,
            optogenetic_effectors=OptogeneticEffectors(effectors=effector_objects),
            optogenetic_viruses=OptogeneticViruses(viral_vectors=[virus]),
            optogenetic_virus_injections=OptogeneticVirusInjections(
                viral_vector_injections=list(injection_objects.values())
            ),
        )
        nwbfile.add_lab_meta_data(opto_experiment)

        return sites_table

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        # Pulse-level stim parameters — fill from lab once confirmed; NaN/−1 until then.
        pulse_length_in_ms: float = math.nan,
        period_in_ms: float = math.nan,
        number_pulses_per_pulse_train: int = -1,
        number_trains: int = -1,
        intertrain_interval_in_ms: float = math.nan,
        power_in_mW: float = math.nan,
    ) -> None:
        import ndx_optogenetics  # noqa: F401 — register namespace
        from ndx_optogenetics import OptogeneticEpochsTable

        opto_meta = (metadata or {}).get("Optogenetics", {})
        excitation_lambda = float(opto_meta.get("excitation_lambda", 635.0))

        sites_table = self._add_optogenetics_metadata(nwbfile=nwbfile, opto_meta=opto_meta, power_in_mW=power_in_mW)

        # Extract stimulation epochs using camera trigger timestamps for ABF-clock alignment
        ttl = self._get_ttl()
        trigger_times = _read_mat(self.source_data["file_path"])["camera_trigger_times"]
        if stub_test:
            ttl = ttl[:100]
            trigger_times = trigger_times[:100]

        start_times, stop_times = self._extract_epochs(ttl, trigger_times)
        if len(start_times) == 0:
            return

        epochs_meta = opto_meta.get("OptogeneticEpochsTable", {})
        epochs_table = OptogeneticEpochsTable(
            name=epochs_meta.get("name", "OptogeneticEpochsTable"),
            description=epochs_meta.get("description", "Optogenetic stimulation epochs."),
            target_tables={"optogenetic_sites": sites_table},
        )

        site_indices = list(range(len(sites_table)))
        for start, stop in zip(start_times, stop_times):
            epochs_table.add_row(
                start_time=float(start),
                stop_time=float(stop),
                stimulation_on=True,
                pulse_length_in_ms=pulse_length_in_ms,
                period_in_ms=period_in_ms,
                number_pulses_per_pulse_train=number_pulses_per_pulse_train,
                number_trains=number_trains,
                intertrain_interval_in_ms=intertrain_interval_in_ms,
                power_in_mW=power_in_mW,
                wavelength_in_nm=excitation_lambda,
                optogenetic_sites=site_indices,
            )

        nwbfile.add_time_intervals(epochs_table)
