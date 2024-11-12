"""utils module."""

import csv
import filecmp
import hashlib
import json
import os
import shutil
import tempfile
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import typer
from natsort import natsorted
from PIL import Image
from pydicom.dataset import FileDataset
from pydicom.filereader import dcmread

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV, ImageModality

warnings.filterwarnings("ignore", category=UserWarning, message="A value of type *")


def do_date(date_str: str, input_format: str, output_format: str) -> str:
    """Convert DCM datetime strings to metadata.json string format."""
    if "." not in date_str:
        input_format = input_format.split(".")[0]
    try:
        dt = datetime.strptime(date_str, input_format)
        return dt.strftime(output_format)
    except Exception:
        return ""


def set_output_dir(ref_path: str | Path, a_path: str | Path) -> str:
    """Determines the appropriate output directory for a given path.

    This function handles absolute and relative paths, resolving symlinks
    if present. If a path is a broken symlink or a relative path,
    it is combined with a reference path to create the output directory.

    Args:
        ref_path: A reference path used when the given path is relative or broken.
        a_path: The path to be analyzed and potentially resolved.

    Returns:
        The determined output directory as a POSIX string (using forward slashes).
        - If `a_path` is absolute and valid, it is returned after symlink resolution.
        - If `a_path` is a broken symlink, it returns the combination of `ref_path` and "exported_data".
        - If `a_path` is relative, it returns the combination of `ref_path` and the resolved relative path.
    """
    path_obj = Path(a_path)

    if path_obj.is_absolute():
        try:
            # Resolve symlinks and return real path
            return path_obj.resolve(strict=False).as_posix()
        except FileNotFoundError:
            return os.path.join(ref_path, "exported_data")  # Handle broken symlink
    else:
        return os.path.join(ref_path, path_obj.as_posix())


def meta_images(dcm_obj: FileDataset) -> dict:
    """Takes a DICOM file dataset and extracts metadata from it to create a dictionary of image metadata.

    Args:
        dcm_obj (FileDataset): The input DICOM file dataset object.

    Returns:
        dict: A dictionary containing the extracted metadata from the input DICOM file dataset.
    """
    meta: dict = defaultdict(dict)
    mod = dcm_obj.get("Modality")
    meta["modality"] = mod.value
    meta["group"] = dcm_obj.get("AccessionNumber", 0)
    meta["size"]["width"] = dcm_obj.get("Columns", 0)
    meta["size"]["height"] = dcm_obj.get("Rows", 0)
    meta["field_of_view"] = dcm_obj.get("HorizontalFieldOfView")
    meta["source_id"] = f"{dcm_obj.Modality.code}-{dcm_obj.AccessionNumber}"
    if mod.is_2d_image:
        meta["dimensions_mm"]["width"] = dcm_obj.get("Columns", 0) * dcm_obj.get("PixelSpacing", [0, 0])[1]
        meta["dimensions_mm"]["height"] = dcm_obj.get("Rows", 0) * dcm_obj.get("PixelSpacing", [0, 0])[0]
        meta["resolutions_mm"]["width"] = dcm_obj.get("PixelSpacing", [0, 0])[1]
        meta["resolutions_mm"]["height"] = dcm_obj.get("PixelSpacing", [0, 0])[0]
        meta["contents"] = [{}]
    elif mod.code == "OCT":
        ss = dcm_obj.get("SharedFunctionalGroupsSequence")
        if "OPTOPOL" in dcm_obj.Manufacturer.upper():
            ss = dcm_obj.get("PerFrameFunctionalGroupsSequence")
        if ss:
            try:
                meta["dimensions_mm"]["width"] = (
                    dcm_obj.get("Columns", 0) * ss[0].PixelMeasuresSequence[0].PixelSpacing[1]
                )
                meta["dimensions_mm"]["height"] = (
                    dcm_obj.get("Rows", 0) * ss[0].PixelMeasuresSequence[0].PixelSpacing[0]
                )
                meta["dimensions_mm"]["depth"] = (dcm_obj.get("NumberOfFrames", 1) - 1) * ss[0].PixelMeasuresSequence[
                    0
                ].get("SliceThickness", 0)
                meta["resolutions_mm"]["width"] = ss[0].PixelMeasuresSequence[0].PixelSpacing[1]
                meta["resolutions_mm"]["height"] = ss[0].PixelMeasuresSequence[0].PixelSpacing[0]
                meta["resolutions_mm"]["depth"] = ss[0].PixelMeasuresSequence[0].get("SliceThickness", 0)
            except AttributeError:
                pass
        meta["contents"] = []
        pp = dcm_obj.get("PerFrameFunctionalGroupsSequence")
        if pp:
            for ii in pp:
                # y0, x0, y1, x1
                # [640.0, 128.0, 640.0, 640.0]
                oo = ii.get("OphthalmicFrameLocationSequence")
                if oo:
                    cc = ii.OphthalmicFrameLocationSequence[0].ReferenceCoordinates
                    meta["contents"].append(
                        {"photo_locations": [{"start": {"x": cc[1], "y": cc[0]}, "end": {"x": cc[3], "y": cc[2]}}]}
                    )
                else:
                    typer.secho("WARN: empty photo_locations", fg=typer.colors.RED)
                    meta["contents"].append({"photo_locations": []})

    return meta


