from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.main import app, process_task
from process_dcm.utils import get_md5
from tests.conftest import remove_ansi_codes


def test_main_defaults(runner):
    result = runner.invoke(app, ["input_dir"])
    assert result.exit_code == 0
    assert "Processed" in result.output


def test_main_version(runner):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"Process DCM Version: {__version__}" in result.output


@pytest.mark.parametrize(
    "input_dir, image_format, output_dir, n_jobs, additional_args, expected_output",
    [
        ("path/to/dcm", "jpg", "/tmp/exported_data", 2, [], "Processed"),
        ("path/to/dcm", "jpg", "/tmp/exported_data", 2, ["--quiet"], ""),
    ],
)
def test_main_with_options(input_dir, image_format, output_dir, n_jobs, additional_args, expected_output, runner):
    args = [
        input_dir,
        "--image_format",
        image_format,
        "--output_dir",
        output_dir,
        "--n_jobs",
        str(n_jobs),
        "--overwrite",
        *additional_args,
    ]

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert expected_output in result.output


def test_cli_without_args(runner):
    result = runner.invoke(app)
    assert result.exit_code == 2
    output = remove_ansi_codes(result.stdout)
    assert "Missing argument 'INPUT_DIR'" in output


@pytest.mark.parametrize(
    "md5, meta, keep",
    [
        (["837808d746aef8e2dd08defbdbc70818"], "0a9a930806f2784aa4e60d47b3bad6ed", "pndg"),
        (["7a355bb7e0c95155d1541c7fe0941c5e"], "fd6c5a84aca6499b0ea8b99d4e25dc92", "pnDg"),
        (["2319181ecfc33d35b01dcec65ab2c568"], "35fe295648681e3521da8dddaed63705", ""),
    ],
)
def test_main(md5, meta, keep, janitor, runner):
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    janitor.append("patient_2_study_id_2.csv")
    # Create a temporary directory using the tempfile module
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = [
            "tests/example-dcms",
            "--output_dir",
            str(output_dir),
            "--n_jobs",
            "1",
            "--overwrite",
            "--keep",
            keep,
        ]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        of = sorted(glob(f"{output_dir}/**/*"))
        assert len(of) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json") == meta
        assert get_md5(of) in md5


def test_main_dummy(janitor, runner):
    janitor.append("dummy_dir")
    args = ["tests/dummy_ex", "-o", "dummy_dir", "-k", "p"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    of = sorted(glob("dummy_dir/**/*"))
    assert len(of) == 2
    assert get_md5("dummy_dir/dummy_ex/metadata.json") == "1cabdb14492a0e62d80cfc0a3fe304e9"
    assert get_md5(of) in "b19bbfca59584915295f67e9259880d7"


def test_main_mapping(janitor, runner):
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    janitor.append("patient_2_study_id_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = [
            "tests/example-dcms",
            "--output_dir",
            str(output_dir),
            "--n_jobs",
            "1",
            "--keep",
            "p",
            "--mapping",
            "tests/map.csv",
            "-r",
        ]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "WARN: '--relative' x 'absolute --output_dir'" in result.output
        of = sorted(glob(f"{output_dir}/**/*"))
        assert len(of) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json") == "261826ad2e067e9adb7143bb6c053dbc"
        assert get_md5(of) in "6ff8e2fe69c5fbe86f81f44f74496cab"


def test_main_abort(runner):
    # Expect the typer.Abort exception to be raised
    args = ["tests/example-dcms", "--keep", "p", "--mapping", RESERVED_CSV]
    result = runner.invoke(app, args)

    # Strip ANSI codes from the output
    output = remove_ansi_codes(result.stdout)

    assert result.exit_code == 1
    assert output == "Can't use reserved CSV file name: patient_2_study_id.csv\nAborted.\n"


# skip this test for CI
def test_main_mapping_example_dir(janitor, runner):
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    janitor.append("patient_2_study_id_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = ["tests/example_dir", "-o", str(output_dir), "-j", "2", "-w", "-k", "nDg", "-m", "tests/map.csv"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        of = sorted(glob(f"{output_dir}/**/**/*"))
        assert len(of) == 262
        assert get_md5(output_dir / "012345/20180724_L/metadata.json") == "1b46961177c80daf69e7dea7379fcc31"
        assert get_md5(output_dir / "3517807670/20180926_R/metadata.json") == "bbf5c47f9fb28f46b4cc1bf08c311593"


# skip this test for CI
def test_main_mapping_example_dir_relative(janitor, runner):
    input_dir = "tests/example_dir"
    janitor.append("patient_2_study_id.csv")
    janitor.append("patient_2_study_id_1.csv")
    janitor.append("patient_2_study_id_2.csv")
    args = ["tests/example_dir", "-o", "dummy", "-j", "2", "-r", "-k", "nDg", "-m", "tests/map.csv"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    of = sorted(glob(f"{input_dir}/**/**/dummy/*"))
    path1 = Path(input_dir) / "012345"
    path2 = Path(input_dir) / "3517807670"
    janitor.append(path1)
    janitor.append(path2)
    assert len(of) == 262
    assert get_md5(path1 / "20180724_L/dummy/metadata.json") == "1b46961177c80daf69e7dea7379fcc31"
    assert get_md5(path2 / "20180926_R/dummy/metadata.json") == "bbf5c47f9fb28f46b4cc1bf08c311593"


def test_process_task():
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        task_data = ("tests/example-dcms/", str(output_dir))
        image_format = "png"
        overwrite = True
        verbose = False
        keep = ""
        mapping = ""
        group = False
        result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group)
        assert result == ("0780320450", "bbff7a25-d32c-4192-9330-0bb01d49f746")
