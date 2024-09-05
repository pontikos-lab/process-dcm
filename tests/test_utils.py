import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from process_dcm.const import ImageModality
from process_dcm.utils import (
    do_date,
    meta_images,
    process_and_save_csv,
    process_dcm,
    process_dcm_meta,
    read_csv,
    set_output_dir,
    update_modality,
    write_to_csv,
)


def test_meta_images_optopol(dicom_opotopol, mocker):
    # Mock the warning print for empty photo locations
    mock_print = mocker.patch("builtins.print")
    update_modality(dicom_opotopol)
    meta = meta_images(dicom_opotopol)

    assert meta["modality"] == "OCT", "Modality extraction failed"
    assert len(meta["contents"]) == 1  # Should correspond to NumberOfFrames
    mock_print.assert_called_with("WARN: empty photo_locations")  # Ensure the warning was printed


def test_meta_images_attribute_error(dicom_attribute_error):
    """Test for handling AttributeError."""
    try:
        update_modality(dicom_attribute_error)
        meta = meta_images(dicom_attribute_error)
        assert "resolutions_mm" not in meta or meta["resolutions_mm"] == {}
    except AttributeError:
        pytest.fail("meta_images failed to handle missing attributes gracefully")


def test_meta_images_with_photo_locations(dicom_with_photo_locations):
    """Test for valid photo locations in meta_images result."""
    update_modality(dicom_with_photo_locations)
    meta = meta_images(dicom_with_photo_locations)

    assert meta["modality"] == "OCT", "Modality extraction failed"
    assert all(
        "photo_locations" in content and len(content["photo_locations"]) == 1 for content in meta["contents"]
    ), "Photo locations not found or incomplete in metadata"


def test_process_dcm_overwrite_and_verbose(input_dir, temp_output_dir, mocker):
    # Mock the verbose print function
    mocker.patch("builtins.print")

    # Test Case 1: Processing DICOM files with overwrite set to False
    process_dcm(input_dir, output_dir=temp_output_dir, overwrite=False, verbose=True)
    output_files_initial = list(Path(temp_output_dir).glob("*.png"))
    assert len(output_files_initial) > 0, "No images were processed initially."

    # Check whether the verbose print was called
    assert print.called, "Verbose print not called"

    # Test Case 2: Reprocessing DICOM files with overwrite set to True
    process_dcm(input_dir, output_dir=temp_output_dir, overwrite=True, verbose=True)
    output_files_after_overwrite = list(Path(temp_output_dir).glob("*.png"))
    assert len(output_files_after_overwrite) == len(output_files_initial), "Output files mismatch after overwrite."

    # Check whether the verbose print was called again
    assert print.called, "Verbose print not called on overwrite"

    # Test Case 3: Ensure metadata.json is created
    metadata_file = Path(temp_output_dir) / "metadata.json"
    assert metadata_file.exists(), "metadata.json was not created."


def test_absolute_path_symlink():
    with patch("pathlib.Path.resolve") as mock_resolve:
        mock_resolve.return_value = Path("/resolved/path")
        assert set_output_dir("/home/user", "/symlink") == "/resolved/path"


def test_absolute_path_broken_symlink():
    with patch("pathlib.Path.resolve", side_effect=FileNotFoundError):
        assert set_output_dir("/home/user", "/broken_symlink") == "/home/user/exported_data"


def test_relative_path():
    assert set_output_dir("/home/user", "relative/path") == "/home/user/relative/path"


def test_broken_symlink_as_relative():
    with patch("pathlib.Path.is_absolute", return_value=False):
        with patch("pathlib.Path.resolve", side_effect=FileNotFoundError):
            assert set_output_dir("/home/user", "exported_data") == "/home/user/exported_data"


def test_relative_path_with_up():
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


def test_update_modality_opt(dicom_base):
    """Test updating modality when the modality is OPT."""
    dicom_base.Modality = "OPT"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality == ImageModality.OCT


def test_update_modality_op_topcon(dicom_base):
    """Test updating modality when the modality is OP and manufacturer is TOPCON."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "TOPCON"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality == ImageModality.COLOUR_PHOTO


def test_update_modality_op_ir(dicom_base):
    """Test updating modality when the modality is OP and SeriesDescription contains IR."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "Another Manufacturer"
    dicom_base.SeriesDescription = "SLO IR"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality == ImageModality.SLO_INFRARED


def test_update_modality_unknown(dicom_base):
    """Test updating modality when it results in unknown."""
    dicom_base.Modality = "OP"
    dicom_base.Manufacturer = "Unknown Manufacturer"
    dicom_base.SeriesDescription = "Unknown Description"
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality == ImageModality.UNKNOWN


def test_update_modality_unsupported(dicom_base):
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
def test_update_modality_op_various_descriptions(dicom_base, description, expected_modality):
    """Test updating modality for various SeriesDescription values."""
    dicom_base.Modality = "OP"
    dicom_base.SeriesDescription = description
    assert update_modality(dicom_base) is True
    assert dicom_base.Modality == expected_modality


def test_process_dcm_meta_with_D_in_keep_and_mapping(dicom_base):
    # Call the function with "D" in keep
    with tempfile.TemporaryDirectory() as tmpdir:
        process_dcm_meta([dicom_base], tmpdir, keep="D", mapping="tests/map.csv")
        rjson = json.load(open(os.path.join(tmpdir, "metadata.json")))
        assert rjson["patient"]["date_of_birth"] == "1902-01-01"
        assert rjson["patient"]["patient_key"] == "00123"


def test_process_and_save_csv(csv_data, unique_sorted_results):
    with tempfile.TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Create initial reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])

        # Process and save new CSV data
        process_and_save_csv(unique_sorted_results, reserved_csv, verbose=True)

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


def test_process_and_save_csv_no_existing_file(unique_sorted_results):
    with tempfile.TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Process and save new CSV data with no existing reserved CSV
        process_and_save_csv(unique_sorted_results, reserved_csv, verbose=True)

        # Check if reserved CSV was created and contains the expected data
        created_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *unique_sorted_results]
        assert created_data == expected_data, f"Expected {expected_data}, but got {created_data}"


def test_process_and_save_csv_with_existing_file(csv_data, unique_sorted_results):
    with tempfile.TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Create initial reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])

        # Process and save new CSV data
        process_and_save_csv(unique_sorted_results, reserved_csv, verbose=True)

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


def test_process_and_save_csv_no_changes(csv_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        reserved_csv = Path(temp_dir) / "reserved.csv"

        # Create reserved CSV with initial csv_data
        write_to_csv(reserved_csv, csv_data, header=["study_id", "patient_id"])

        # Process and save the same CSV data
        process_and_save_csv(csv_data, reserved_csv, verbose=True)

        # Check if reserved CSV remains unchanged
        unchanged_data = read_csv(reserved_csv)
        expected_data = [["study_id", "patient_id"], *csv_data]
        assert unchanged_data == expected_data, f"Expected {expected_data}, but got {unchanged_data}"

        # Check that no backup was created
        backup_file = Path(temp_dir) / "reserved_1.csv"
        assert not backup_file.exists(), f"Did not expect backup file {backup_file} to exist"
