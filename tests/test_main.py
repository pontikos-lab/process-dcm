import tempfile
from glob import glob
from pathlib import Path

import pytest
import typer

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.main import app, cli, main, process_task
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


@pytest.mark.parametrize(
    "md5, meta, keep",
    [
        (["837808d746aef8e2dd08defbdbc70818"], "0a9a930806f2784aa4e60d47b3bad6ed", "pndg"),
        (["7a355bb7e0c95155d1541c7fe0941c5e"], "fd6c5a84aca6499b0ea8b99d4e25dc92", "pnDg"),
        (["2319181ecfc33d35b01dcec65ab2c568"], "35fe295648681e3521da8dddaed63705", ""),
    ],
)
def test_main(md5, meta, keep, janitor):
    input_dir = "tests/example-dcms"
    image_format = "png"
    n_jobs = 1
    overwrite = False
    verbose = True
    mapping = ""
    janitor.append("patient_2_study_id.csv")
    # Create a temporary directory using the tempfile module
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        main(
            input_dir=input_dir,
            image_format=image_format,
            output_dir=str(output_dir),
            n_jobs=n_jobs,
            overwrite=overwrite,
            verbose=verbose,
            keep=keep,
            mapping=mapping,
        )
        of = sorted(glob(f"{output_dir}/**/*"))
        assert len(of) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json") == meta
        assert get_md5(of) in md5


def test_main_mapping(janitor):
    input_dir = "tests/example-dcms"
    image_format = "png"
    n_jobs = 1
    overwrite = False
    verbose = True
    janitor.append("patient_2_study_id.csv")
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        main(
            input_dir=input_dir,
            image_format=image_format,
            output_dir=str(output_dir),
            n_jobs=n_jobs,
            overwrite=overwrite,
            verbose=verbose,
            keep="p",
            mapping="tests/map.csv",
        )
        of = sorted(glob(f"{output_dir}/**/*"))
        assert len(of) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json") == "261826ad2e067e9adb7143bb6c053dbc"
        assert get_md5(of) in "6ff8e2fe69c5fbe86f81f44f74496cab"


def test_main_abort():
    input_dir = "tests/example-dcms"
    image_format = "png"
    n_jobs = 1
    overwrite = False
    verbose = True
    # Expect the typer.Abort exception to be raised
    with pytest.raises(typer.Abort):
        main(
            input_dir=input_dir,
            image_format=image_format,
            output_dir="/tmp",
            n_jobs=n_jobs,
            overwrite=overwrite,
            verbose=verbose,
            keep="p",
            mapping=RESERVED_CSV,
        )


# skip this test for CI
def test_main_mapping_example_dir(janitor):
    input_dir = "tests/example_dir"
    image_format = "png"
    n_jobs = 2
    overwrite = True
    verbose = True
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        main(
            input_dir=input_dir,
            image_format=image_format,
            output_dir=str(output_dir),
            n_jobs=n_jobs,
            overwrite=overwrite,
            verbose=verbose,
            keep="nDg",
            mapping="tests/map.csv",
        )
        of = sorted(glob(f"{output_dir}/**/**/*"))
        assert len(of) == 262
        assert get_md5(output_dir / "010-0001/20180724_L/metadata.json") == "1b46961177c80daf69e7dea7379fcc31"
        assert get_md5(output_dir / "010-0002/20180926_R/metadata.json") == "bbf5c47f9fb28f46b4cc1bf08c311593"


# skip this test for CI
def test_main_mapping_example_dir_relative(janitor):
    input_dir = "tests/example_dir"
    image_format = "png"
    n_jobs = 2
    overwrite = False
    verbose = True
    relative = True
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    main(
        input_dir=input_dir,
        image_format=image_format,
        output_dir="dummy",
        n_jobs=n_jobs,
        overwrite=overwrite,
        verbose=verbose,
        keep="nDg",
        mapping="tests/map.csv",
        relative=relative,
    )
    of = sorted(glob(f"{input_dir}/**/**/dummy/*"))
    path1 = Path(input_dir) / "010-0001/20180724_L/dummy"
    path2 = Path(input_dir) / "010-0002/20180926_R/dummy"
    janitor.append(path1)
    janitor.append(path2)
    assert len(of) == 262
    assert get_md5(path1 / "metadata.json") == "1b46961177c80daf69e7dea7379fcc31"
    assert get_md5(path2 / "metadata.json") == "bbf5c47f9fb28f46b4cc1bf08c311593"


def test_process_task():
    with tempfile.TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        task_data = ("tests/example-dcms/", str(output_dir))
        image_format = "png"
        overwrite = True
        verbose = False
        keep = ""
        mapping = ""
        result = process_task(task_data, image_format, overwrite, verbose, keep, mapping)
        assert result == ("0780320450", "bbff7a25-d32c-4192-9330-0bb01d49f746")
