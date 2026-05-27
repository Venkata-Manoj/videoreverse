from utils.cli import parse_cli_args


def test_parse_cli_args_supports_no_transcribe() -> None:
    options = parse_cli_args(["sample.mp4", "--no-transcribe"])
    assert options["video_path"] == "sample.mp4"
    assert options["no_transcribe"] is True


def test_parse_cli_args_defaults_no_transcribe_false() -> None:
    options = parse_cli_args(["sample.mp4"])
    assert options["no_transcribe"] is False


def test_print_help_uses_src_main() -> None:
    from utils.cli import print_help
    import io

    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        print_help()
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "python -m src.main" in output
    assert "python -m src.pipeline" not in output


def test_print_help_has_max_retries_default_3() -> None:
    from utils.cli import print_help
    import io

    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        print_help()
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "--max-retries" in output
    assert "default: 3" in output
