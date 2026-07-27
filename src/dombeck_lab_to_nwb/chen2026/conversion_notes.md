# Conversion Notes — Dombeck Lab NWB Conversions

## LRRK2 Dataset (2026-07)

**Manuscript:** "Leucine-rich repeat kinase 2 impairs the release sites of Parkinson's disease vulnerable dopamine axons", Chen, He et al. (in preparation)
**Analysis code:** https://github.com/DombeckLab/lrrk2_photometry_analysis (Zenodo: 10.5281/zenodo.20244434)
**Status:** All interfaces implemented; 27/27 sessions converted successfully.
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

**Column order verified from `LRRK2_binning_and_processing.m`** — confirmed the 10-column layout above matches the MATLAB script output exactly. Processing steps also verified:
- `corrected470`/`corrected405`: output of `baselineCorrect()` — sliding 8th-percentile baseline (window=2001 samples, subtraction factor 0.85)
- `dff470`/`dff405`: output of `df_f()` — `(signal − F0) / F0 × 100`, then smoothed with `movmean(20)` (20-sample moving mean at 100 Hz = 200 ms window)
- Binning: camera-trigger-aligned, `fps=100`, velocity calibration factor `calib = 0.6766 × 2 = 1.3532`

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
| Photometry fiber (Anxa/DLS) | Doric MFC_200/250-0.66_2.0mm_ZF1.25(G)_FLT, 200 µm, 0.66 NA, 2 mm depth |
| Photometry fiber (Calb/DMS) | Doric MFC_00/250-0.66_3.0mm_ZF1.25(G)_FLT, 200 µm, 0.66 NA, 3 mm depth |
| Opto fiber (SNc, both groups) | Doric MFC_400/430-0.66_4.0mm_TS3.0_C60, 400 µm, 0.66 NA, 4 mm depth |
| Opto LED | Doric LEDFRJ_635 (635 nm red LED); controlled by Doric Studio software |
| Opto control | Stimulation trains triggered by custom LabVIEW script |

Fiber implant DV depth = ferrule length (Doric convention), referenced from dura surface.

**Optogenetics surgery (Anxa1+ group):**
- SNc craniotomy: −3.20 mm caudal, +1.60 mm lateral from bregma (right hemisphere)
- ChRmine injection: 4 depths (−3.8, −4.1, −4.4, −4.7 mm ventral from dura), 0.1 µL/depth = 0.4 µL total
- Opto fiber implanted via same craniotomy just above SNc (tip at ~4.0 mm from dura)
- Striatum GRAB-DA3m injection (DLS): +0.5 mm caudal, +1.8 mm lateral; −1.9 mm from dura

**Optogenetics surgery (Calb1+ group):**
- Same SNc craniotomy as Anxa1+ (−3.20 mm caudal, +1.60 mm lateral)
- ChRmine injection: 1 depth only (−4.3 mm from dura) to prevent VTA/thalamus spillover
- Striatum GRAB-DA3m injection (DMS): +0.5 mm caudal, +1.4 mm lateral; −1.9 mm from dura

**Confirmed stimulation parameters (measured from raw ABF, channel `opto_TTL`, 2000 Hz):**

Each session contains **64 trains total** (8 power levels × 8 repetitions). The two halves of the session use different pulse protocols:

| Epoch range | Amplitude | Pulse ON | Pulse OFF | Period | Pulses/train | Train duration |
|-------------|-----------|----------|-----------|--------|--------------|----------------|
| 0 – 31 (first half) | ~1.2 V | 9 ms | 1 ms | 10 ms (100 Hz) | 32 | ~320 ms |
| 32 – 63 (second half) | ~0.05 V | 8 ms | 8 ms | 16 ms (62.5 Hz) | 32 | ~505 ms |

The manuscript states "8 ms on / 8 ms off" (16 ms period, ~31 pulses), which describes only the second half. Both halves have exactly 32 pulses per train. The first-half trains fire at 100 Hz (one pulse per camera frame). Per-epoch values are stored in `OptogeneticEpochsTable` columns — see `convert_session.py`.

