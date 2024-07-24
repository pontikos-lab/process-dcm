"""app to procces DCM files."""

from functools import partial
from multiprocessing import Pool

import typer
from tqdm import tqdm

from process_dcm import __version__
from process_dcm.utils import find_dcm_subfolders, process_dcm

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

out_msg = """Output directory for extracted images and metadata. Defaults to: __input_dir__/exported_data\n
Use absolut path if you want to save the output in a specific location."""


def print_version(value: bool) -> None:
    """Print the version of the app."""
    if value:
        typer.echo(f"Process DCM Version: {__version__}")
        raise typer.Exit()


@app.command()
def main(
    input_dir: str = typer.Argument(..., help="Input directory containing subfolders with DICOM files."),
    image_format: str = typer.Option(
        "png", "-f", "--image_format", help="Image format for extracted images (png, jpg, webp). Defaults to: png"
    ),
    output_dir: str = typer.Option("exported_data", "-o", "--output_dir", help=out_msg),
    n_jobs: int = typer.Option(1, "-j", "--n_jobs", help="Number of parallel jobs. Defaults to: 1"),
    overwrite: bool = typer.Option(False, "-w", "--overwrite", help="Overwrite existing images if found."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output."),
    version: bool = typer.Option(
        None, "-V", "--version", callback=print_version, is_eager=True, help="Prints app version"
    ),
) -> None:
    """Process DICOM files in subfolders, extract images and metadata using parallel processing."""
    subfolders = find_dcm_subfolders(input_dir)

    # Create a partial function with fixed arguments
    process_dcm_with_args = partial(
        process_dcm, image_format=image_format, output_dir=output_dir, overwrite=overwrite, verbose=verbose
    )

    with Pool(n_jobs) as pool:
        results = list(tqdm(pool.imap(process_dcm_with_args, subfolders), total=len(subfolders)))

    print(f"Processed {len(results)} DICOM folders.")


def cli() -> None:
    """Run the app."""
    app()
