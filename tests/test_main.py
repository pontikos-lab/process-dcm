import tempfile
from glob import glob
from pathlib import Path

from process_dcm import __version__
from process_dcm.main import app, cli, main
from process_dcm.utils import get_md5


def test_main_defaults(runner):
    result = runner.invoke(app, ["input_dir"])
    assert result.exit_code == 0
    assert "Processed" in result.output


def test_main_version(runner):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"Process DCM Version: {__version__}" in result.output


def test_main_with_options(runner):
    input_dir = "path/to/dcm"
    image_format = "jpg"
    output_dir = "/tmp/exported_data"
    n_jobs = 2

    args = [
        input_dir,
        "--image_format",
        image_format,
        "--output_dir",
        output_dir,
        "--n_jobs",
        str(n_jobs),
        "--overwrite",
        "--verbose",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert "Processed" in result.output


def test_cli_without_args(capsys):
    # works with pytest CLI but not with vscode because of its wrapper args
    try:
        cli()
    except SystemExit:
        pass

    captured = capsys.readouterr()
    assert "Missing argument 'INPUT_DIR'" in captured.err


def test_main():
    input_dir = "tests/example-dcms"
    image_format = "png"
    n_jobs = 1
    overwrite = False
    verbose = True
    md5 = ["837808d746aef8e2dd08defbdbc70818"]

    # Create a temporary directory using the tempfile module
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)

        # Run your app's main function with the test inputs
        main(input_dir, image_format, str(output_dir), n_jobs, overwrite, verbose)
        of = sorted(glob(f"{output_dir}/*"))
        assert len(of) == 51
        assert get_md5(output_dir / "metadata.json") == "0a9a930806f2784aa4e60d47b3bad6ed"
        assert get_md5(of) in md5