def process_dcm_meta(
    dcm_objs: list[FileDataset], output_dir: str, mapping: str = "", keep: str = ""
) -> tuple[str, str]:
    """Extract and save metadata from a list of DICOM files into a JSON file.

    Args:
        dcm_objs (list[FileDataset]): A list of FileDataset objects representing the DICOM files.
        output_dir (str): The directory where the metadata JSON file will be saved.
        mapping (str, optional): Path to the CSV file containing patient ID to study ID mapping.
                                 If not provided and patient_id is not anonymized,
                                 a '{RESERVED_CSV}' file will be generated.
        keep (str, optional): String containing the letters indicating which fields to keep.
                              Options: 'p' for patient key, 'n' for patient names, 'd' for precise date of birth,
                              'D' for anonymized date of birth (year only), and 'g' for gender. Defaults to "".

    Returns:
        tuple[str, str]: A tuple containing the new patient key and the original patient key.
    """
    meta_file = os.path.join(output_dir, "metadata.json")
    metadata: dict = defaultdict(dict)
    metadata["patient"] = {}
    metadata["exam"] = {}
    metadata["series"] = {}
    metadata["images"]["images"] = []
    metadata["parser_version"] = [1, 5, 2]
    metadata["py_dcm_version"] = list(map(int, __version__.split(".")))

    keep_gender = "g" in keep
    keep_names = "n" in keep
    keep_patient_key = "p" in keep

    # Read the mapping file if provided
    patient_to_study = {}
    if mapping:
        patient_to_study = dict(read_csv(mapping))

    original_patient_key = ""
    new_patient_key = ""

    for dcm_obj in dcm_objs:
        patient_key = dcm_obj.get("PatientID", "")
        original_patient_key = patient_key
        if patient_key in patient_to_study:
            patient_key = patient_to_study[patient_key]
        elif not keep_patient_key:
            patient_key = get_hash(patient_key)

        new_patient_key = patient_key

        first_name = dcm_obj.get("PatientName.name_prefix")
        last_name = dcm_obj.get("PatientName.name_suffix")
        if not keep_names:
            first_name = None if first_name else first_name
            last_name = None if last_name else last_name

        date_of_birth = do_date(dcm_obj.get("PatientBirthDate", "10010101"), "%Y%m%d", "%Y-%m-%d")
        if "D" in keep:
            year = date_of_birth[:4]
            date_of_birth = f"{year}-01-01"
        elif "d" not in keep:
            date_of_birth = "1001-01-01"

        gender = dcm_obj.get("PatientSex")
        if not keep_gender:
            gender = None if gender else gender

        metadata["patient"]["patient_key"] = patient_key
        metadata["patient"]["first_name"] = first_name
        metadata["patient"]["last_name"] = last_name
        metadata["patient"]["date_of_birth"] = date_of_birth
        metadata["patient"]["gender"] = gender
        metadata["patient"]["source_id"] = dcm_obj.get("StudyInstanceUID")

        metadata["exam"]["manufacturer"] = dcm_obj.get("Manufacturer")
        metadata["exam"]["scan_datetime"] = do_date(
            dcm_obj.get("AcquisitionDateTime", "00000000"), "%Y%m%d%H%M%S.%f", "%Y-%m-%d %H:%M:%S"
        )
        metadata["exam"]["scanner_model"] = dcm_obj.get("ManufacturerModelName")
        metadata["exam"]["scanner_serial_number"] = dcm_obj.get("DeviceSerialNumber")
        metadata["exam"]["scanner_software_version"] = str(dcm_obj.get("SoftwareVersions"))
        metadata["exam"]["scanner_last_calibration_date"] = ""
        metadata["exam"]["source_id"] = dcm_obj.get("StudyInstanceUID")

        metadata["series"]["laterality"] = dcm_obj.get("ImageLaterality", dcm_obj.get("Laterality"))
        metadata["series"]["fixation"] = ""
        aa = dcm_obj.get("AnatomicRegionSequence")
        if aa:
            metadata["series"]["fixation"] = dcm_obj.get("AnatomicRegionSequence")[0].get("CodeMeaning")
        metadata["series"]["anterior"] = ""  # bool
        metadata["series"]["protocol"] = dcm_obj.get("SeriesDescription")  # Guessing, "Rectangular volume"
        metadata["series"]["source_id"] = dcm_obj.get("StudyInstanceUID")
        metadata["images"]["images"].append(meta_images(dcm_obj))
    if len(dcm_objs) > 1:
        metadata["series"]["protocol"] = "OCT ART Volume"

    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=4)

    return (new_patient_key, original_patient_key)


