"""utils module."""

import hashlib
import json
import os
import shutil
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from natsort import natsorted
from PIL import Image
from pydicom.dataset import FileDataset
from pydicom.filereader import dcmread

from process_dcm.const import ImageModality

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
                    print("WARN: empty photo_locations")
                    meta["contents"].append({"photo_locations": []})

    return meta


def process_dcm_meta(dcm_objs: list[FileDataset], output_dir: str) -> None:
    """Extract and save metadata from a list of DICOM files to a JSON file.

    Args:
        dcm_objs (list[FileDataset]): A list of FileDataset objects representing the DICOM files.
        output_dir (str): The directory where the metadata JSON file will be saved.

    Returns:
        None
    """
    meta_file = os.path.join(output_dir, "metadata.json")
    metadata: dict = defaultdict(dict)
    metadata["patient"] = {}
    metadata["exam"] = {}
    metadata["series"] = {}
    metadata["images"]["images"] = []
    metadata["parser_version"] = [1, 5, 2]
    metadata["py_dcm_version"] = [0, 1, 0]
    for dcm_obj in dcm_objs:
        metadata["patient"]["patient_key"] = dcm_obj.get("PatientID")
        metadata["patient"]["first_name"] = dcm_obj.get("PatientName.name_prefix")
        metadata["patient"]["last_name"] = dcm_obj.get("PatientName.name_suffix")
        metadata["patient"]["date_of_birth"] = do_date(dcm_obj.get("PatientBirthDate"), "%Y%m%d", "%Y-%m-%d")
        metadata["patient"]["gender"] = dcm_obj.get("PatientSex")
        metadata["patient"]["source_id"] = dcm_obj.get("StudyInstanceUID")

        metadata["exam"]["manufacturer"] = dcm_obj.get("Manufacturer")
        metadata["exam"]["scan_datetime"] = do_date(
            dcm_obj.get("AcquisitionDateTime"), "%Y%m%d%H%M%S.%f", "%Y-%m-%d %H:%M:%S"
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


def process_dcm(
    input_dir: str | Path,
    image_format: str = "png",
    output_dir: str = "exported_data",
    overwrite: bool = False,
    verbose: bool = False,
) -> None:
    """Process DICOM files from the input directory and save images in the specified format.

    Args:
        input_dir (str|Path): Path to the directory containing DICOM files.
        output_dir (str): Path to the directory where images will be saved. Defaults to "__input_dir__/exported_data".
                          Use full path if wanting to save to a specific folder.
        image_format (str): The format in which to save the images. Defaults to "png".
        overwrite (bool): Whether to overwrite existing files in the output directory. Defaults to False.
        verbose (bool, optional): Whether to print out progress information during processing. Defaults to True.
    """
    output_dir = set_output_dir(input_dir, output_dir)

    if overwrite:
        shutil.rmtree(output_dir, ignore_errors=True)
    else:
        if os.path.exists(output_dir) and verbose:
            print(f"Output directory '{output_dir}' already exists.")

    # Load both DICOM files in the input directory
    dcm_objs = [dcmread(os.path.join(input_dir, f)) for f in os.listdir(input_dir) if f.endswith(".dcm")]
    dcm_objs.sort(key=lambda x: x.Modality)
    dcms = []
    # using AccessionNumber to emulate group_id
    for dcm in dcm_objs:
        # update modality
        if not update_modality(dcm):
            continue  # Ignore any other modalities

        dcm.AccessionNumber = 0
        # process images
        arr = dcm.pixel_array
        os.makedirs(output_dir, exist_ok=True)

        if not dcm.get("NumberOfFrames"):
            dcm.NumberOfFrames = 1

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

        dcms.append(dcm)

    process_dcm_meta(dcms, output_dir)


def find_dcm_subfolders(root_folder: str) -> list[str]:
    """Finds all unique subfolders within the root folder that contain at least one DCM file.

    Args:
        root_folder: The path to the root folder to search.

    Returns:
        A naturally sorted list of unique full paths of subfolders containing DCM files.
    """
    unique_subfolders = set()

    for dirpath, _, filenames in os.walk(root_folder):
        if any(filename.lower().endswith(".dcm") for filename in filenames):
            unique_subfolders.add(dirpath)  # Store full path

    return natsorted(list(unique_subfolders))


def get_md5(file_path: Path | str | list[str]) -> str:
    """Calculate the MD5 checksum of a file or list of files."""
    md5_hash = hashlib.md5()
    if isinstance(file_path, str) or isinstance(file_path, Path):
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                md5_hash.update(chunk)
    elif isinstance(file_path, list):
        for fname in file_path:
            with open(fname, "rb") as f:
                while chunk := f.read(4096):
                    md5_hash.update(chunk)
    return md5_hash.hexdigest()
