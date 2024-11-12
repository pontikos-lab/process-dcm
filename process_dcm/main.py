"""app to procces DCM files."""

import csv
import os
from collections.abc import Iterable
from functools import partial
from multiprocessing.pool import Pool

import typer
from rich.progress import track

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.utils import delete_if_empty, find_dicom_folders_with_base, process_and_save_csv, process_dcm

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


def print_version(value: bool) -> None:
    """Print the version of the app."""
    if value:
        typer.secho(f"Process DCM Version: {__version__}", fg="blue")
        raise typer.Exit()


def process_task(
    task: tuple[str, str],
    image_format: str,
    overwrite: bool,
    quiet: bool,
    keep: str,
    mapping: str,
    group: bool,
    tol: int,
) -> tuple[str, str]:
    """Process task."""
    subfolder, out_dir = task
    return process_dcm(
        input_dir=subfolder,
        output_dir=out_dir,
        image_format=image_format,
        overwrite=overwrite,
        quiet=quiet,
        keep=keep,
        mapping=mapping,
        group=group,
        tol=tol,
    )


@app.command()
def main(
    input_dir: str = typer.Argument(..., help="Input directory containing subfolders with DICOM files."),
    image_format: str = typer.Option(
        "png", "-f", "--image_format", help="Image format for extracted images (png, jpg, webp)."
    ),
    output_dir: str = typer.Option(
        "exported_data",
        "-o",
        "--output_dir",
        help="Output directory for extracted images and metadata.",
    ),
    group: bool = typer.Option(
        False, "-g", "--group", help="Re-group DICOM files in a given folder by AcquisitionDateTime."
    ),
    tol: int = typer.Option(
        2, "-t", "--tol", help="Tolerance in seconds for grouping DICOM files by AcquisitionDateTime."
    ),
    relative: bool = typer.Option(
        False, "-r", "--relative", help="Save extracted data in folders relative to _input_dir_."
    ),
    n_jobs: int = typer.Option(1, "-j", "--n_jobs", help="Number of parallel jobs."),
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
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Silence verbosity."),
    version: bool = typer.Option(
        None,
        "-V",
        "--version",
        callback=print_version,
        is_eager=True,
        help="Prints app version.",
    ),
) -> None:
    """Process DICOM files in subfolders, extract images and metadata using parallel processing.

    Version: 0.4.4
    """
    task_processor = partial(
        process_task,
        image_format=image_format,
        overwrite=overwrite,
        quiet=quiet,
        keep=keep,
        mapping=mapping,
        group=group,
        tol=tol,
    )

    if mapping == RESERVED_CSV:
        typer.secho(f"Can't use reserved CSV file name: {RESERVED_CSV}", fg="red")
        raise typer.Abort()
    if "p" in keep and mapping:
        typer.secho(
            f"WARN:'--mapping' x '--keep p': file '{mapping}' it will overwrite patient_id anyway",
            fg=typer.colors.BRIGHT_YELLOW,
        )

    len_sf, base_dir, subfolders = find_dicom_folders_with_base(os.path.abspath(input_dir))
    output_dirs = []

    if os.path.isabs(output_dir):
        if relative:
            typer.secho(
                "WARN: '--relative' x 'absolute --output_dir' are incompatible, absolute 'output_dir' takes precedence",
                fg=typer.colors.BRIGHT_YELLOW,
            )
            relative = False
        output_dirs = [x.replace(base_dir, output_dir) for x in subfolders]
    else:
        if relative:
            output_dirs = [os.path.join(x, output_dir) for x in subfolders]
        else:
            output_dir = os.path.abspath(output_dir)
            output_dirs = [x.replace(os.path.abspath(base_dir), output_dir) for x in subfolders]

    tasks = list(zip(subfolders, output_dirs))

    def track_tasks(pool: Pool, tasks: list[tuple[str, str]], quiet: bool, total: int) -> Iterable[tuple[str, str]]:
        if quiet:
            return pool.imap(task_processor, tasks)
        else:
            return track(pool.imap(task_processor, tasks), total=total, description="Processing DICOM files")

    with Pool(n_jobs) as pool:
        results = list(track_tasks(pool, tasks, quiet, total=len_sf))

    unique_sorted_results = sorted(set(results))  # (study_id, patient_id)
    dict_res = dict(unique_sorted_results)

    delete_if_empty(output_dir, n_jobs=n_jobs)

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
        process_and_save_csv(unique_sorted_results, RESERVED_CSV, quiet=quiet)

    if not quiet:
        typer.secho(
            f"Processed {len(results)} DICOM folders\nSaved to '{os.path.abspath(output_dir)}'",
            fg=typer.colors.BRIGHT_WHITE,
        )


def cli() -> None:
    """Run the app."""
    app()  # no cov
