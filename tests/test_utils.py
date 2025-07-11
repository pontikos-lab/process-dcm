import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import pytest
import typer
from pydicom.dataset import FileDataset
from pytest_mock import MockerFixture

from process_dcm.const import ImageModality
from process_dcm.utils import (
    delete_if_empty,
    do_date,
    get_md5,
    get_versioned_filename,
    meta_images,
    process_and_save_csv,
    process_dcm,
    process_dcm_meta,
    read_csv,
    set_output_dir,
    tree,
    update_modality,
    write_to_csv,
)
from tests.conftest import bottom, create_directory_structure


def test_meta_images_optopol(dicom_opotopol: FileDataset, mocker: MockerFixture) -> None:
    """Test the meta_images function with an Optopol DICOM dataset."""
    # Mock the typer.secho call for empty photo locations
    mock_secho = mocker.patch("typer.secho")
    update_modality(dicom_opotopol)
    meta = meta_images(dicom_opotopol)

    assert meta["modality"] == "OCT", "Modality extraction failed"
    assert len(meta["contents"]) == 1  # Should correspond to NumberOfFrames
    mock_secho.assert_called_with("\nWARN: empty photo_locations", fg=typer.colors.RED)


def test_meta_images_attribute_error(dicom_attribute_error: FileDataset) -> None:
    """Test for handling AttributeError."""
    try:
        update_modality(dicom_attribute_error)
        meta = meta_images(dicom_attribute_error)
        assert "resolutions_mm" not in meta or meta["resolutions_mm"] == {}
    except AttributeError:
        pytest.fail("meta_images failed to handle missing attributes gracefully")


def test_meta_images_with_photo_locations(dicom_with_photo_locations: FileDataset) -> None:
    """Test for valid photo locations in meta_images result."""
    update_modality(dicom_with_photo_locations)
    meta = meta_images(dicom_with_photo_locations)

    assert meta["modality"] == "OCT", "Modality extraction failed"
    assert all("photo_locations" in content and len(content["photo_locations"]) == 1 for content in meta["contents"]), (
        "Photo locations not found or incomplete in metadata"
    )


def test_absolute_path_symlink() -> None:
    with patch("pathlib.Path.resolve") as mock_resolve:
        mock_resolve.return_value = Path("/resolved/path")
        assert set_output_dir("/home/user", "/symlink") == "/resolved/path"


def test_absolute_path_broken_symlink() -> None:
    with patch("pathlib.Path.resolve", side_effect=FileNotFoundError):
        assert set_output_dir("/home/user", "/broken_symlink") == "/home/user/exported_data"


def test_relative_path() -> None:
    assert set_output_dir("/home/user", "relative/path") == "/home/user/relative/path"


def test_broken_symlink_as_relative() -> None:
    with patch("pathlib.Path.is_absolute", return_value=False):
        with patch("pathlib.Path.resolve", side_effect=FileNotFoundError):
            assert set_output_dir("/home/user", "exported_data") == "/home/user/exported_data"


def test_relative_path_with_up() -> None:
    assert set_output_dir("/home/user", "../up/relative") == "/home/user/../up/relative"


def test_do_date() -> None:
    input_format = "%Y%m%d%H%M%S.%f"
    output_format = "%Y-%m-%d %H:%M:%S"
    date_str = "20220101000000.00"
    expected_output = "2022-01-01 00:00:00"
    assert do_date(date_str, input_format, output_format) == expected_output
    assert do_date("20230723", "%Y%m%d", "%Y-%m-%d") == "2023-07-23"
    assert do_date("20230723102530.123456", "%Y%m%d%H%M%S.%f", "%Y-%m-%d %H:%M:%S") == "2023-07-23 10:25:30"
    assert do_date("InvalidDate", "%Y%m%d", "%Y-%m-%d") == ""


def test_update_modality_opt(dicom_base: FileDataset) -> None:
    """Test updating modality when the modality is OPT."""
    dicom_base.Modality = "OPT"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality is ImageModality.OCT  # type: ignore