process_dcm_meta.__doc__ = (
    process_dcm_meta.__doc__.format(RESERVED_CSV=RESERVED_CSV) if process_dcm_meta.__doc__ else None
)


def update_modality(dcm: FileDataset) -> bool:
    """Updates the modality of the given DICOM object based on its Manufacturer and SeriesDescription attributes.

    Args:
        dcm (pydicom.dataset.FileDataset): The DICOM object to update.

    Returns:
        bool: True if modality is updated; False if the modality is unsupported.
    """
    if dcm.Modality == "OPT":
        dcm.Modality = ImageModality.OCT
    elif dcm.Modality == "OP":
        if dcm.Manufacturer.upper() == "TOPCON":
            dcm.Modality = ImageModality.COLOUR_PHOTO
        elif dcm.Manufacturer.upper() == "OPTOS" and dcm.HorizontalFieldOfView == 200:
            dcm.Modality = ImageModality.PSEUDOCOLOUR_ULTRAWIDEFIELD
        elif " IR" in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.SLO_INFRARED
        elif " BAF " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.AUTOFLUORESCENCE_BLUE
        elif " ICGA " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.INDOCYANINE_GREEN_ANGIOGRAPHY
        elif " FA&ICGA " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.FA_ICGA
        elif " FA " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.FLUORESCEIN_ANGIOGRAPHY
        elif " RF " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.RED_FREE
        elif " BR " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.REFLECTANCE_BLUE
        elif " MColor " in dcm.get("SeriesDescription", ""):
            dcm.Modality = ImageModality.REFLECTANCE_MCOLOR
        else:
            dcm.Modality = ImageModality.UNKNOWN
    else:
        return False  # Unsupported modality, continue

    return True  # Modality updated successfully


def group_dcms_by_acquisition_time(dcms: list[FileDataset], tolerance_seconds: int = 2) -> dict[str, list[FileDataset]]:
    """Group DICOM files by AcquisitionDateTime within the specified tolerance."""
    grouped_dcms: dict[str, list[FileDataset]] = defaultdict(list)
    for dcm in dcms:
        acquisition_datetime_str = dcm.get("AcquisitionDateTime", "unknown")
        if acquisition_datetime_str != "unknown":
            acquisition_datetime = datetime.strptime(acquisition_datetime_str, "%Y%m%d%H%M%S.%f")
            # Find the closest group within the tolerance
            for group_time_str, group in grouped_dcms.items():
                if group_time_str != "unknown":
                    group_time = datetime.strptime(group_time_str, "%Y%m%d%H%M%S.%f")
                    if abs(acquisition_datetime - group_time) <= timedelta(seconds=tolerance_seconds):
                        grouped_dcms[group_time_str].append(dcm)
                        break
            else:
                # If no close group found, create a new one
                grouped_dcms[acquisition_datetime_str].append(dcm)
        else:
            grouped_dcms["unknown"].append(dcm)

    return grouped_dcms


