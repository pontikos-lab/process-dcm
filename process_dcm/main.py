"""App to process DCM files."""

import csv
import shutil
import warnings
from pathlib import Path

import typer

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.utils import delete_if_empty, process_and_save_csv, process_dcm

# Filter the specific pydicom warning
warnings.filterwarnings(
    "ignore", message=r"The value length \(\d+\) exceeds the maximum length of \d+ allowed for VR CS\."
)

TOL = 2.0

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


def print_version(value: bool) -> None:
    """Print the version of the app."""
    if value:
        typer.secho(f"Process DCM Version: {__version__}", fg="blue")
        raise typer.Exit()


@app.command()
def main(
    input_dir: Path = typer.Argument(..., help="Input directory containing subfolders with DICOM files."),
    image_format: str = typer.Option(
        "png", "-f", "--image_format", help="Image format for extracted images (png, jpg, webp)."
    ),
    output_dir: Path = typer.Option(
        "exported_data",
        "-o",
        "--output_dir",
        help="Output directory for extracted images and metadata.",
    ),
    group: bool = typer.Option(
        False, "-g", "--group", help="Re-group DICOM files in a given folder by AcquisitionDateTime."
    ),
    tol: float | None = typer.Option(
        None,
        "-t",
        "--tol",
        help="Tolerance in seconds for grouping DICOM files by AcquisitionDateTime. Only used when --group is set.",
    ),
    n_jobs: int = typer.Option(1, "-j", "--n_jobs", help="Number of parallel jobs."),
    mapping: str = typer.Option(
        "",
        "-m",
        "--mapping",
        help=f"""Path to CSV containing patient_id to study_id mapping. If not provided and patient_id is anonymised, a '{RESERVED_CSV}' file will be generated.""",  # noqa: E501
    ),
    keep: str = typer.Option(
        "",
        "-k",
        "--keep",
        help="Keep the specified fields (p: patient_key, n: names, d: date_of_birth, D: year-only DOB, g: gender)",
    ),
    overwrite: bool = typer.Option(False, "-w", "--overwrite", help="Overwrite existing images if found."),
    reset: bool = typer.Option(False, "-r", "--reset", help="Reset the output directory if it exists."),
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
    """Process DICOM files in subfolders, extract images and metadata.

    Version: 0.7.0
    """
    keep_patient_key = "p" in keep
    if not keep_patient_key:
        if mapping == RESERVED_CSV:
            typer.secho(f"Can't use reserved CSV file name: {RESERVED_CSV}", fg="red")
            raise typer.Abort()
    elif mapping:
        typer.secho("'--mapping' x '--keep p': are mutually excluding options", fg=typer.colors.BRIGHT_YELLOW)
        raise typer.Abort()

    if not input_dir.exists():
        typer.secho(f"Input directory '{input_dir}' does not exist", fg="red")
        raise typer.Abort()

    if group:
        if tol is None:
            tol = TOL  # Default value when grouping is enabled
    elif tol is not None:
        typer.secho("'--tol' option can only be used when '--group' is set.", fg="red")
        raise typer.Abort()

    if reset:
        for dcm_folder in output_dir.glob("**/*.DCM"):
            if dcm_folder.is_dir():
                shutil.rmtree(dcm_folder)

    tol = TOL if tol is None else tol

    processed, skipped, results = process_dcm(
        input_dir=input_dir,
        output_dir=output_dir,
        image_format=image_format,
        overwrite=overwrite,
        quiet=quiet,
        keep=keep,
        mapping=mapping,
        time_group=group,
        tol=tol,
        n_jobs=n_jobs,
    )

    total = processed + skipped

    if not total:
        typer.secho(f"\nNo DICOM files found in {input_dir}", fg="yellow")
        raise typer.Exit()

    delete_if_empty(output_dir)

    unique_sorted_results = sorted([x for x in set(results) if x != ("", "")])  # (study_id, patient_id)
    dict_res = dict(unique_sorted_results)

    if not keep_patient_key:
        save_csv = True
        if mapping:
            save_csv = False
            with open(mapping) as file:
                reader = csv.reader(file)
                mapping_study_ids = set(row[1] for row in reader)

            missing_study_ids = set(result[0] for result in unique_sorted_results) - mapping_study_ids

            for study_id in missing_study_ids:
                save_csv = True
                typer.secho(
                    f"Missing map in {mapping}: {dict_res[study_id]} -> {study_id} (<- new hash created)", fg="yellow"
                )
        if save_csv:
            process_and_save_csv(unique_sorted_results, RESERVED_CSV, quiet=quiet)

    if not quiet:
        if processed and not skipped:
            msg = f"Processed {processed} DICOM folders\nSaved to '{output_dir.resolve()}'"
        elif skipped and not processed:
            msg = f"Skipped {skipped} DICOM folders in folder '{output_dir.resolve()}'"
        elif processed and skipped:
            msg = f"Processed {processed} DICOM folders\nSkipped {skipped} DICOM folders\nSee '{output_dir.resolve()}'"
        typer.secho(msg, fg=typer.colors.BRIGHT_WHITE)


def cli() -> None:
    """Run the app."""
    app()  # no cov