- Powers: 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0 mW at cannula tip (pseudorandom order, 8 reps each)
- Intertrain interval: ≥20 s; each recording session = 20 minutes
- TTL in `_data.mat` is HIGH for the full train duration (not per-pulse)

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

### Time Alignment

#### Recording clocks and reference frame

All data in a single session is acquired on a single clock: the **Axon Digidata 1550B** DAQ, sampling all six channels (or five, for the Anxa open-loop setup) at 2000 Hz. Time zero (`t = 0`) for the NWB file is defined by the ABF recording start — the moment the Digidata started acquiring. All raw data timestamps are in seconds relative to this start.

The **session start time** (`NWBFile.session_start_time`) is derived from the ABF file header (Axon `uFileStartDateTime` field, UTC). This is the absolute wall-clock time at the moment the Digidata started. All relative timestamps in the NWB file are seconds elapsed from that moment.

#### Raw fiber photometry (470 nm signal + 405 nm isosbestic)

- **Source:** ABF file, `520sig` channel (continuous analog, 2000 Hz).
- **Demultiplexing** (`_load_and_demux` in `raw_fiber_photometry_interface.py`):
  1. Read all 2000 Hz samples from `520sig` and `fxn_gen`.
  2. Build a 2000-sample-per-second time vector: `timestamps = np.arange(n) / abf.dataRate` — these are seconds since DAQ start, in the ABF clock.
  3. Classify each sample: `wave470 = fxn_gen > 1 V`, `wave405 = ~wave470`.
  4. Mark transition samples as borders, mirroring the MATLAB logic:
     - `border405 = [0, |diff(wave405)|]` (leading-edge flag)
     - `border470 = [|diff(wave470)|, 1]` (trailing-edge flag; last sample always flagged)
     - `border = (border405 + border470) > 0`
  5. Select retained samples and their timestamps:
     - 470 nm: `sig520[wave470 & ~border]`, `timestamps[wave470 & ~border]`
     - 405 nm: `sig520[wave405 & ~border]`, `timestamps[wave405 & ~border]`
- **Timestamps stored in NWB:** the subset of ABF timestamps corresponding to retained samples — explicit, irregular, in the ABF clock. The 470 nm and 405 nm series have slightly different sample counts (e.g. 1,055,733 vs 1,055,138 in the example session) because the LED duty cycle is not exactly 50/50 and each channel discards its own transition samples.
- **Time range:** `t ≈ 0 s` to `t ≈ 1319 s` (example session; spans the full ABF recording).
- **NWB location:** `acquisition/FiberPhotometryResponseSeriesRawSignal` (470 nm) and `acquisition/FiberPhotometryResponseSeriesIsosbesticControl` (405 nm).

#### Session start time

`NWBFile.session_start_time` is the wall-clock datetime read directly from the ABF header (`abf.abfDateTime`). The ABF stores it without timezone info; the lab is at Northwestern University (Chicago), so `America/Chicago` is applied. This is also returned by `get_metadata()` so it flows automatically into the NWB file without any manual override.

#### Processed fiber photometry and all `_data.mat` signals

The MATLAB processing script (`LRRK2_binning_and_processing.m`) reads the raw ABF and re-bins all signals into **camera-trigger-aligned bins at 100 Hz**. It detects rising edges in the `camera` ABF channel (square wave 0 / 3.3 V, 100 Hz) and uses each trigger as a bin boundary. The binned outputs are stored in `*_data.mat`.

**Critical offset:** the camera does not start triggering immediately at recording start. In the example session (animal 4007), the first camera trigger fires at **t ≈ 21.06 s** into the ABF recording. Consequently all `_data.mat` columns (corrected signal, ΔF/F, TTL, velocity, acceleration) begin at ~21 s, not at 0 s. Storing them with `starting_time = 0` would shift all processed data 21 s earlier than reality and misalign them against the raw FP.

**Alignment solution:** `_read_mat()` detects the camera trigger rising edges from the `camera` column (threshold 1.0 V, 2000 Hz), computes `trigger_times = rising_edge_sample_index / 2000.0`, and stores them as `"camera_trigger_times"` in the cache. All 100 Hz interfaces use these times as explicit timestamps:

