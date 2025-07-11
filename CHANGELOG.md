## v0.10.0 (2025-07-09)

### Feat

- :sparkles: add `source_file` to metadata, increase parser_version to 1.5.3 DCM  (#4)

### Fix

- update expected MD5 hash in `test_main_dummy` for consistency with latest changes

## v0.9.0 (2025-04-09)

### Feat

- update input parameter to accept either a file or a folder

## v0.8.0 (2025-04-08)

### Feat

- update MD5 assertion in test_optomap for additional checksum validation
- update ipython dependency to version 8.35.0
- add example DICOM file for testing purposes
- enhance DICOM modality detection for OPTOS Optomap

## v0.7.0 (2025-03-17)

### Feat

- update test assertions to include additional MD5 checks for consistency
- update README and main function to clarify '--tol' option usage and set default tolerance
- add reset option to main function and enhance DCM file handling
- enable parallel processing and enhance test coverage with new DICOM examples
- huge refactoring and add DICOMDIR support

### Refactor

- update process_dcm function to use Path objects and clean up tests

## v0.6.1 (2025-03-12)

### Refactor

- add type hints to test functions in test_const.py

## v0.6.0 (2025-03-12)

### Feat

- enhance DICOM processing by filtering out empty modalities and improving file type checks

## v0.5.0 (2025-02-04)

### Feat

- add OPTOS_FA modality and corresponding test case

## v0.4.9 (2025-02-04)

### Fix

- update version provider from poetry to pep621 in pyproject.toml
- add thread safety to folder deletion process
- sort DICOM files when loading from input directory
- fix typings

## v0.4.8 (2024-11-28)

### Fix

- :bug: Fix bug about existing folder when using re-group option

## v0.4.7 (2024-11-13)

### Fix

- improve output details for unknown modalities

## v0.4.6 (2024-11-13)

### Fix

- :bug: Avoid overwriting images in some scenarios

## v0.4.5 (2024-11-13)

### Fix

- :bug: Improve the way to handle AcquisitionDateTime

## v0.4.4 (2024-11-12)

### Fix

- :bug: Able to handle OPTOS PSEUDOCOLOUR_ULTRAWIDEFIELD modality

## v0.4.3 (2024-11-12)

### Fix

- :bug: Added tolerance parameter for grouping AcquisitionDateTime

## v0.4.2 (2024-09-30)

## v0.4.1 (2024-09-30)

### Fix

- :bug: Fix output dir bug
- :bug: Fix wrong py_dcm_version in metadata.json

## v0.4.0 (2024-09-16)

### Feat

- :sparkles: Option to re-group DCM results by AcquisitionDateTime

### Fix

- :bug: Fix issue with anonymised folder output

## v0.3.0 (2024-09-11)

### Feat

- :sparkles: Make it compatible with python >=3.10

## v0.2.2 (2024-09-11)

### Fix

- :bug: Fix absolute path for output_dir issue

## v0.2.1 (2024-09-09)

### Fix

- Fix the abort case and test
- Update to pydicom 3.0 and fixed some typos

## v0.2.0 (2024-09-05)

### Feat

- :sparkles: Added anonymiser option by default

## v0.1.1 (2024-09-04)

### Fix

- :bug: Assign the right group id for multi-groups cases in metadata.json

## v0.1.0 (2024-07-31)

### Feat

- :bookmark: Added GH action

### Fix

- :bug: Attempt to fix GH action

## v0.0.2 (2024-07-31)

### Fix

- Fixed pyproject.toml for cz

## v0.0.1 (2024-07-31)
