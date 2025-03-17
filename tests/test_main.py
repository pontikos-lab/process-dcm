import shutil
from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from typer.testing import CliRunner

from process_dcm import __version__
from process_dcm.const import RESERVED_CSV
from process_dcm.main import app
from process_dcm.utils import get_md5
from tests.conftest import bottom, remove_ansi_codes


def test_main_defaults(runner: CliRunner) -> None:
    result = runner.invoke(app, ["input_dir"])
    output = remove_ansi_codes(result.stdout)
    assert result.exit_code == 1
    assert "Input directory 'input_dir' does not exist\nAborted.\n" in output


@pytest.mark.skip(reason="for debug")
def test_main_debug(runner: CliRunner) -> None:
    result = runner.invoke(app, ["/Users/alan/Downloads/CE/Alan_Dicom_Exported", "-q", "-k", "pndg"])
    assert result.exit_code == 0
    # assert "Processed" in result.output


def test_main_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"Process DCM Version: {__version__}" in result.output


@pytest.mark.parametrize(
    "input_dir, image_format, output_dir, additional_args, expected_output",
    [
        ("path/to/dcm", "jpg", "/tmp/exported_data", [], "Aborted"),
    ],
)
def test_main_with_options(
    input_dir: str,
    image_format: str,
    output_dir: str,
    additional_args: list[str],
    expected_output: str,
    runner: CliRunner,
) -> None:
    args = [
        input_dir,
        "--image_format",
        image_format,
        "--output_dir",
        output_dir,
        "--overwrite",
        *additional_args,
    ]

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert expected_output in result.output


def test_cli_without_args(runner: CliRunner) -> None:
    result = runner.invoke(app)
    assert result.exit_code == 2
    output = remove_ansi_codes(result.stdout)
    assert "Missing argument 'INPUT_DIR'" in output


@pytest.mark.parametrize(
    "md5, meta, keep, key",
    [
        (
            ["5ba37cc43233db423394cf98c81d5fbc", "a726b59587ca4ea1a478802e3ee9235c"],
            "f6d93f3763ede47885ecbcefc6ff2153",
            "pndg",
            "bbff7a25-d32c-4192-9330-0bb01d49f746",
        ),
        (
            ["5ba37cc43233db423394cf98c81d5fbc", "a726b59587ca4ea1a478802e3ee9235c"],
            "0f5b4e1006a22dab2d85beafb07d21f5",
            "pnDg",
            "bbff7a25-d32c-4192-9330-0bb01d49f746",
        ),
        (
            ["5ba37cc43233db423394cf98c81d5fbc", "a726b59587ca4ea1a478802e3ee9235c"],
            "b6097b6a5f2ec1fe727737efb2c09674",
            "",
            "0780320450",
        ),
    ],
)
def test_main(md5: list[str], meta: str, keep: str, key: str, janitor: list[str], runner: CliRunner) -> None:
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
            "--overwrite",
            "--keep",
            keep,
        ]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        tof = sorted(glob(f"{output_dir}/**/*"))
        of = [x for x in tof if "metadata.json" not in x]
        assert len(tof) == 51
        assert (
            get_md5(
                output_dir / f"{key}_20150624_144600_2e3f4b_OD_OCT" / "metadata.json",
                bottom,
            )
            == meta
        )
        assert get_md5(of) in md5