def process_dcm(
    input_dir: str | Path,
    image_format: str = "png",
    output_dir: str = "exported_data",
    mapping: str = "",
    keep: str = "",
    overwrite: bool = False,
    quiet: bool = False,
    group: bool = False,
    tol: int = 2,
) -> tuple[str, str]:
    """Process DICOM files from the input directory and save images in the specified format.

    Args:
        input_dir (str | Path): Path to the directory containing DICOM files.
        image_format (str, optional): The format in which to save the images. Defaults to "png".
        output_dir (str, optional): Path to the directory where images will be saved. Defaults to "exported_data".
        mapping (str, optional): Path to the CSV file containing patient ID to study ID mapping.
                                 If not provided and patient_id is not anonymized,
                                 a '{RESERVED_CSV}' file will be generated.
        keep (str, optional): String containing the letters indicating which fields to keep.
                              Options: 'p' for patient key, 'n' for patient names, 'd' for precise date of birth,
                              'D' for anonymized date of birth (year only), and 'g' for gender. Defaults to "".
        overwrite (bool, optional): Whether to overwrite existing files in the output directory. Defaults to False.
        quiet (bool, optional): Silence verbosity. Defaults to False.
        group (bool, optional): Whether to re-group DICOM files by AcquisitionDateTime. Defaults to False.
        tol (int, optional): Tolerance in seconds for grouping DICOM files by AcquisitionDateTime. Defaults to 2.

    Returns:
        tuple[str, str]: A tuple containing the new patient key and the original patient key.
    """
    # Load DICOM files from input directory
    dcm_objs = [dcmread(os.path.join(input_dir, f)) for f in os.listdir(input_dir) if f.endswith(".dcm")]
    dcm_objs.sort(key=lambda x: x.Modality)
    patient_id = dcm_objs[0].PatientID

    keep_patient_key = "p" in keep
    org_output_dir = output_dir

    # Read the mapping file if provided
    patient_to_study = {}
    hash_pat_id = get_hash(patient_id)
    if mapping:
        patient_to_study = dict(read_csv(mapping))

    if patient_to_study:
        new_patient_key = patient_to_study.get(patient_id, hash_pat_id)
        output_dir = output_dir.replace(os.sep + patient_id + os.sep, os.sep + new_patient_key + os.sep)
    elif not keep_patient_key:
        output_dir = output_dir.replace(os.sep + patient_id + os.sep, os.sep + hash_pat_id + os.sep)

    if overwrite:
        for folder in [output_dir, org_output_dir]:
            shutil.rmtree(folder, ignore_errors=True)
    else:
        if os.path.exists(output_dir):
            # Check if output_dir contains metadata.json and files with the specified image_format
            has_metadata = os.path.exists(os.path.join(output_dir, "metadata.json"))
            has_images = any(f.endswith(image_format) for f in os.listdir(output_dir))

            if has_metadata and has_images:
                if not quiet:
                    typer.secho(
                        f"Output directory '{output_dir}' already exists with metadata and images. Skipping...",
                        fg="yellow",
                    )
                return "", ""

    dcms = []
    # using AccessionNumber to emulate group_id
    for dcm in dcm_objs:
        # update modality
        if not update_modality(dcm):
            continue  # Ignore any other modalities

        dcm.AccessionNumber = 0

        if not dcm.get("NumberOfFrames"):
            dcm.NumberOfFrames = 1

        dcms.append(dcm)

    if group:
        # Group DICOM files by AcquisitionDateTime
        grouped_dcms = group_dcms_by_acquisition_time(dcms, tolerance_seconds=tol)

        # Sort groups by AcquisitionDateTime
        sorted_groups = sorted(grouped_dcms.items())

        for gid, (_, group_dcms) in enumerate(sorted_groups):
            group_dir = os.path.join(output_dir, f"group_{gid}")
            os.makedirs(group_dir, exist_ok=True)

            for dcm in group_dcms:
                # process images
                arr = dcm.pixel_array

                if dcm.NumberOfFrames == 1:
                    arr = np.expand_dims(arr, axis=0)

                for i in range(dcm.NumberOfFrames):
                    out_img = os.path.join(group_dir, f"{dcm.Modality.code}-{dcm.AccessionNumber}_{i}.{image_format}")
                    array = cv2.normalize(arr[i], None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)  # type: ignore #AWSS
                    image = Image.fromarray(array)
                    image.save
                    image.save(out_img)

            # Process metadata for the grouped DCMs
            new, old = process_dcm_meta(dcm_objs=group_dcms, output_dir=group_dir, mapping=mapping, keep=keep)

    else:
        os.makedirs(output_dir, exist_ok=True)

        for dcm in dcms:
            # process images
            arr = dcm.pixel_array

            if dcm.NumberOfFrames == 1:
                arr = np.expand_dims(arr, axis=0)

            for i in range(dcm.NumberOfFrames):
                out_img = os.path.join(output_dir, f"{dcm.Modality.code}-{dcm.AccessionNumber}_{i}.{image_format}")
                if os.path.exists(out_img):
                    dcm.AccessionNumber += 1  # increase group_id
                    out_img = os.path.join(output_dir, f"{dcm.Modality.code}-{dcm.AccessionNumber}_{i}.{image_format}")

                array = cv2.normalize(arr[i], None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)  # type: ignore #AWSS
                image = Image.fromarray(array)
                image.save(out_img)

        new, old = process_dcm_meta(dcm_objs=dcms, output_dir=output_dir, mapping=mapping, keep=keep)

    return new, old


