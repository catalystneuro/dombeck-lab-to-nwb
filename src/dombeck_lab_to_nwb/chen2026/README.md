# src/dombeck_lab_to_nwb/chen2026

NWB conversion scripts for the LRRK2 fiber photometry dataset from the Dombeck Lab.
**Preprint:** [https://doi.org/10.1101/2025.08.28.672006](https://doi.org/10.1101/2025.08.28.672006)
**DANDI archive:** [DANDI:001933](https://dandiarchive.org/dandiset/001933) (embargoed)

## Installation

The package can be installed directly from GitHub, which has the advantage that the source code can be modified if you need to amend some of the code we originally provided to adapt to future experimental differences.
To install the conversion from GitHub you will need to use `git` ([installation instructions](https://github.com/git-guides/install-git)). We also recommend the installation of `conda` ([installation instructions](https://docs.conda.io/en/latest/miniconda.html)) as it contains
all the required machinery in a single and simple install.

From a terminal (note that conda should install one in your system) you can do the following:

```
git clone https://github.com/catalystneuro/dombeck-lab-to-nwb
cd dombeck-lab-to-nwb
conda env create --file src/dombeck_lab_to_nwb/chen2026/environment.yaml
conda activate chen2026
```

This creates a [conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/environments.html) which isolates the conversion code from your system libraries.
Then, you can install the repository in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs):

```
pip install -e . --no-deps
```

The `--no-deps` flag skips the root `requirements.txt` so that the dependencies already installed
by the conda environment (in particular `neuroconv` from the GitHub main branch) are not
overwritten by an older PyPI release.

## Folder structure

```
chen2026/
├── README.md                        # this file
├── environment.yaml                 # conda environment specification (Python 3.13 + all dependencies)
├── convert_session.py               # convert a single session — edit paths at the bottom and run
├── convert_all_sessions.py          # batch conversion for all 27 sessions (parallel, 4 workers)
├── nwbconverter.py                  # NWBConverter subclass wiring all interfaces together
├── conversion_notes.md              # detailed technical notes on data format and implementation
├── interfaces/
│   ├── __init__.py
│   ├── raw_fiber_photometry_interface.py       # reads raw .abf; demultiplexes 470/405 nm streams
│   ├── processed_fiber_photometry_interface.py # reads *_data.mat; writes corrected FP + ΔF/F
│   ├── behavior_interface.py                   # reads *_data.mat; writes treadmill velocity + acceleration
│   ├── optogenetics_interface.py               # reads *_data.mat TTL; writes OptogeneticEpochsTable
│   └── raw_treadmill_interface.py              # reads raw .abf treadmill channel; writes RawTreadmillVoltage
├── metadata/
│   ├── general_metadata.yaml        # NWBFile and Subject fields shared across all sessions
│   ├── fiber_photometry.yaml        # hardware metadata: devices, fiber implants, virus injections,
│   │                                # indicators, FiberPhotometryTable rows, and response series entries
│   └── optogenetics.yaml            # optogenetics metadata: LED, fiber, ChRmine virus, injection sites
└── tutorials/
    └── chen2026_demo.ipynb          # end-to-end tutorial reading a local NWB file
```

## NWB file contents

Each converted `.nwb` file contains one session (one animal, one recording). Both groups
(Anxa-LRRK2 and Calb-LRRK2) share the same structure:

| Location | Object | Source | Notes |
|----------|--------|--------|-------|
| `acquisition/` | `FiberPhotometryResponseSeriesRawSignal` | ABF `520sig` (470 nm demux) | 2000 Hz, irregular timestamps |
| `acquisition/` | `FiberPhotometryResponseSeriesIsosbesticControl` | ABF `520sig` (405 nm demux) | 2000 Hz, irregular timestamps |
| `acquisition/` | `CommandedVoltageSeries` | ABF `fxn_gen` (LED switching waveform) | 2000 Hz, rate-based; linked to FiberPhotometryTable |
| `acquisition/` | `RawTreadmillVoltage` | ABF `treadmill` channel | 2000 Hz, analog ~1.2–2.0 V |
| `processing/ophys/` | `FiberPhotometryResponseSeriesCorrectedSignal` | `_data.mat` `corrected470` | 100 Hz, camera-trigger timestamps |
| `processing/ophys/` | `FiberPhotometryResponseSeriesCorrectedIsosbesticControl` | `_data.mat` `corrected405` | 100 Hz, camera-trigger timestamps |
| `processing/ophys/` | `FiberPhotometryResponseSeriesDfOverF` | `_data.mat` `dff470` | 100 Hz, % ΔF/F |
| `processing/ophys/` | `FiberPhotometryResponseSeriesDfOverFIsosbesticControl` | `_data.mat` `dff405` | 100 Hz, % ΔF/F |
| `processing/behavior/` | `BehavioralTimeSeries` | `_data.mat` `velocity`, `acceleration` | 100 Hz, m/s and m/s² |
| `intervals/` | `OptogeneticEpochsTable` | `_data.mat` `TTL` (merged) | 64 train epochs; per-epoch pulse params and power |

### Key files

**`convert_session.py`** — the script you run to produce a single NWB file. Edit the file paths and
animal parameters in the `if __name__ == "__main__"` block at the bottom, then run:

```bash
python src/dombeck_lab_to_nwb/chen2026/convert_session.py
```

**`convert_all_sessions.py`** — batch conversion for all 27 sessions using a `ProcessPoolExecutor`
(4 parallel workers by default). Errors are written to per-session log files. Run with:

```bash
python src/dombeck_lab_to_nwb/chen2026/convert_all_sessions.py
```

**`metadata/general_metadata.yaml`** — contains static NWBFile fields shared across all sessions
(`experiment_description`, `keywords`, `institution`, `lab`, `experimenter`) and Subject fields
(`species`, `strain`). Per-group session descriptions and subject descriptions are also stored here
as templates; the `{genotype_label}` placeholder is filled in at runtime.

**`metadata/fiber_photometry.yaml`** — contains all fiber photometry hardware metadata structured
as `BaseFiberPhotometryInterface` expects: device models and instances (`DeviceModels`, `Devices`),
virus and injection records (`FiberPhotometryViruses`, `FiberPhotometryVirusInjections`),
fluorescence indicators (`FiberPhotometryIndicators`), the `FiberPhotometryTable` rows (one per
fiber × excitation wavelength), and one response series entry per interface instance. Both groups
are covered in a single file: Anxa-LRRK2 (DLS rows) and Calb-LRRK2 (DMS rows).

**`metadata/optogenetics.yaml`** — contains optogenetics hardware metadata used by
`Chen2026OptogeneticsInterface`: the 635 nm LED (`ExcitationSourceModel`, `ExcitationSource`),
opto fiber at SNc (`OpticalFiberModel`, `OpticalFibers`), ChRmine viral vector and injection
(`ViralVector`, `VirusInjections`), ChRmine effector (`Effectors`), and `OptogeneticSitesTable`.

**`interfaces/raw_fiber_photometry_interface.py`** — subclasses `BaseFiberPhotometryInterface`.
Reads the multiplexed 520 nm PMT signal from an Axon `.abf` file and demultiplexes it into
470 nm (functional) and 405 nm (isosbestic) streams using the `fxn_gen` LED-switching channel.
Instantiated twice per session (once per wavelength). A module-level cache (`_DEMUX_CACHE`)
avoids reading the ABF file twice.

**`interfaces/processed_fiber_photometry_interface.py`** — subclasses `BaseFiberPhotometryInterface`.
Reads baseline-corrected and ΔF/F traces from the per-animal `*_data.mat` file and routes them to
`nwb.processing["ophys"]` (camera-trigger-aligned, 100 Hz). Instantiated four times per session
(corrected470, corrected405, dff470, dff405).

**`interfaces/behavior_interface.py`** — reads `velocity` and `acceleration` columns from
`*_data.mat` and writes them as a `BehavioralTimeSeries` in `nwb.processing["behavior"]` (100 Hz).

**`interfaces/optogenetics_interface.py`** — reads the binary `TTL` column from `*_data.mat`,
merges TTL fragments within 1 s into full trains, and writes an `OptogeneticEpochsTable` with
per-epoch `pulse_length_in_ms`, `period_in_ms`, `number_pulses_per_pulse_train`, and `power_in_mW`.
Full ndx-optogenetics device provenance (LED, fiber, ChRmine virus, injection sites) is also added.

**`interfaces/raw_treadmill_interface.py`** — reads the `treadmill` channel from the `.abf` file
and writes it as `RawTreadmillVoltage` in `nwb.acquisition` (2000 Hz, ~1.2–2.0 V). Shares the
`_DEMUX_CACHE` with `raw_fiber_photometry_interface.py` to avoid duplicate ABF reads.
