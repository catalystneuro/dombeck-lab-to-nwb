# src/dombeck_lab_to_nwb/chen2026
NWB conversion scripts for the LRRK2 Dataset from the Dombeck lab (2026-07).

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
├── convert_session.py               # main entry point — edit paths at the bottom and run
├── chen2026nwbconverter.py          # NWBConverter subclass wiring all interfaces together
├── interfaces/
│   ├── raw_fiber_photometry_interface.py       # reads raw .abf; demultiplexes 470/405 nm streams
└── metadata/
    ├── general_metadata.yaml        # NWBFile and Subject fields shared across all sessions
    └── fiber_photometry.yaml        # hardware metadata: devices, fiber implants, virus injections,
                                     # indicators, FiberPhotometryTable rows, and response series entries
```

### Key files

**`convert_session.py`** — the script you run to produce an NWB file. Edit the file paths and
animal parameters in the `if __name__ == "__main__"` block at the bottom.

**`metadata/general_metadata.yaml`** — contains static NWBFile fields shared across all sessions
(`experiment_description`, `keywords`, `institution`, `lab`, `experimenter`) and Subject fields
(`species`, `strain`, `age`, `sex`). Per-group session descriptions and subject descriptions are
also stored here as templates; the `{genotype_label}` placeholder is filled in at runtime.

**`metadata/fiber_photometry.yaml`** — contains all fiber photometry hardware metadata structured
as `BaseFiberPhotometryInterface` expects: device models and instances (`DeviceModels`, `Devices`),
virus and injection records (`FiberPhotometryViruses`, `FiberPhotometryVirusInjections`),
fluorescence indicators (`FiberPhotometryIndicators`), the `FiberPhotometryTable` rows (one per
fiber × excitation wavelength), and one response series entry per interface instance. Both groups
are covered in a single file: Anxa-LRRK2 (DLS rows) and Calb-LRRK2 (DMS rows).

**`interfaces/raw_fiber_photometry_interface.py`** — subclasses `BaseFiberPhotometryInterface`.
Reads the multiplexed 520 nm PMT signal from an Axon `.abf` file and demultiplexes it into
470 nm (functional) and 405 nm (isosbestic) streams using the `fxn_gen` LED-switching channel.
Instantiated twice per session: once per wavelength.

### Running the conversion

You can run the conversion of a single session with the following command:

```bash
python src/dombeck_lab_to_nwb/chen2026/convert_session.py
```

### Running the batch conversion

You can run the conversion of all 27 sessions with the following command:

```bash
python src/dombeck_lab_to_nwb/chen2026/convert_all_sessions.py
```
