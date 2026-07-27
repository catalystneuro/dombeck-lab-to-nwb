# Conversion Notes — Dombeck Lab NWB Conversions

## LRRK2 Dataset (2026-07)

**Manuscript:** "Leucine-rich repeat kinase 2 impairs the release sites of Parkinson's disease vulnerable dopamine axons", Chen, He et al. (in preparation)
**Analysis code:** https://github.com/DombeckLab/lrrk2_photometry_analysis (Zenodo: 10.5281/zenodo.20244434)
**Status:** Data inspection complete, metadata extracted from manuscript, code not yet written.
**Detailed notes:** see `lrrk2_investigation.md`

---

### Experiment Summary

In vivo fiber photometry of striatal dopamine release (GRAB-DA3m sensor) in awake head-fixed mice during optogenetic activation of dopamine neuron subtypes. Two groups:

- **Calb-LRRK2**: Calb1-Cre mice, fiber in dorsal medial striatum (DMS), Calb1+ dopamine neurons
- **Anxa-LRRK2**: Anxa1-iCre mice, fiber in dorsal lateral striatum (DLS), Anxa1+ dopamine neurons

Each group has WT and LRRK2-G2019S knockin animals. Optogenetic stimulation of cell bodies in SNc via ChRmine (635 nm). No behavioral video — `camera` channel is a frame sync TTL only.

---

### Subject Groups

| Group | Cre line | Genotypes | n | Recording site |
|-------|----------|-----------|---|----------------|
| Calb-LRRK2 | Calb1-Cre | WT, GS (LRRK2-G2019S, JAX:030961) | 12 | DMS |
| Anxa-LRRK2 | Anxa1-iCre | WT, GS | 15 | DLS |

- Background: C57BL/6J
- Age at surgery: 6 months; recordings 4 weeks post-surgery
- Sex: both male and female; no per-animal sex records confirmed yet

---

### Data Structure

```
/
├── LRRK2-animal-list-meta.mat       # Animal metadata (ID, Genotype, Group, filename mapping)
├── LRRK2_binning_and_processing.m   # MATLAB processing pipeline (Step 2)
├── LRRK2_save_raw_data.m            # MATLAB processing pipeline (Step 1)
├── Calb-LRRK2/
│   ├── 2025_11_10_0002.abf          # Raw ABF files (one per animal)
│   ├── ...                          # 12 total ABF files
│   ├── 302/
│   │   ├── 302raw.mat               # MATLAB intermediate (Step 1 — skip for NWB)
│   │   └── 302_data.mat             # MATLAB processed (Step 2 — use for NWB)
│   └── ...                          # 12 animals: 302, 306, 671, 673, 688, 740, 741, 848, 852, 935, 966, 1803
└── Anxa-LRRK2/
    ├── 2025_01_24_0002.abf          # 16 total ABF files (1 excluded by metadata)
    ├── ...
    ├── 3742/
    │   ├── 3742raw.mat
    │   └── 3742_data.mat
    └── ...                          # 15 animals: 3742, 3743, 3947, 3948, 4004, 4005, 4007, 4253, 4398, 4401, 4558, 4561, 4651, 4652, 4885
```

**Total:** 27 animals (12 Calb + 15 Anxa), 1 session per animal.

---

### Raw ABF Channel Layout

**6-channel** (Calb-LRRK2, closed-loop setup):
`520sig`, `fxn_gen`, `initiation`, `opto_TTL`, `camera`, `treadmill`

**5-channel** (Anxa-LRRK2, open-loop setup):
`520sig`, `fxn_gen`, `opto_TTL`, `camera`, `treadmill`

| Channel | Description | Signal type | Rate |
|---------|-------------|-------------|------|
| `520sig` | Multiplexed fluorescence — GCaMP/GRAB + isosbestic interleaved | Continuous analog | 2000 Hz |
| `fxn_gen` | LED switching signal (>1V → 470 nm on, <1V → 405 nm on) | Square wave ~0–5V | 2000 Hz |
| `initiation` | Closed-loop initiation trigger (Calb only) | Near-zero in inspected file | 2000 Hz |
| `opto_TTL` | Optogenetic stimulation trigger (threshold >0.05V) | Sparse analog pulse | 2000 Hz |
| `camera` | Camera frame trigger — sync only, no video recorded | Square wave 0/3.3V | 2000 Hz |
| `treadmill` | Treadmill rotary encoder voltage | Continuous analog | 2000 Hz |

`520sig` is demultiplexed using `fxn_gen`: samples where `fxn_gen > 1V` → 470 nm (GRAB signal); `fxn_gen < 1V` → 405 nm (isosbestic).

---

### Processed `_data.mat` Column Layout

MATLAB table, one row per file. Read via h5py (`#subsystem#/MCOS`): column names at `MCOS[9]`, data at `MCOS[4]`.

