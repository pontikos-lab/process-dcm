"""app to procces DCM files."""

import csv
import os
from functools import partial
from multiprocessing import Pool

import typer
from tqdm import tqdm

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.utils import find_dicom_folders_with_base, process_and_save_csv, process_dcm

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


def print_version(value: bool) -> None:
    """Print the version of the app."""
    if value:
        typer.secho(f"Process DCM Version: {__version__}", fg="blue")
        raise typer.Exit()


def process_task(
    task: tuple[str, str], image_format: str, overwrite: bool, verbose: bool, keep: str, mapping: str
) -> tuple[str, str]:
    """Process task."""
    subfolder, out_dir = task
    return process_dcm(
        input_dir=subfolder,
        output_dir=out_dir,
        image_format=image_format,
        overwrite=overwrite,
        verbose=verbose,
        keep=keep,
        mapping=mapping,
    )


@app.command()
def main(
    input_dir: str = typer.Argument(..., help="Input directory containing subfolders with DICOM files."),
    image_format: str = typer.Option(
        "png", "-f", "--image_format", help="Image format for extracted images (png, jpg, webp). Defaults to: png"
    ),
    output_dir: str = typer.Option(
        "exported_data",
        "-o",
        "--output_dir",
        help="Output directory for extracted images and metadata. Defaults to: exported_data",
    ),
    relative: bool = typer.Option(
        False, "-r", "--relative", help="Save extracted data in folders relative to _input_dir_."
    ),
    n_jobs: int = typer.Option(1, "-j", "--n_jobs", help="Number of parallel jobs. Defaults to: 1"),
    mapping: str = typer.Option(
        "",
        "-m",
        "--mapping",
        help=f"Path to CSV containing patient_id to study_id mapping. If not provided and patient_id is not anonymised, a '{RESERVED_CSV}' file will be generated",  # noqa: E501
    ),
    keep: str = typer.Option(
        "",
        "-k",
        "--keep",
        help="Keep the specified fields (p: patient_key, n: names, d: date_of_birth, D: year-only DOB, g: gender)",
    ),
    overwrite: bool = typer.Option(False, "-w", "--overwrite", help="Overwrite existing images if found."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output."),
    version: bool = typer.Option(
        None, "-V", "--version", callback=print_version, is_eager=True, help="Prints app version"
    ),
) -> None:
    """Process DICOM files in subfolders, extract images and metadata using parallel processing."""
    if mapping == RESERVED_CSV:
        typer.secho(f"Can't use reserved CSV file name: {RESERVED_CSV}", fg="red")
        raise typer.Abort()
    if "p" in keep and mapping:
        typer.secho(f"WARN:'--mapping' x '--keep p': File , {mapping} it will overwrite patient_id anyway", fg="yellow")

    len_sf, base_dir, subfolders = find_dicom_folders_with_base(input_dir)
    output_dirs = []

    if os.path.isabs(output_dir):
        if relative:
            typer.secho(
                "WARN: '--relative' x 'absolute --output_dir' are incompatible, absolute 'output_dir' takes precedence",
                fg="yellow",
            )
            relative = False
        output_dir = os.path.abspath(output_dir)
        output_dirs = [x.replace(base_dir, output_dir) for x in subfolders]
    elif relative:
        output_dirs = [os.path.join(x, output_dir) for x in subfolders]

    tasks = list(zip(subfolders, output_dirs))

    with Pool(n_jobs) as pool:
        results = list(
            tqdm(
                pool.imap(
                    partial(
                        process_task,
                        image_format=image_format,
                        overwrite=overwrite,
                        verbose=verbose,
                        keep=keep,
                        mapping=mapping,
                    ),
                    tasks,
                ),
                total=len_sf,
            )
        )

    unique_sorted_results = sorted(set(results))  # (study_id, patient_id)
    dict_res = dict(unique_sorted_results)

    if mapping:
        with open(mapping) as file:
            reader = csv.reader(file)
            mapping_study_ids = set(row[1] for row in reader)

        missing_study_ids = set(result[0] for result in unique_sorted_results) - mapping_study_ids

        for study_id in missing_study_ids:
            typer.secho(
                f"Missing map in {mapping}: {dict_res[study_id]} -> {study_id} (<- new hash created)", fg="yellow"
            )
    else:
        process_and_save_csv(unique_sorted_results, RESERVED_CSV)

    print(f"Processed {len(results)} DICOM folders.")


def cli() -> None:
    """Run the app."""
    app()
