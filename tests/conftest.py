import datetime
import os
import re
import tempfile
from collections.abc import Generator
from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from typer.testing import CliRunner

from process_dcm import __version__ as version
from process_dcm.const import ImageModality


def pytest_report_header():
    return f">>>\tVersion: {version}\n"


def remove_ansi_codes(text):
    ansi_escape = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def del_file_paths(file_paths: list[str]) -> None:
    """Deletes all files and folders in the list of file paths.

    Args:
        file_paths (List[str]): A list of file paths to delete.

    Returns:
        None
    """
    for path in file_paths:
        if not os.path.exists(path):
            continue
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(path)


def create_directory_structure(base_path, structure):
    for item, content in structure.items():
        path = base_path / item
        if isinstance(content, dict):
            path.mkdir(exist_ok=True)
            create_directory_structure(path, content)
        else:
            path.write_text(content)


@pytest.fixture(scope="module")
def runner():
    return CliRunner()


@pytest.fixture(scope="module")
def temp_output_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(scope="module")
def input_dir():
    return Path("tests/example-dcms").resolve()


@pytest.fixture(scope="module")
def input_dir2():
    return Path("tests/example_dir/010-0001/20180724_L").resolve()


@pytest.fixture
def dicom_opotopol():
    """Fixture to create a mocked DICOM FileDataset for OPTOPOL."""
    # Create a FileMetaDataset instead of a defaultdict
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian  # or other appropriate UID

    # Create the FileDataset object
    dataset = FileDataset(
        "tests/example-dcms/bscans.dcm",
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
        is_implicit_VR=False,
        is_little_endian=True,
    )

    # Mock setting relevant fields to simulate OPTOPOL DICOM
    dataset.Modality = "OPT"
    dataset.Manufacturer = "OPTOPOL Technology S.A."
    dataset.Columns = 512
    dataset.Rows = 512
    dataset.NumberOfFrames = 5
    dataset.AccessionNumber = 0

    # Add the PerFrameFunctionalGroupsSequence with missing fields to simulate "empty photo_locations"
    functional_group = Dataset()
    functional_group.OphthalmicFrameLocationSequence = []

    dataset.PerFrameFunctionalGroupsSequence = [functional_group]

    # Optionally set the current date and time for the dataset
    dt = datetime.datetime.now()
    dataset.ContentDate = dt.strftime("%Y%m%d")
    dataset.ContentTime = dt.strftime("%H%M%S.%f")  # fractional seconds

    return dataset


@pytest.fixture
def dicom_attribute_error():
    """Fixture to create a mocked DICOM FileDataset for AttributeError simulation."""
    # Create a FileMetaDataset instead of a defaultdict
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian  # or appropriate UID

    # Create the FileDataset object
    dataset = FileDataset(
        "tests/example-dcms/bscans.dcm",
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
        is_implicit_VR=False,
        is_little_endian=True,
    )

    # Mock setting relevant fields to simulate a DICOM file
    dataset.Modality = "OPT"
    dataset.Manufacturer = "OPTOPOL Technology S.A."
    dataset.Columns = 512
    dataset.Rows = 512
    dataset.NumberOfFrames = 5
    dataset.AccessionNumber = 0

    # Add the PerFrameFunctionalGroupsSequence
    functional_group = Dataset()
    functional_group.OphthalmicFrameLocationSequence = []

    dataset.PerFrameFunctionalGroupsSequence = [functional_group]

    # Optionally set the current date and time for the dataset
    dt = datetime.datetime.now()
    dataset.ContentDate = dt.strftime("%Y%m%d")
    dataset.ContentTime = dt.strftime("%H%M%S.%f")  # fractional seconds

    return dataset


@pytest.fixture
def dicom_with_photo_locations():
    """Fixture to create a mocked DICOM FileDataset for valid photo locations."""
    # Create a FileMetaDataset instead of a defaultdict
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian  # or appropriate UID

    # Create the FileDataset object
    dataset = FileDataset(
        "tests/example-dcms/bscans.dcm",
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
        is_implicit_VR=False,
        is_little_endian=True,
    )

    # Mock setting relevant fields to simulate a DICOM file
    dataset.Modality = "OPT"
    dataset.Manufacturer = "Other Manufacturer"
    dataset.Columns = 512
    dataset.Rows = 512
    dataset.NumberOfFrames = 5
    dataset.AccessionNumber = 0

    # Add the PerFrameFunctionalGroupsSequence with valid OphthalmicFrameLocationSequence
    frame_location = Dataset()
    frame_location.OphthalmicFrameLocationSequence = [Dataset()]
    frame_location.OphthalmicFrameLocationSequence[0].ReferenceCoordinates = [0.0, 0.0, 512.0, 512.0]

    # Repeat the same PerFrameFunctionalGroupsSequence for each frame
    dataset.PerFrameFunctionalGroupsSequence = [frame_location for _ in range(dataset.NumberOfFrames)]

    # Optionally set the current date and time for the dataset
    dt = datetime.datetime.now()
    dataset.ContentDate = dt.strftime("%Y%m%d")
    dataset.ContentTime = dt.strftime("%H%M%S.%f")  # fractional seconds

    return dataset


@pytest.fixture
def dicom_base():
    """Base fixture for creating a mocked DICOM FileDataset."""
    # Create a FileMetaDataset instead of a defaultdict
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian  # or appropriate UID

    # Create the FileDataset object
    dataset = FileDataset(
        "test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128, is_implicit_VR=False, is_little_endian=True
    )

    # Mock setting relevant fields to simulate a basic DICOM file
    dataset.AccessionNumber = 0
    dataset.Modality = ImageModality.OCT
    dataset.PatientBirthDate = "19020202"
    dataset.Manufacturer = ""
    dataset.SeriesDescription = ""
    dataset.PatientID = "bbff7a25-d32c-4192-9330-0bb01d49f746"

    return dataset


@pytest.fixture
def csv_data():
    return [
        ["study_id_1", "patient_id_1"],
        ["study_id_2", "patient_id_2"],
    ]


@pytest.fixture
def unique_sorted_results():
    return [
        ["study_id_3", "patient_id_3"],
        ["study_id_4", "patient_id_4"],
    ]


@pytest.fixture
def janitor() -> Generator[list[str], None, None]:
    to_delete: list[str] = []
    yield to_delete
    del_file_paths(to_delete)


@pytest.fixture
def temp_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)
