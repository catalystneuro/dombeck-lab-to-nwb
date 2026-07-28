# Dombeck Lab — Chen et al. 2026 (LRRK2) Conversion Progress

**Manuscript:** "Leucine-rich repeat kinase 2 impairs the release sites of Parkinson's disease vulnerable dopamine axons", Chen, He et al. (in preparation)
**Analysis code:** https://github.com/DombeckLab/lrrk2_photometry_analysis (Zenodo: 10.5281/zenodo.20244434)
**Google Drive data:** https://drive.google.com/drive/u/0/folders/1Tw_es0etUGW8ttCysiUQYRJGnU0qeh3Q
**Conversion folder:** `src/dombeck_lab_to_nwb/chen2026/`
**Detailed data notes:** [`conversion_notes.md`](src/dombeck_lab_to_nwb/chen2026/conversion_notes.md), [`lrrk2_investigation.md`](src/dombeck_lab_to_nwb/chen2026/lrrk2_investigation.md)

**Progress: 27 / 27 sessions converted and uploaded to DANDI**
**Dandiset:** [DANDI:001933](https://dandiarchive.org/dandiset/001933) (embargoed draft)

---

## Pre-Conversion

- [x] Repo setup
- [x] Data inspection — ABF channel layout, `_data.mat` column layout, MATLAB HDF5 reference chain
- [x] Metadata extraction from manuscript — hardware, coordinates, virus, indicator
- [x] `general_metadata.yaml` — NWBFile fields, Subject fields, session/subject description templates
- [x] `fiber_photometry.yaml` — device models (optical fibers, LEDs, PMT, filters, dichroics), FiberPhotometryTable rows (4 rows: DLS×470, DLS×405, DMS×470, DMS×405), 12 response-series entries
- [x] `optogenetics.yaml` — OptogeneticStimulusSite (SNc), OptogeneticSeries, ChRmine device metadata (AAV5, Addgene #130998)
- [x] `environment.yaml` — conda env, Python 3.13, neuroconv from GitHub main, ndx-fiber-photometry ≥0.2.3, ndx-ophys-devices ≥0.3.1
- [x] ABF → animal ID mapping from `LRRK2-animal-list-meta.mat` — decoded via `_data.mat` filename field
- [x] Per-epoch power values decoded from `stimulation sequence LRRK2.xlsx` — stim_sequence 'a'/'b' resolved as pseudorandom power order; all 27 sessions populated
- [x] `convert_all_sessions.py` — batch script for all 27 animals (parallel, 4 workers, per-animal error logs)
- [ ] **Pending lab reply** — per-animal sex records, `initiation` channel meaning (Calb only), Calb DV fiber coordinate, Calb injection DV coordinate, publication DOI

---

## Dataset: Chen et al. 2026 — LRRK2 Fiber Photometry

27 animals total · 1 session per animal · two experimental groups

| Group | Cre line | Recording site | n animals | Animal IDs |
|-------|----------|----------------|-----------|------------|
| Anxa-LRRK2 | Anxa1-iCre | DLS (right) | 15 | 3742, 3743, 3947, 3948, 4004, 4005, 4007, 4253, 4398, 4401, 4558, 4561, 4651, 4652, 4885 |
| Calb-LRRK2 | Calb1-Cre | DMS (right) | 12 | 302, 306, 671, 673, 688, 740, 741, 848, 852, 935, 966, 1803 |

Genotypes per group: WT and LRRK2-G2019S (JAX:030961). Background: C57BL/6J. Age at surgery ~6 months.

---

### Fiber Photometry

#### Raw fluorescence (from ABF — 2 kHz, irregular timestamps post-demux)

- [x] `FiberPhotometryResponseSeriesRawSignal` — 470 nm functional channel (GRAB-DA3m)
- [x] `FiberPhotometryResponseSeriesIsosbesticControl` — 405 nm isosbestic control
- [x] Demux uses `fxn_gen` channel (>1 V → 470 nm; <1 V → 405 nm); transition samples discarded; module-level cache avoids double ABF read
- [x] Wired into converter and `convert_all_sessions.py`; all 27 sessions (Anxa + Calb)

#### CommandedVoltageSeries — LED switching waveform

- [x] `CommandedVoltageSeries` in `nwb.acquisition` — full 2 kHz `fxn_gen` square wave
- [x] Linked to both FiberPhotometryTable rows as `commanded_voltage_series` column
- [x] `frequency=100 Hz` (LED alternation), `rate=2000 Hz` (ADC sample rate)

#### Processed fluorescence (from `*_data.mat` — 100 Hz, camera-trigger timestamps)

- [x] `FiberPhotometryResponseSeriesCorrectedSignal` — baseline-corrected 470 nm (`corrected470`)
- [x] `FiberPhotometryResponseSeriesCorrectedIsosbesticControl` — baseline-corrected 405 nm (`corrected405`)
- [x] `FiberPhotometryResponseSeriesDfOverF` — % ΔF/F 470 nm, smoothed (`dff470`)
- [x] `FiberPhotometryResponseSeriesDfOverFIsosbesticControl` — % ΔF/F 405 nm (`dff405`)
- [x] Routed to `nwb.processing["ophys"]` (workaround override; TODO comment marks for future neuroconv PR)
- [x] Camera-trigger offset (~21 s) handled correctly: first trigger at ~21 s is the `starting_time` of all 100 Hz series
- [ ] Open neuroconv PR: add `parent_container: Literal["acquisition", "processing/ophys"]` to `BaseFiberPhotometryInterface.add_to_nwbfile`

---

### Behavior (from `*_data.mat` — 100 Hz, camera-trigger timestamps)

- [x] `treadmill_velocity` (m/s) → `BehavioralTimeSeries` in `nwb.processing["behavior"]`
- [x] `treadmill_acceleration` (m/s²) → same `BehavioralTimeSeries`
- [x] `Chen2026BehaviorInterface` implemented (`behavior_interface.py`); wired into converter and batch script

#### Raw treadmill voltage (from ABF — 2 kHz)

- [x] `RawTreadmillVoltage` → `TimeSeries` in `nwb.acquisition`; ABF `treadmill` channel, ~1.2–2.0 V
- [x] `Chen2026RawTreadmillInterface` implemented (`raw_treadmill_interface.py`); shares `_DEMUX_CACHE` with `Chen2026RawFiberPhotometryInterface`
- [x] Bug fixed (2026-07-27): stray `metadata=metadata` kwarg removed from `TimeSeries.__init__` call (caused `TypeError` for session 688)

---

### Optogenetics

#### Stimulation epochs (from `*_data.mat` TTL — merged to 64 trains)

- [x] `OptogeneticEpochsTable` in `nwb.intervals` — 64 trains per session (8 powers × 8 reps)
- [x] Per-epoch columns: `power_in_mW`, `pulse_length_in_ms`, `period_in_ms`, `number_pulses_per_pulse_train`, `wavelength_in_nm`, `number_trains`, `intertrain_interval_in_ms`
- [x] TTL fragmentation fix: blobs with gap < 1 s merged; all 27 sessions → exactly 64 epochs
- [x] `Chen2026OptogeneticsInterface` implemented (`optogenetics_interface.py`); per-epoch pulse params detected from raw ABF via `_detect_opto_pulse_params()` in `convert_session.py`
- [x] Powers populated from `stimulation sequence LRRK2.xlsx` for all 27 sessions

#### Optogenetic device metadata

- [x] `OptogeneticStimulusSite` — SNc, right hemisphere, Cre-dependent ChRmine, 635 nm
- [x] `OptogeneticSeries` metadata from `optogenetics.yaml`; wired into converter

---

### Session Metadata

- [x] `stim_sequence` — resolved as pseudorandom power order; per-epoch `power_in_mW` populated in epochs table from Excel sheet (no separate metadata field needed)

---

### Tutorials / Notebooks

- [x] `chen2026_demo.ipynb` — 11-section end-to-end demo (subject metadata → raw FP → CVS → processed FP → ΔF/F → behavior → opto epochs → ABF events → opto metadata → PSTH)

---

### Post-Conversion

- [x] Re-run batch conversion (27/27 sessions, all fixes applied)
- [x] Run NWBInspector with `--config dandi` — 0 violations, 1 unresolvable suggestion (`OptogeneticSitesTable` single-row, structural constraint of ndx-optogenetics)
- [x] Fix NWBInspector findings — `RawTreadmillVoltage` rate/starting_time, missing descriptions on viral vector injections and LED model
- [x] Setup Dandiset — [DANDI:001933](https://dandiarchive.org/dandiset/001933) (embargoed draft, created 2026-07-27)
- [x] Upload all 27 NWB files to DANDI — 572.9 MB, 0 errors (2026-07-27); files organized with `dandi organize --files-mode move`, `_behavior` suffix added by DANDI per detected NWB data types
- [x] Confirm per-animal sex records with lab and update `Subject.sex` (currently `U` for all) — re-upload affected files after update
- [x] Update `NWBFile.related_publications` with preprint DOI (https://doi.org/10.1101/2025.08.28.672006) — re-converted and re-uploaded all 27 files (2026-07-28)

---

## Open Questions (lab confirmation needed)

| # | Question | Affects |
|---|----------|---------|
| 1 | Calb group DV fiber coordinate | `FiberInsertion.depth_in_mm` (currently estimated from ferrule length 3 mm) |
| 2 | Calb group GRAB-DA3m injection DV | `FiberPhotometryVirusInjection.dv_in_mm` (currently `2.9` estimate) |
| 3 | Hamamatsu H10770PA-40 gain value | `PhotodetectorModel.gain` |