| Column | dtype | Rate | Description |
|--------|-------|------|-------------|
| `filename` | str | — | Corresponding ABF filename |
| `corrected470` | float64 | 100 Hz | Baseline-corrected 470 nm signal |
| `corrected405` | float64 | 100 Hz | Baseline-corrected 405 nm isosbestic |
| `dff470` | float64 | 100 Hz | Smoothed ΔF/F 470 nm (moving mean 20 samples) |
| `dff405` | float64 | 100 Hz | Smoothed ΔF/F 405 nm |
| `TTL` | uint8 | 100 Hz | Binary opto TTL (0=off, 1=on), already binned |
| `velocity` | float64 | 100 Hz | Treadmill velocity (m/s, calib factor 1.3532) |
| `acceleration` | float64 | 100 Hz | Acceleration (m/s²) |
| `camera` | float64 | 2000 Hz | Raw camera trigger — **not binned**, likely not needed in NWB |
| `stim_sequence` | categorical | — | Opto stim sequence type: 'a' (18 animals) or 'b' (9 animals) — meaning unclear |

Note: `stim_sequence` is a MATLAB categorical — pymatreader cannot parse it. Use h5py `MCOS[8]` (uint8), map 1→'a', 2→'b'.

---

### Key Hardware Metadata (from manuscript)

| Component | Details |
|-----------|---------|
| Indicator | GRAB-DA3m (dopamine sensor, **not** GCaMP), pAAV-hSyn-GRAB-gDA3m, AAV1, Addgene #208698, ≥7×10¹² vg/mL |
| Opsin | ChRmine, pAAV-Ef1a-DIO-ChRmine-mScarlet-WPRE, AAV5, Addgene #130998, 2.20×10¹³ vg/mL |
| 470 nm LED | Thorlabs M70F3 |
| 405 nm LED | Thorlabs M405FP1 |
| LED power | 0.5 mW at fiber tip |
| 470 nm excitation filter | Semrock FF02-472/30-25 |
| 405 nm excitation filter | Semrock FF01-406/15-25 |
| Excitation dichroic | Chroma T425lpxr |
| Emission filter | Semrock FF01-540/50-25 |
| Emission dichroic | Chroma T505lpxr |
| Detector | Hamamatsu H10770PA-40 GaAsP PMT |
| Amplifier | Stanford Research Systems SR570 |
| DAQ | Axon Digidata 1550B, 2 kHz |
| Photometry fiber (Anxa/DLS) | Doric MFC_200/250-0.66_2.0mm, 200 µm, 0.66 NA, 2 mm length/depth |
| Photometry fiber (Calb/DMS) | Doric MFC_00/250-0.66_3.0mm, 200 µm, 0.66 NA, 3 mm length/depth |
| Opto fiber (SNc, both groups) | Doric MFC_400/430-0.66_4.0mm, 400 µm, 0.66 NA, 4 mm length/depth |

Fiber implant DV depth = ferrule length (Doric convention), referenced from dura surface.

---

### Comparison with Existing Pipelines

#### vs `he_embargo_2024`

**Reusable as-is:**
- `AxonBinaryInterface` — same ABF format, 2000 Hz, same channel names
- `AxonBinaryTimeSeriesInterface` — same channel mapping (`520sig` → Fluorescence, `treadmill` → Velocity)
- `AxonBinaryTtlInterface` — same `fxn_gen` demux logic for 470/405 TTLs

**Must adapt:**
- Fiber photometry interface: MCOS indices differ (LRRK2: names at `[9]`, data at `[4]`; he_embargo_2024: `[7]`/`[2]`); single session per file (no `session_id` needed)
- Optogenetics: TTL already binary at 100 Hz in `_data.mat` — no separate opto `.mat` file
- New channels: `initiation` (Calb only), `stim_sequence` (session metadata)

**ndx-fiber-photometry version:** use v0.2.x API (ndx-ophys-devices) — do **not** replicate the v0.1.0 approach used in he_embargo_2024 and azcorra2023.

---

### CommandedVoltageSeries — LED switching square wave

The `fxn_gen` ABF channel records the function generator square wave that drives the two LEDs.
It is stored as a `CommandedVoltageSeries` in `nwb.acquisition` and linked to both rows of the
`FiberPhotometryTable` as the commanded voltage source.

| Voltage level | Meaning | Demultiplexed stream |
|---------------|---------|----------------------|
| High (> 1 V) | 470 nm LED on | `FiberPhotometryResponseSeriesRawSignal` |
| Low (< 1 V) | 405 nm LED on | `FiberPhotometryResponseSeriesIsosbesticControl` |

- **Waveform frequency** (`frequency`): 100 Hz — the LED alternation rate (10 ms per cycle).
- **Sampling rate** (`rate`): 2000 Hz — the ABF ADC rate at which the waveform is digitised.

Transition samples at each LED switch edge are discarded before storing the demultiplexed
fluorescence series, explaining why the raw signal timestamps are irregular.

---

### Open Questions (needs lab confirmation)

1. **`stim_sequence` 'a' vs 'b'**: 18 animals have 'a', 9 have 'b', mixed across groups and genotypes. What does this distinguish?
2. **`initiation` channel**: What does this signal represent? Store in NWB?
3. **Per-animal sex records** — manuscript says both sexes used but no individual records confirmed
4. **Photometry fiber DV coordinate for Calb group** — not stated in manuscript
5. **GRAB-DA3m injection DV for Calb group** — not stated in manuscript
6. **Publication DOI** — manuscript not yet published
7. **Experimenter names** — confirm which authors collected the photometry data