| Interface | Timestamps source |
|-----------|------------------|
| Processed FP (`corrected470`, `corrected405`, `dff470`, `dff405`) | `camera_trigger_times` |
| Behavior (`velocity`, `acceleration`) | `camera_trigger_times` |
| Optogenetic epochs (TTL) | `camera_trigger_times[start_index]` and `camera_trigger_times[stop_index]` |

The trigger spacing is nominally 10 ms (100 Hz) with ±0.5 ms quantization noise from the 2 kHz sampling grid. This means 129,307 triggers align to 129,307 samples in each processed column.

**Verified alignment (example session):**

| Signal | Time range in NWB | Notes |
|--------|-------------------|-------|
| Raw FP (470 nm) | 0.000 – 1319.295 s | Full ABF recording |
| Raw FP (405 nm) | 0.000 – 1319.295 s | Same ABF clock |
| Processed FP / ΔF/F | 21.061 – 1313.823 s | Camera-trigger-aligned |
| Behavior (velocity, acceleration) | 21.061 – 1313.823 s | Same camera triggers |
| Optogenetic epochs | 51.764 – ... s | TTL first epoch; within processed range ✓ |

#### Optogenetic stimulation epochs

- **Source:** `TTL` column in `_data.mat` (uint8, 0 or 1, 100 Hz). The MATLAB script binarizes via `any(opto > 0.05 V)` per 10 ms camera bin.
- **TTL fragmentation problem:** first-half trains (~1.2 V, 10 ms period) appear as clean single blobs in the mat TTL. Second-half trains (~0.05 V, barely above the 0.05 V threshold) fragment into 2–10 blobs per train because the low-amplitude ABF pulses alias unevenly across 10 ms camera bins. Naively detected blobs = 122 for these sessions; correct train count = 64.
- **Merge fix:** `_extract_epochs()` merges blobs whose gap is < 1 s into a single epoch. Inter-train intervals are ≥20 s, so the 1 s threshold is unambiguous. All 27 sessions yield exactly 64 epochs after merging.
- **Epoch times:** `start_time = camera_trigger_times[first_high_sample]`, `stop_time = camera_trigger_times[first_low_sample_after_epoch]`. These are in the ABF clock, aligned with all other signals.
- **Note:** stimulation begins at ~30–50 s into the session (well after the ~21 s camera-start offset), so all 64 epochs fall within the processed FP time range.

#### Summary: what defines `t = 0` for this dataset

`t = 0` is the **Axon Digidata recording start** (ADC enabled), captured as an absolute UTC datetime in the ABF header and stored in `NWBFile.session_start_time`. All signals are in seconds elapsed from that moment. The raw FP starts at `t ≈ 0 s`; the processed / behavior / opto signals start at `t ≈ 21 s` (first camera trigger). There is no separate synchronization signal between the ABF and any other acquisition device — everything is on one DAQ.

---

### NWB File Content Summary

Each converted `.nwb` file contains:

| Location | Object | Source | Notes |
|----------|--------|--------|-------|
| `acquisition/` | `FiberPhotometryResponseSeriesRawSignal` | ABF `520sig` (470 nm demux) | 2000 Hz, explicit timestamps |
| `acquisition/` | `FiberPhotometryResponseSeriesIsosbesticControl` | ABF `520sig` (405 nm demux) | 2000 Hz, explicit timestamps |
| `acquisition/` | `CommandedVoltageSeries` | ABF `fxn_gen` (LED switching waveform) | 2000 Hz, rate-based timestamps; linked to FiberPhotometryTable |
| `acquisition/` | `RawTreadmillVoltage` | ABF `treadmill` channel | 2000 Hz, analog ~1.2–2.0 V; data provenance for velocity/acceleration |
| `processing/ophys/` | `FiberPhotometryResponseSeriesCorrectedSignal` | `_data.mat` `corrected470` | 100 Hz, camera-trigger timestamps |
| `processing/ophys/` | `FiberPhotometryResponseSeriesCorrectedIsosbestic` | `_data.mat` `corrected405` | 100 Hz, camera-trigger timestamps |
| `processing/ophys/` | `FiberPhotometryResponseSeriesDfOverF` | `_data.mat` `dff470` | 100 Hz, camera-trigger timestamps |
| `processing/ophys/` | `FiberPhotometryResponseSeriesDfOverFIsosbestic` | `_data.mat` `dff405` | 100 Hz, camera-trigger timestamps |
| `processing/behavior/` | `BehavioralTimeSeries` → `treadmill_velocity`, `treadmill_acceleration` | `_data.mat` `velocity`, `acceleration` | 100 Hz, camera-trigger timestamps |
| `intervals/` | `OptogeneticEpochsTable` | `_data.mat` `TTL` (merged) | 64 train epochs; per-epoch pulse params and power |

