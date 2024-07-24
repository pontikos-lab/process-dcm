import tempfile
from collections import defaultdict
from pathlib import Path

import pytest
from pydicom.dataset import Dataset, FileDataset
from typer.testing import CliRunner

from process_dcm import __version__ as version


def pytest_report_header():
    return f">>>\tVersion: {version}\n"


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


@pytest.fixture
def dicom_opotopol():
    """Fixture to create a mocked DICOM FileDataset for OPTOPOL."""
    dataset = FileDataset("tests/example-dcms/bscans.dcm", {}, file_meta=defaultdict(str), preamble=b"\0" * 128)

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

    return dataset


@pytest.fixture
def dicom_attribute_error():
    """Fixture to create a mocked DICOM FileDataset for AttributeError simulation."""
    dataset = FileDataset("tests/example-dcms/bscans.dcm", {}, file_meta=defaultdict(str), preamble=b"\0" * 128)

    # Mock setting relevant fields to simulate a DICOM file
    dataset.Modality = "OPT"
    dataset.Manufacturer = "OPTOPOL Technology S.A."
    dataset.Columns = 512
    dataset.Rows = 512
    dataset.NumberOfFrames = 5
    dataset.AccessionNumber = 0

    functional_group = Dataset()
    functional_group.OphthalmicFrameLocationSequence = []

    dataset.PerFrameFunctionalGroupsSequence = [functional_group]

    return dataset


@pytest.fixture
def dicom_with_photo_locations():
    """Fixture to create a mocked DICOM FileDataset for valid photo locations."""
    dataset = FileDataset("tests/example-dcms/bscans.dcm", {}, file_meta=defaultdict(str), preamble=b"\0" * 128)

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
    dataset.PerFrameFunctionalGroupsSequence = [frame_location for _ in range(dataset.NumberOfFrames)]

    return dataset


@pytest.fixture
def dicom_base():
    """Base fixture for creating a mocked DICOM FileDataset."""
    dataset = FileDataset("test.dcm", {}, file_meta=defaultdict(str), preamble=b"\0" * 128)
    dataset.Modality = ""
    dataset.Manufacturer = ""
    dataset.SeriesDescription = ""
    return dataset
