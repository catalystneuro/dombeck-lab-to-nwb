# Dombeck Lab — Chen et al. 2026 (LRRK2) Conversion Progress

**Manuscript:** "Leucine-rich repeat kinase 2 impairs the release sites of Parkinson's disease vulnerable dopamine axons", Chen, He et al. (in preparation)
**Analysis code:** https://github.com/DombeckLab/lrrk2_photometry_analysis (Zenodo: 10.5281/zenodo.20244434)
**Google Drive data:** https://drive.google.com/drive/u/0/folders/1Tw_es0etUGW8ttCysiUQYRJGnU0qeh3Q
**Conversion folder:** `src/dombeck_lab_to_nwb/chen2026/`
**Detailed data notes:** [`conversion_notes.md`](src/dombeck_lab_to_nwb/chen2026/conversion_notes.md), [`lrrk2_investigation.md`](src/dombeck_lab_to_nwb/chen2026/lrrk2_investigation.md)

**Progress: 0 / 27 sessions converted**

---

## Pre-Conversion

- [x] Repo setup
- [x] Data inspection — ABF channel layout, `_data.mat` column layout, MATLAB HDF5 reference chain
- [x] Metadata extraction from manuscript — hardware, coordinates, virus, indicator
- [x] `general_metadata.yaml` — NWBFile fields, Subject fields, session/subject description templates
- [x] `fiber_photometry.yaml` — device models (optical fibers, LEDs, PMT, filters, dichroics), FiberPhotometryTable rows (4 rows: DLS×470, DLS×405, DMS×470, DMS×405), 12 response-series entries
- [x] `environment.yaml` — conda env, Python 3.13, neuroconv from GitHub main, ndx-fiber-photometry ≥0.2.3, ndx-ophys-devices ≥0.3.1
- [x] Raw fiber photometry interface (`raw_fiber_photometry_interface.py`) — demultiplexes 470/405 nm from ABF using `fxn_gen` channel; module-level cache avoids double ABF read
- [x] Processed fiber photometry interface (`processed_fiber_photometry_interface.py`) — reads `*_data.mat` (MATLAB v7.3 HDF5 via h5py reference chain); exposes corrected470, corrected405, dff470, dff405 at 100 Hz
- [x] `Chen2026NWBConverter` — RawSignal + IsosbesticControl interfaces wired
- [x] Stub test passes — Anxa group, animal 4007, session 2025-01-24-0002 ✓
- [x] Stub test — Calb group (need to download a Calb ABF)
- [x] ABF → animal ID mapping from `LRRK2-animal-list-meta.mat` (which ABF file corresponds to which animal?)
- [x] `convert_all_sessions.py` — batch script for all 27 animals
- [ ] **Pending lab reply** — per-animal sex records, `stim_sequence` 'a' vs 'b' meaning, `initiation` channel meaning (Calb only), Calb DV fiber coordinate, Calb injection DV coordinate, publication DOI, experimenter name(s)

---

## Dataset: Chen et al. 2026 — LRRK2 Fiber Photometry

27 animals total · 1 session per animal · two experimental groups

| Group | Cre line | Recording site | n animals | Animal IDs |
|-------|----------|----------------|-----------|------------|
| Anxa-LRRK2 | Anxa1-iCre | DLS (right) | 15 | 3742, 3743, 3947, 3948, 4004, 4005, 4007, 4253, 4398, 4401, 4558, 4561, 4651, 4652, 4885 |
| Calb-LRRK2 | Calb1-Cre | DMS (right) | 12 | 302, 306, 671, 673, 688, 740, 741, 848, 852, 935, 966, 1803 |

Genotypes per group: WT and LRRK2-G2019S (JAX:030961). Background: C57BL/6J. Age at surgery ~6 months.

### Fiber Photometry

#### Raw fluorescence (from ABF — 2 kHz, irregular timestamps post-demux)