The raw ABF is the sole source for `acquisition/` and `CommandedVoltageSeries`. Individual pulse times are not stored as a separate EventsTable: the `OptogeneticEpochsTable` columns `pulse_length_in_ms`, `period_in_ms`, and `number_pulses_per_pulse_train` fully specify the pulse train structure since the hardware function generator produces perfectly regular pulses. Camera frame times are not stored as a separate EventsTable because they are already the explicit timestamps of every 100 Hz processed series — duplicating ~129k rows would add significant write time without new information.

---

### Implementation Notes

#### Raw Treadmill Interface (`Chen2026RawTreadmillInterface`)

Class in `interfaces/raw_treadmill_interface.py`, registered as `RawTreadmill` in the converter. Always present (no `mat_file` required).

Writes one `TimeSeries` to `nwb.acquisition`:

- **`RawTreadmillVoltage`**: the raw analog voltage from the rotary encoder (ABF `treadmill` channel, 2000 Hz, explicit timestamps). Voltage range ~1.2–2.0 V across the Anxa/Calb cohorts. Unit: V.

Shares the module-level `_DEMUX_CACHE` from `raw_fiber_photometry_interface.py` (keyed by `file_path`), so the ABF is read only once regardless of which interface runs first. The cache stores all channels including `treadmill` alongside the demultiplexed 470/405 nm streams.

**Derived signals cross-reference**: `treadmill_velocity` (m/s) and `treadmill_acceleration` (m/s²) are in `nwb.processing['behavior']['BehavioralTimeSeries']` at 100 Hz. Those are computed by the MATLAB `LRRK2_binning_and_processing.m` script (calibration factor `calib = 1.3532 m/s per V`) and read from `_data.mat` by `Chen2026BehaviorInterface`.

---

#### Processed series routing to `processing/ophys`

`BaseFiberPhotometryInterface` (neuroconv) hardcodes `nwbfile.add_acquisition(response_series)` with no override point for the target container. As a workaround, `Chen2026ProcessedFiberPhotometryInterface` overrides `add_to_nwbfile` to:
1. Call `super().add_to_nwbfile(...)` (adds to acquisition)
2. Delete the series from `nwbfile.acquisition` via `LabelledDict.__delitem__`
3. Create `nwbfile.processing["ophys"]` if absent, then add the series there

A TODO comment in the interface marks this for removal once a neuroconv PR adds a `parent_container: Literal["acquisition", "processing/ophys"] = "acquisition"` parameter to `BaseFiberPhotometryInterface.add_to_nwbfile`. The pattern already exists in `roiextractors.py` (lines 460–464) and uses the `get_module` utility already imported in the fiber photometry module.

---

### Open Questions (needs lab confirmation)

1. **`stim_sequence` 'a' vs 'b'**: resolved — encodes the pseudorandom power order. Per-epoch `power_in_mW` is now populated in `OptogeneticEpochsTable` for all 27 sessions from `LRRK2.xlsx`.
2. **`initiation` channel**: What does this signal represent? Store in NWB?
3. **Per-animal sex records** — manuscript says both sexes used but no individual records confirmed
4. **Publication DOI** — manuscript not yet published; Zenodo: 10.5281/zenodo.20244434
5. **Experimenter names** — confirm which authors collected the photometry data