# Ensure that process_dcm_meta docstring includes RESERVED_CSV
process_dcm.__doc__ = process_dcm.__doc__.format(RESERVED_CSV=RESERVED_CSV) if process_dcm.__doc__ else None


def find_dicom_folders_with_base(root_folder: str) -> tuple[int, str, list[str]]:
    """Finds all unique subfolders within the root folder that contain at least one DICOM (.dcm) file.

    It also returns the common base directory and the number of found subfolders.

    Args:
        root_folder (str): The path to the root folder to search for subfolders containing DICOM files.

    Returns:
        tuple[int, str, list[str]]: A tuple containing:
            - int: The number of subfolders containing at least one DICOM file.
            - str: The base directory common to all found subfolders, or an empty string if none found.
            - list[str]: A naturally sorted list of unique full paths of subfolders containing DICOM files.

    Example:
        find_dicom_folders_with_base("/data/patient")
    """
    unique_subfolders = set()
    for dirpath, _, filenames in os.walk(root_folder):
        if any(filename.lower().endswith(".dcm") for filename in filenames):
            unique_subfolders.add(dirpath)  # Add the full path of subfolders containing DCM files

    folders = list(unique_subfolders)
    len_ins = len(folders)

    if len_ins == 0:
        return 0, "", []

    if len_ins == 1:
        base_dir = folders[0].rstrip("/")  # Strip trailing slash if present
        base_dir = os.path.dirname(base_dir)
    else:
        base_dir = os.path.commonpath(folders)  # Get the common base directory

    return len_ins, base_dir, natsorted(folders)


def get_md5(file_path: Path | str | list[str], minus: int = 0) -> str:
    """Calculate the MD5 checksum of a file or list of files, optionally suppressing lines from the bottom."""
    md5_hash = hashlib.md5()

    def process_file(file: Path | str) -> None:
        with open(file, "rb") as f:
            lines = f.readlines()
            for line in lines[:-minus] if minus > 0 else lines:
                md5_hash.update(line)

    if isinstance(file_path, str | Path):
        process_file(file_path)
    elif isinstance(file_path, list):
        for fname in file_path:
            process_file(fname)

    return md5_hash.hexdigest()


def get_hash(value: str) -> str:
    """Get a 10 digit hash based on the input string."""
    hex_dig = hashlib.sha256(str(value).encode()).hexdigest()
    return f"{int(hex_dig[:8], 16):010}"


def get_versioned_filename(base_filename: str, version: int) -> str:
    """Generates a file name with a version suffix.

    Args:
        base_filename (str): The base name of the file.
        version (int): The version number to append.

    Returns:
        str: The generated file name with a version suffix.
    """
    base, ext = os.path.splitext(base_filename)
    return f"{base}_{version}{ext}"