- [x] `FiberPhotometryResponseSeriesRawSignal` — 470 nm functional channel (GRAB-DA3m)
- [x] `FiberPhotometryResponseSeriesIsosbesticControl` — 405 nm isosbestic control
- [x] Interfaces implemented and stub tested (Anxa group)
- [x] Enable for Calb group (stub test)
- [x] Wire into `convert_all_sessions.py`

#### Processed fluorescence (from `*_data.mat` — 100 Hz, regular timestamps)

- [ ] `FiberPhotometryResponseSeriesCorrectedSignal` — baseline-corrected 470 nm (`corrected470`)
- [ ] `FiberPhotometryResponseSeriesCorrectedIsosbesticControl` — baseline-corrected 405 nm (`corrected405`)
- [ ] `FiberPhotometryResponseSeriesDfOverF` — % ΔF/F 470 nm, smoothed (`dff470`)
- [ ] `FiberPhotometryResponseSeriesDfOverFIsosbesticControl` — % ΔF/F 405 nm (`dff405`)
- [ ] Processed interface implemented (`processed_fiber_photometry_interface.py`)
- [ ] Wire processed interfaces back into `Chen2026NWBConverter` and `convert_session.py` (currently commented out)
- [ ] Stub test processed interfaces

### Behavior (from `*_data.mat` — 100 Hz)

- [ ] Treadmill velocity (m/s) → `TimeSeries` or `SpatialSeries` in `processing/behavior`
- [ ] Treadmill acceleration (m/s²) → `TimeSeries` in `processing/behavior`

### Optogenetics

#### Stimulation events (from `*_data.mat` — 100 Hz binary TTL)

- [ ] Binary opto TTL column → `TimeIntervals` (onset/offset) in `processing/optogenetics` or `stimulus`
- [ ] Decide: `TimeIntervals` (NWB epochs) vs `TimeSeries` (raw binary)

#### Optogenetic device metadata (ChRmine, 635 nm, SNc)

- [ ] Add ChRmine virus (`pAAV-Ef1a-DIO-ChRmine-mScarlet-WPRE`, AAV5, Addgene #130998, 2.20×10¹³ vg/mL) to `fiber_photometry.yaml` or a separate `optogenetics.yaml`
- [ ] Add `OptogeneticStimulusSite` + `OptogeneticSeries` metadata for SNc fiber (Doric MFC_400/430-0.66_4.0mm)

### Session Metadata

- [ ] `stim_sequence` ('a' vs 'b', MATLAB categorical) → `NWBFile.lab_meta_data` or `LabMetaData` extension — **needs lab clarification on meaning**
- [ ] `initiation` channel (Calb only) — store or skip? **Needs lab clarification**

### Post-Conversion

- [ ] Run NWBInspector on a full (non-stub) NWB file
- [ ] Fix any NWBInspector warnings
- [ ] Setup Dandiset (embargoed until publication — DOI pending)
- [ ] Upload all 27 NWB files to DANDI
- [ ] Example notebook — local read + key figure reproduction

---

## Open Questions (lab confirmation needed)

| # | Question | Affects |
|---|----------|---------|
| 1 | Per-animal sex records | `Subject.sex` (currently `U` placeholder) |
| 2 | `stim_sequence` 'a' vs 'b' meaning | Session metadata field |
| 3 | `initiation` channel meaning (Calb only) | Whether to store, and how |
| 4 | Calb group DV fiber coordinate | `FiberInsertion.depth_in_mm` (currently estimated from ferrule length 3 mm) |
| 5 | Calb group GRAB-DA3m injection DV | `FiberPhotometryVirusInjection.dv_in_mm` (currently `2.9` estimate) |
| 6 | Publication DOI | `NWBFile.related_publications` |
| 7 | Experimenter name(s) who collected photometry data | `NWBFile.experimenter` |
| 8 | Hamamatsu H10770PA-40 gain value | `PhotodetectorModel.gain` (wavelength range 300–740 nm already set) |
