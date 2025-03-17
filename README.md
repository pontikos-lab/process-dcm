# Process DCM

[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=plastic)](https://github.com/pontikos-lab/process-dcm/graphs/commit-activity)
[![GitHub](https://img.shields.io/github/license/pontikos-lab/process-dcm?style=plastic)](https://github.com/pontikos-lab/process-dcm)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/pontikos-lab/process-dcm?display_name=tag&logo=github&style=plastic)](https://github.com/pontikos-lab/process-dcm)
[![GitHub Release](https://img.shields.io/github/release-date/pontikos-lab/process-dcm?style=plastic&logo=github)](https://github.com/pontikos-lab/process-dcm)
[![PyPI](https://img.shields.io/pypi/v/process-dcm?style=plastic&logo=pypi)](https://pypi.org/project/process-dcm/)
[![Poetry](https://img.shields.io/endpoint?style=plastic&url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?style=plastic&url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=plastic)](https://github.com/pre-commit/pre-commit)

## About The Project

Python library and app to extract images from DCM files with metadata in a JSON-based standard format

## Installation and Usage

```bash
pip install process-dcm
```

```bash
 Usage: process-dcm [OPTIONS] INPUT_DIR

 Process DICOM files in subfolders, extract images and metadata.
 Version: 0.6.1

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    input_dir      PATH  Input directory containing subfolders with DICOM files. [default: None] [required] │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --image_format        -f      TEXT     Image format for extracted images (png, jpg, webp). [default: png]    │
│ --output_dir          -o      PATH     Output directory for extracted images and metadata.                   │
│                                        [default: exported_data]                                              │
│ --group               -g               Re-group DICOM files in a given folder by AcquisitionDateTime.        │
│ --tol                 -t      FLOAT    Tolerance in seconds for grouping DICOM files by AcquisitionDateTime. │
│                                        Only used when --group is set.                                        │
│                                        [default: None]                                                       │
│ --n_jobs              -j      INTEGER  Number of parallel jobs. [default: 1]                                 │
│ --mapping             -m      TEXT     Path to CSV containing patient_id to study_id mapping. If not         │
│                                        provided and patient_id is anonymised, a 'study_2_patient.csv' file   │
│                                        will be generated.                                                    │
│ --keep                -k      TEXT     Keep the specified fields (p: patient_key, n: names, d:               │
│                                        date_of_birth, D: year-only DOB, g: gender)                           │
│ --overwrite           -w               Overwrite existing images if found.                                   │
│ --reset               -r               Reset the output directory if it exists.                              │
│ --quiet               -q               Silence verbosity.                                                    │
│ --version             -V               Prints app version.                                                   │
│ --install-completion                   Install completion for the current shell.                             │
│ --show-completion                      Show completion for the current shell, to copy it or customize the    │
│                                        installation.                                                         │
│ --help                -h               Show this message and exit.                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────
```

## For Developers

To run this project locally, you will need to install the prerequisites and follow the installation section.

### Prerequisites

This Project depends on the [`poetry`](https://python-poetry.org/).

1. Install poetry, via `homebrew` or [`pipx`](https://github.com/pypa/pipx):

   ```bash
   brew install poetry
   ```

   or

   ```bash
   pipx install poetry
   ```

2. Don't forget to use the python environment you set before and, if using `VScode`, apply it there.

3. It's optional, but we strongly recommend [`commitizen`](https://github.com/commitizen-tools/commitizen), which follows [Conventional Commits](https://www.conventionalcommits.org/)

### Installation

1. Clone the repo

   ```sh
   git clone https://github.com/pontikos-lab/process-dcm
   cd process-dcm
   ```

## Bumping Version

We use [`commitizen`](https://github.com/commitizen-tools/commitizen), which follows [Conventional Commits](https://www.conventionalcommits.org/). The instructions below are only for exceptional cases.

1. Using [poetry-bumpversion](https://github.com/monim67/poetry-bumpversion). Bump the version number by running `poetry version [part] [--dry-run]` where `[part]` is `major`, `minor`, or `patch`, depending on which part of the version number you want to bump.

   Use `--dry-run` option to check it in advance.

1. Push the tagged commit created above and the tag itself, i.e.:

   ```bash
   ver_tag=$(poetry version | cut -d ' ' -f2)
   git tag -a v"$ver_tag" -m "Tagged version $ver_tag"
   git push
   git push --tags
   ```