def save_to_temp_file(data: list[list[str]]) -> str:
    """Saves data to a temporary CSV file.

    Args:
        data (list[list[str]]): The data to be written to the temporary file.

    Returns:
        str: The path of the temporary file.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w", newline="", suffix=".csv")
    temp_file.close()  # Close the NamedTemporaryFile to be reused by write_to_csv
    write_to_csv(temp_file.name, data, header=["study_id", "patient_id"])
    return temp_file.name


def files_are_identical(file1: str, file2: str) -> bool:
    """Checks if two files are identical.

    Args:
        file1 (str): The path to the first file.
        file2 (str): The path to the second file.

    Returns:
        bool: True if the files are identical, False otherwise.
    """
    return filecmp.cmp(file1, file2, shallow=False)


def process_and_save_csv(unique_sorted_results: list, reserved_csv: str, quiet: bool = False) -> None:
    """Processes unique sorted results and saves them to the reserved CSV file.

    If the content is identical to the existing file, it leaves the existing file unchanged.
    If the content differs, it renames the existing file with a suffix and saves the new content as the reserved CSV.

    Args:
        unique_sorted_results (list): The data to be written to the CSV file. Each sublist
                                      represents a row with 'study_id' and 'patient_id'.
        reserved_csv (str): The path to the reserved CSV file.
        quiet (bool, optional): Silene verbosity. Defaults to False.
    """
    temp_filename = save_to_temp_file(unique_sorted_results)

    if os.path.exists(reserved_csv):
        if files_are_identical(temp_filename, reserved_csv):
            os.remove(temp_filename)
            if not quiet:
                typer.secho(f"No changes detected. '{reserved_csv}' remains unchanged.", fg="yellow")
        else:
            version = 1
            new_version_filename = get_versioned_filename(reserved_csv, version)
            while os.path.exists(new_version_filename):
                version += 1
                new_version_filename = get_versioned_filename(reserved_csv, version)

            shutil.move(reserved_csv, new_version_filename)
            if not quiet:
                typer.secho(f"Old '{reserved_csv}' renamed to '{new_version_filename}'", fg="yellow")
            shutil.move(temp_filename, reserved_csv)
            if not quiet:
                typer.secho(f"New generated mapping saved to '{reserved_csv}'", fg="yellow")
    else:
        shutil.move(temp_filename, reserved_csv)
        if not quiet:
            typer.secho(f"Generated mapping saved to '{reserved_csv}'", fg="blue")


def read_csv(file_path: str) -> list[list[str]]:
    """Reads a CSV file and returns its contents as a list of rows.

    Each row is represented as a list of strings.

    Args:
        file_path (str): The path to the CSV file to be read.

    Returns:
        list[list[str]]: A list of rows, where each row is a list of strings representing the CSV data.
    """
    with open(file_path) as file:
        reader = csv.reader(file)
        return list(reader)


def write_to_csv(file_path: str | Path, data: list[list[str]], header: list[str] = []) -> None:
    """Writes data to a CSV file at the specified file path.

    Args:
        file_path (str|Path): The path to the CSV file.
        data (list[list[str]]): The data to write to the CSV file. Each sublist represents a row.
        header (list[str], optional): An optional list representing the CSV header.
                                      Defaults to None.
    """
    file_path = Path(file_path)
    with file_path.open(mode="w", newline="") as file:
        writer = csv.writer(file)
        if header:
            writer.writerow(header)
        writer.writerows(data)


def delete_if_empty(folder_path: str | Path, n_jobs: int = 1) -> bool:
    """Check if a given path is an empty folder (including empty subfolders) and delete it if so.

    This function recursively checks if the specified path and its subfolders are empty.
    If a folder is empty, it is deleted. The function can operate in parallel for faster
    processing of large directory structures.

    Args:
        folder_path (Union[str, Path]): The path to check and possibly delete.
        n_jobs (int): The number of parallel jobs to run. Default is 1 (sequential processing).

    Returns:
        bool: True if the path was an empty folder (or contained only empty subfolders) and was successfully deleted,
              False otherwise.
    """
    path = Path(folder_path).resolve()

    if not path.is_dir():
        return False

    def process_folder(folder: Path) -> bool:
        is_empty = True
        for item in folder.iterdir():
            if item.is_file():
                is_empty = False
                break
            if item.is_dir():
                if not delete_if_empty(item, n_jobs=1):  # Recursive call, but without parallelism
                    is_empty = False
                    break

        if is_empty:
            folder.rmdir()
        return is_empty

    if n_jobs > 1:
        with ThreadPoolExecutor(max_workers=n_jobs) as executor:
            futures = [executor.submit(process_folder, subfolder) for subfolder in path.iterdir() if subfolder.is_dir()]
            results = [future.result() for future in as_completed(futures)]

            # Check if all subfolders were empty and deleted
            if all(results) and not any(path.glob("*")):
                path.rmdir()
                return True
    else:
        return process_folder(path)

    return False
