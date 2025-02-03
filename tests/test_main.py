from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.main import app, process_task
from process_dcm.utils import get_md5
from tests.conftest import bottom, remove_ansi_codes


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
        (["a726b59587ca4ea1a478802e3ee9235c"], "27e4fa04ad730718b2509af36743c995", "pndg"),
        (["a726b59587ca4ea1a478802e3ee9235c"], "3a15fdd18a67b3d4ce7be6164f58f073", "pnDg"),
        (["a726b59587ca4ea1a478802e3ee9235c"], "ba5973bc8dd8e15aa6bef95bcd248fbf", ""),
    ],
)
def test_main(md5, meta, keep, janitor, runner):
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
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
        tof = sorted(glob(f"{output_dir}/**/*"))
        of = [x for x in tof if "metadata.json" not in x]
        assert len(tof) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json", bottom) == meta
        assert get_md5(of) in md5


def test_main_group(janitor, runner):
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = ["tests/example-dcms", "-o", str(output_dir), "-j", "1", "-k", "gD", "-g"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        tof = sorted(output_dir.rglob("*.*"))
        of = sorted(output_dir.rglob("*.png"))
        assert len(tof) == 51
        assert get_md5(output_dir / "example-dcms/group_0/metadata.json", bottom) == "5387538e2f018288154ec2e98d4d29b1"
        assert get_md5(of) in ["a726b59587ca4ea1a478802e3ee9235c"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "example-dcms/group_0' already exists with metadata" in result.output


def test_main_dummy(janitor, runner):
    janitor.append("dummy_dir")
    args = ["tests/dummy_ex", "-o", "dummy_dir", "-k", "p"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    tof = sorted(glob("dummy_dir/**/*"))
    of = [x for x in tof if "metadata.json" not in x]
    assert len(tof) == 3
    assert get_md5("dummy_dir/dummy_ex/metadata.json", bottom) == "0693469a3fcf388d89627eb212ace2bc"
    assert get_md5(of) in ["fb7c7e0fe4e7d3e89e0daae479d013c4"]


def test_main_mapping(janitor, runner):
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
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
        tof = sorted(glob(f"{output_dir}/**/*"))
        of = [x for x in tof if "metadata.json" not in x]
        assert len(tof) == 51
        assert get_md5(output_dir / "example-dcms/metadata.json", bottom) == "450e2e40d321a24219c1c9ec15b2c80e"
        assert get_md5(of) in ["a726b59587ca4ea1a478802e3ee9235c"]


def test_main_abort(runner):
    # Expect the typer.Abort exception to be raised
    args = ["tests/example-dcms", "--keep", "p", "--mapping", RESERVED_CSV]
    result = runner.invoke(app, args)

    # Strip ANSI codes from the output
    output = remove_ansi_codes(result.stdout)

    assert result.exit_code == 1
    assert output == "Can't use reserved CSV file name: study_2_patient.csv\nAborted.\n"


# skip this test for CI
def test_main_mapping_example_dir(janitor, runner):
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = ["tests/example_dir", "-o", str(output_dir), "-j", "2", "-w", "-k", "nDg", "-m", "tests/map.csv"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        of = sorted(glob(f"{output_dir}/**/**/*"))
        assert len(of) == 262
        assert get_md5(output_dir / "012345/20180724_L/metadata.json", bottom) == "93fff12758d6c0f9098e7fd5e8c8304e"
        assert get_md5(output_dir / "3517807670/20180926_R/metadata.json", bottom) == "b9ff35a765db6b1eaeac4253c93a6044"


# skip this test for CI
def test_main_mapping_example_dir_relative(janitor, runner):
    input_dir = "tests/example_dir"
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    args = ["tests/example_dir", "-o", "dummy", "-j", "2", "-r", "-k", "nDg", "-m", "tests/map.csv"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    of = sorted(glob(f"{input_dir}/**/**/dummy/*"))
    path1 = Path(input_dir) / "012345"
    path2 = Path(input_dir) / "3517807670"
    janitor.append(path1)
    janitor.append(path2)
    assert len(of) == 262
    assert get_md5(path1 / "20180724_L/dummy/metadata.json", bottom) == "93fff12758d6c0f9098e7fd5e8c8304e"
    assert get_md5(path2 / "20180926_R/dummy/metadata.json", bottom) == "b9ff35a765db6b1eaeac4253c93a6044"


def test_process_task():
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        task_data = ("tests/example-dcms/", str(output_dir))
        image_format = "png"
        overwrite = True
        verbose = False
        keep = ""
        mapping = ""
        group = True
        tol = 2
        result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group, tol)
        assert result == ("0780320450", "bbff7a25-d32c-4192-9330-0bb01d49f746")


def test_process_task_optos():
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        task_data = ("tests/example-optos/", str(output_dir))
        image_format = "png"
        overwrite = True
        verbose = True
        keep = ""
        mapping = ""
        group = True
        tol = 2
        result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group, tol)
        assert result == ("0570586923", "BEH002")


def test_process_acquisition_datetime():
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        task_data = ("tests/cataract/", str(output_dir))
        image_format = "png"
        overwrite = True
        verbose = True
        keep = ""
        mapping = ""
        group = True
        tol = 2
        result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group, tol)
        assert result == ("0558756784", "20241113-093410")


# def test_process_many():
#     with TemporaryDirectory() as tmpdirname:
#         output_dir = Path(tmpdirname)
#         task_data = ("20220823_R/", str(output_dir))
#         image_format = "png"
#         overwrite = True
#         verbose = True
#         keep = ""
#         mapping = ""
#         group = False
#         tol = 2
#         result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group, tol)
#         assert result == ("0558756784", "20241113-093410")


# def test_process_taskL():
#     with TemporaryDirectory() as tmpdirname:
#         output_dir = Path(tmpdirname)
#         task_data = ("E2G_1472/2140433/20230315_L/", str(output_dir))
#         image_format = "png"
#         overwrite = True
#         verbose = True
#         keep = ""
#         mapping = ""
#         group = True
#         result = process_task(task_data, image_format, overwrite, verbose, keep, mapping, group)
#         assert result == ("4290892805", "2140433")
