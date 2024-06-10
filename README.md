# dombeck-lab-to-nwb
NWB conversion scripts for Dombeck lab data to the [Neurodata Without Borders](https://nwb-overview.readthedocs.io/) data format.


## Installation
The package can be installed directly from GitHub, which has the advantage that the source code can be modified if you need to amend some of the code we originally provided to adapt to future experimental differences.
To install the conversion from GitHub you will need to use `git` ([installation instructions](https://github.com/git-guides/install-git)). We also recommend the installation of `conda` ([installation instructions](https://docs.conda.io/en/latest/miniconda.html)) as it contains
all the required machinery in a single and simple install.

From a terminal (note that conda should install one in your system) you can do the following:

```
git clone https://github.com/catalystneuro/dombeck-lab-to-nwb
cd dombeck-lab-to-nwb
conda env create --file make_env.yml
conda activate dombeck_lab_to_nwb_env
```

This creates a [conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/environments.html) which isolates the conversion code from your system libraries.
We recommend that you run all your conversion related tasks and analysis from the created environment in order to minimize issues related to package dependencies.

Alternatively, if you want to avoid conda altogether (for example if you use another virtual environment tool)
you can install the repository with the following commands using only pip:

```
git clone https://github.com/catalystneuro/dombeck-lab-to-nwb
cd dombeck-lab-to-nwb
pip install -e .
```

Note:
both of the methods above install the repository in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs).

## Repository structure
Each conversion is organized in a directory of its own in the `src` directory:

    dombeck-lab-to-nwb/
    ├── LICENSE
    ├── make_env.yml
    ├── pyproject.toml
    ├── README.md
    ├── requirements.txt
    ├── setup.py
    └── src
        ├── dombeck_lab_to_nwb
        │   └── azcorra2023
        │       ├── extractors
        │       │   ├── __init__.py
        │       │   └──  picoscope_recordingextractor.py
        │       ├── interfaces
        │       │   ├── __init__.py
        │       │   ├── azcorra2023_fiberphotometryinterface.py
        │       │   ├── azcorra2023_processedfiberphotometryinterface.py
        │       │   ├── picoscope_eventinterface.py
        │       │   └── picoscope_timeseriesinterface.py
        │       ├── matlab_utils
        │       │   ├── convert_data6.m
        │       │   ├── resave_mat_files.m
        │       ├── metadata
        │       │   ├── azcorra2023_fiber_photometry_metadata.yaml
        │       │   ├── azcorra2023_nwbfile_metadata.yaml
        │       │   ├── azcorra2023_subjects_metadata.yaml
        │       ├── photometry_utils
        │       │   ├── __init__.py
        │       │   ├── add_fiber_photometry.py
        │       │   ├── process_extra_metadata.py
        │       ├──tutorials
        │       │   └── azcorra2023_demo.ipynb
        │       ├── azcorra2023_convert_all_sessions.py
        │       ├── azcorra2023_convert_session.py
        │       ├── azcorra2023_notes.md
        │       ├── azcorra2023_requirements.txt
        │       ├── azcorra2023nwbconverter.py
        │       └── __init__.py
        └── __init__.py

For the conversion `azcorra2023` you can find a directory located in `src/dombeck-lab-to-nwb/azcorra2023`.
Inside the conversion directory you can find the following files:

* `azcorra2023_convert_all_sessions.py`: this script defines the function to convert all sessions of the conversion.
* `azcorra2023_convert_sesion.py`: this script defines the function to convert one full session of the conversion.
* `azcorra2023_requirements.txt`: the dependencies specific to this conversion.
* `azcorra2023_notes.md`: the notes and comments concerning this specific conversion.
* `azcorra2023nwbconverter.py`: the place where the `NWBConverter` class is defined.
* `extractors/`: a directory containing the extractor for the PicoScope format.
* `interfaces/`: a directory containing the interfaces for the raw and processed fiber photometry data.
* `metadata/`: a directory containing the editable metadata for the conversion.
* `tutorials/`: a directory containing a jupyter notebook that demonstrates how to access each data stream in an NWB file.
* `matlab_utils/`: a directory containing the matlab scripts used to resave the .mat files to be readable in Python.
* `photometry_utils/`: a directory containing the utility functions to add the fiber photometry data to the NWB file.

### Notes on the conversion

The conversion [notes](https://github.com/catalystneuro/dombeck-lab-to-nwb/blob/main/src/dombeck_lab_to_nwb/azcorra2023/azcorra2023_notes.md)
contain information about the expected folder structure and the conversion process.

### Running a specific conversion
To run a specific conversion, you might need to install first some conversion specific dependencies that are located in each conversion directory:

```bash
conda activate dombeck_lab_to_nwb_env
pip install -r src/dombeck_lab_to_nwb/azcorra2023/azcorra2023_requirements.txt
```

You can run a specific conversion with the following command:
```bash
python src/dombeck_lab_to_nwb/azcorra2023/azcorra2023_convert_session.py
```

## NWB tutorials

The `tutorials` directory contains jupyter notebooks that demonstrate how to access the data in the NWB files.
You might need to install `jupyter` before running the notebooks:

```bash
pip install jupyter
cd src/dombeck_lab_to_nwb/azcorra2023/tutorials
jupyter lab
```
