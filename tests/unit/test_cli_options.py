from utils.cli import parse_cli_args


def test_parse_cli_args_supports_no_transcribe() -> None:
    options = parse_cli_args(["sample.mp4", "--no-transcribe"])
    assert options["video_path"] == "sample.mp4"
    assert options["no_transcribe"] is True


def test_parse_cli_args_defaults_no_transcribe_false() -> None:
    options = parse_cli_args(["sample.mp4"])
    assert options["no_transcribe"] is False