def test_main_group(janitor: list[str], runner: CliRunner) -> None:
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = ["tests", "-o", str(output_dir), "-k", "gD", "-g"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "Found DICOMDIR file at tests/DICOMDIR" in result.output
        tof = sorted(output_dir.rglob("*.*"))
        of = sorted(output_dir.rglob("*.png"))
        assert len(tof) == 51
        assert (
            get_md5(output_dir / "0780320450_20150624_144600_2e3f4b_OD_OCT" / "metadata.json", bottom)
            == "6b97085eaf90b6cc2f99680a7343bb3a"
        )
        assert get_md5(of) in ["a726b59587ca4ea1a478802e3ee9235c"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "0780320450_20150624_144600_2e3f4b_OD_OCT' already exists with metadata" in result.output


def test_main_dummy(janitor: list[str], runner: CliRunner) -> None:
    janitor.append("dummy_dir")
    args = ["tests/dummy_ex", "-o", "dummy_dir", "-k", "p"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    tof = sorted(glob("dummy_dir/**/*"))
    of = [x for x in tof if "metadata.json" not in x]
    assert len(tof) == 3
    assert (
        get_md5(Path("dummy_dir") / "123456__340692_OU_U" / "metadata.json", bottom)
        == "c7d343cf486526d737f7fea8dd1ada55"
    )
    assert get_md5(of) in ["fb7c7e0fe4e7d3e89e0daae479d013c4"]


def test_main_abort(runner: CliRunner) -> None:
    # Expect the typer.Abort exception to be raised
    args = ["tests/example-dcms", "--keep", "p", "--mapping", RESERVED_CSV]
    result = runner.invoke(app, args)

    # Strip ANSI codes from the output
    output = remove_ansi_codes(result.stdout)

    assert result.exit_code == 1
    assert output == "'--mapping' x '--keep p': are mutually excluding options\nAborted.\n"


def test_main_abort_reserved_csv(runner: CliRunner) -> None:
    # Expect the typer.Abort exception to be raised
    args = ["tests/example-dcms", "--mapping", RESERVED_CSV]
    result = runner.invoke(app, args)

    # Strip ANSI codes from the output
    output = remove_ansi_codes(result.stdout)

    assert result.exit_code == 1
    assert output == f"Can't use reserved CSV file name: {RESERVED_CSV}\nAborted.\n"


def test_main_no_dicom(runner: CliRunner, tmp_path: Path) -> None:
    args = [tmp_path.as_posix()]
    result = runner.invoke(app, args)

    # Strip ANSI codes from the output
    output = remove_ansi_codes(result.stdout)

    assert result.exit_code == 0
    assert output == f"\nNo DICOM files found in {tmp_path}\n"


# skip this test for CI
def test_main_mapping_example_dir(janitor: list[str], runner: CliRunner) -> None:
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        args = ["tests/example_dir", "-o", str(output_dir), "-j", "2", "-w", "-k", "nDg", "-m", "tests/map.csv"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        of = sorted([p for p in output_dir.rglob("*") if p.is_file()])
        assert len(of) == 264
        assert (
            get_md5(output_dir / "2910892726_20180724_161901_477b53_OS_OCT" / "metadata.json", bottom)
            == "e157247cb35354f99e57d5106de5e1ea"
        )
        assert (
            get_md5(output_dir / "3517807670_20180926_140517_600177_OD_OCT" / "metadata.json", bottom)
            == "e5e15b903b7606df5664bb2951423faf"
        )
        args = ["tests/example_dir", "-o", str(output_dir), "-k", "nDg", "-m", "tests/map.csv"]
        result = runner.invoke(app, args)
        shutil.rmtree(output_dir / "3517807670_20180926_140517_600177_OD_OCT")
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "\nProcessed 1 DICOM folders\nSkipped 3 DICOM folders\n" in result.output


def test_main_optos_fa(janitor: list[str], runner: CliRunner) -> None:
    janitor.append("study_2_patient.csv")
    janitor.append("study_2_patient_1.csv")
    janitor.append("study_2_patient_2.csv")
    with TemporaryDirectory() as tmpdirname:
        output_dir = Path(tmpdirname)
        input_dir = "tests/optos_fa/"
        args = [input_dir, "-o", str(tmpdirname), "-k", "pndg"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        of = sorted(glob(f"{output_dir}/**/*"))
        assert len(of) == 2
        assert (
            get_md5(output_dir / "1840002001__44fd1d_OD_OPTOS_FA" / "metadata.json", bottom)
            == "ee1d9d5be87c805f5a501b3b82dde86b"
        )