def test_update_modality_op_topcon(dicom_base: FileDataset) -> None:
    """Test updating modality when the modality is OP and manufacturer is TOPCON."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "TOPCON"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality is ImageModality.COLOUR_PHOTO  # type: ignore


def test_update_modality_op_ir(dicom_base: FileDataset) -> None:
    """Test updating modality when the modality is OP and SeriesDescription contains IR."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "Another Manufacturer"
    dicom_base.SeriesDescription = "SLO IR"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality is ImageModality.SLO_INFRARED  # type: ignore


def test_update_modality_unknown(dicom_base: FileDataset) -> None:
    """Test updating modality when it results in unknown."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "Unknown Manufacturer"
    dicom_base.SeriesDescription = "Unknown Description"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality is ImageModality.UNKNOWN  # type: ignore


def test_update_modality_unsupported(dicom_base: FileDataset) -> None:
    """Test update_modality when the modality is unsupported."""
    dicom_base.Modality = "UNSUPPORTED"
    assert update_modality(dicom_base) is False


@pytest.mark.parametrize(
    "description, expected_modality",
    [
        (" IR", ImageModality.SLO_INFRARED),
        (" BAF ", ImageModality.AUTOFLUORESCENCE_BLUE),
        (" ICGA ", ImageModality.INDOCYANINE_GREEN_ANGIOGRAPHY),
        (" FA&ICGA ", ImageModality.FA_ICGA),
        (" FA ", ImageModality.FLUORESCEIN_ANGIOGRAPHY),
        (" RF ", ImageModality.RED_FREE),
        (" BR ", ImageModality.REFLECTANCE_BLUE),
        (" MColor ", ImageModality.REFLECTANCE_MCOLOR),
    ],
)
def test_update_modality_op_various_descriptions(
    dicom_base: FileDataset, description: str, expected_modality: ImageModality
) -> None:
    """Test updating modality for various SeriesDescription values."""
    dicom_base.Modality = "OP"
    dicom_base.SeriesDescription = description
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality is expected_modality  # type: ignore


def test_process_dcm_meta_with_D_in_keep_and_mapping(dicom_base: FileDataset) -> None:
    # Call the function with "D" in keep
    with TemporaryDirectory() as tmpdir:
        process_dcm_meta([dicom_base], Path(tmpdir), keep="D", mapping="tests/map.csv")
        rjson = json.load(open(os.path.join(tmpdir, "metadata.json")))
        assert rjson["patient"]["date_of_birth"] == "1902-01-01"
        assert rjson["patient"]["patient_key"] == "00123"


def test_process_and_save_csv(csv_data: list[list[str]], unique_sorted_results: list[list[str]]) -> None:
    with TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Create initial reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])

        # Process and save new CSV data
        process_and_save_csv(unique_sorted_results, reserved_csv)

        # Check if reserved CSV was updated
        updated_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *unique_sorted_results]
        assert updated_data == expected_data, f"Expected {expected_data}, but got {updated_data}"

        # Check if backup was created
        backup_file = Path(temp_dir) / "reserved_1.csv"
        assert backup_file.exists(), f"Expected backup file {backup_file} to exist"

        backup_data = read_csv(backup_file)
        expected_backup_data = [["study_id", "patient_id"], *csv_data]
        assert backup_data == expected_backup_data, f"Expected {expected_backup_data}, but got {backup_data}"


def test_process_and_save_csv_no_existing_file(unique_sorted_results: list[list[str]]) -> None:
    with TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Process and save new CSV data with no existing reserved CSV
        process_and_save_csv(unique_sorted_results, reserved_csv)

        # Check if reserved CSV was created and contains the expected data
        created_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *unique_sorted_results]
        assert created_data == expected_data, f"Expected {expected_data}, but got {created_data}"


def test_process_and_save_csv_with_existing_file(
    csv_data: list[list[str]], unique_sorted_results: list[list[str]]
) -> None:
    with TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"
        reserved_csv1 = get_versioned_filename(reserved_csv, 1)

        # Create initial reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])
        write_to_csv(reserved_csv1, csv_data, header=["study_id", "patient_id"])

        # Process and save new CSV data
        process_and_save_csv(unique_sorted_results, reserved_csv)

        # Check if reserved CSV was updated
        updated_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *unique_sorted_results]
        assert updated_data == expected_data, f"Expected {expected_data}, but got {updated_data}"

        # Check if backup was created
        backup_file = Path(temp_dir) / "reserved_1.csv"
        assert backup_file.exists(), f"Expected backup file {backup_file} to exist"

        backup_data = read_csv(backup_file)
        expected_backup_data = [["study_id", "patient_id"], *csv_data]
        assert backup_data == expected_backup_data, f"Expected {expected_backup_data}, but got {backup_data}"


def test_process_and_save_csv_no_changes(csv_data: list[list[str]]) -> None:
    with TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Create reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])

        # Process and save the same CSV data
        process_and_save_csv(csv_data, reserved_csv.name)

        # Check if reserved CSV remains unchanged
        unchanged_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *csv_data]
        assert unchanged_data == expected_data, f"Expected {expected_data}, but got {unchanged_data}"

        # Check that no backup was created
        backup_file = Path(temp_dir) / "reserved_1.csv"
        assert not backup_file.exists(), f"Did not expect backup file {backup_file} to exist"


# skip this test for CI
def test_process_dcm(temp_dir: str, input_dir2: Path, mocker: Any) -> None:
    mock_secho = mocker.patch("typer.secho")
    output_dir = Path(temp_dir)
    p, s, new_old = process_dcm(input_path=input_dir2, output_dir=output_dir, overwrite=True)
    output_files_initial = list(output_dir.rglob("*.png"))
    assert len(output_files_initial) == 130, "No images were processed initially."
    assert set(new_old) == {("2910892726", "010-0001")}

    # Run process_dcm function with overwrite=False, should skip processing
    p, s, new_old = process_dcm(input_path=input_dir2, output_dir=Path(temp_dir), overwrite=False)

    msg = f"\nOutput directory '{output_dir / '2910892726_20180724_162720_63d3f1_OS_OCT.DCM'}' already exists with metadata and images. Skipping..."  # noqa: E501
    mock_secho.assert_called_with(msg, fg=typer.colors.YELLOW)
    assert len(list(output_dir.rglob("*.png"))) == len(output_files_initial)


def test_process_dcm_dummy(temp_dir: str) -> None:
    p, s, new_old = process_dcm(input_path=Path("tests/dummy_ex"), output_dir=Path(temp_dir), overwrite=True)
    assert new_old == [("2375458543", "123456")]
    assert (
        get_md5(os.path.join(temp_dir, "2375458543__340692_OU_U.DCM", "metadata.json"), bottom)
        == "a770962058621bd0b4e6e6a5ba5e1e7a"
    )


def test_process_dcm_dummy_group(temp_dir: str) -> None:
    p, s, new_old = process_dcm(
        input_path=Path("tests/dummy_ex"), output_dir=Path(temp_dir), overwrite=True, time_group=True
    )
    assert new_old == [("2375458543", "123456")]
    assert (
        get_md5(os.path.join(temp_dir, "2375458543__OU_U.DCM", "metadata.json"), bottom)
        == "a770962058621bd0b4e6e6a5ba5e1e7a"
    )


def test_process_dcm_dummy_mapping(temp_dir: str) -> None:
    p, s, pair = process_dcm(
        input_path=Path("tests/dummy_ex"), output_dir=Path(temp_dir), overwrite=True, mapping="tests/map.csv"
    )
    assert pair == [("2375458543", "123456")]
    assert (
        get_md5(os.path.join(temp_dir, "2375458543__340692_OU_U.DCM", "metadata.json"), bottom)
        == "7d60d85ffcf442ccece3948af93873bc"
    )


def test_delete_empty_folder(temp_directory: Path) -> None:
    empty_folder = temp_directory / "empty"
    empty_folder.mkdir()
    assert delete_if_empty(empty_folder)
    assert not empty_folder.exists()


def test_delete_nested_empty_folders(temp_directory: Path) -> None:
    structure: dict = {"parent": {"child1": {}, "child2": {"grandchild": {}}}}
    create_directory_structure(temp_directory, structure)
    assert delete_if_empty(temp_directory / "parent")
    assert not (temp_directory / "parent").exists()


def test_non_empty_folder(temp_directory: Path) -> None:
    structure = {"non_empty": {"file.txt": "content"}}
    create_directory_structure(temp_directory, structure)
    assert not delete_if_empty(temp_directory / "non_empty")
    assert (temp_directory / "non_empty").exists()
    assert (temp_directory / "non_empty" / "file.txt").exists()


def test_mixed_structure(temp_directory: Path) -> None:
    structure = {"mixed": {"empty1": {}, "empty2": {}, "non_empty": {"file.txt": "content"}}}
    create_directory_structure(temp_directory, structure)
    tree1 = tree(temp_directory)
    assert tree1 == "mixed\n    └── empty1\n    └── empty2\n    └── non_empty\n        └── file.txt\n"
    assert not delete_if_empty(temp_directory / "mixed", n_jobs=2)
    tree2 = tree(temp_directory)
    assert tree2 == "mixed\n    └── non_empty\n        └── file.txt\n"
    assert (temp_directory / "mixed").exists()
    assert not (temp_directory / "mixed" / "empty1").exists()
    assert not (temp_directory / "mixed" / "empty2").exists()
    assert (temp_directory / "mixed" / "non_empty").exists()


def test_tree_with_invalid_directory() -> None:
    invalid_directory = "/path/to/invalid/directory"
    expected_error_message = f"Error: '{invalid_directory}' is not a valid directory."

    # Ensure that the path does not exist or is not a directory
    assert not os.path.isdir(invalid_directory)

    result = tree(invalid_directory)
    assert result == expected_error_message


def test_non_existent_path() -> None:
    assert not delete_if_empty("/path/does/not/exist")


def test_file_path(temp_directory: Path) -> None:
    file_path = temp_directory / "file.txt"
    file_path.write_text("content")
    assert not delete_if_empty(file_path)
    assert file_path.exists()


@pytest.mark.parametrize("n_jobs", [2, 4, 8])
def test_parallel_processing(temp_directory: Path, n_jobs: int) -> None:
    structure: dict = {
        "nested1": {
            "subnested1": {},  # An empty sub-subdirectory
            "subnested2": {},  # Another empty sub-subdirectory
        },
        "nested2": {
            "subnested1": {},  # An empty sub-subdirectory
        },
        "empty": {},  # Another top-level empty directory
    }
    create_directory_structure(temp_directory, structure)

    result = delete_if_empty(temp_directory, n_jobs=n_jobs)

    # The top-level directory should be deleted because all subdirectories are empty
    assert result is True, "Expected the top-level directory to be empty and deleted"
    assert not temp_directory.exists(), "Expected the top-level directory to no longer exist"


@pytest.mark.parametrize("n_jobs", [2, 4, 8])
def test_parallel_processing_mixed_structure(temp_directory: Path, n_jobs: int) -> None:
    structure = {
        "nested1": {
            "subnested1": {},  # An empty sub-subdirectory
            "subnested2": {},  # Another empty sub-subdirectory
        },
        "empty": {},  # Another top-level empty directory
        "file.txt": "content",  # A file in the top-level directory, should prevent deletion
    }
    create_directory_structure(temp_directory, structure)

    result = delete_if_empty(temp_directory, n_jobs=n_jobs)

    # The top-level directory should not be deleted because it contains a file
    assert result is False, "Expected the top-level directory to not be deleted due to the presence of files"
    assert temp_directory.exists(), "Expected the top-level directory to still exist"
    assert (temp_directory / "file.txt").exists(), "Expected the file to still exist in the top-level directory"
