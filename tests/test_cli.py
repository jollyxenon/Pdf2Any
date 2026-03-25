import pytest
from ui.cli_parser import get_parser

def test_cli_parser_valid():
    parser = get_parser()
    args = parser.parse_args(["-i", "test1.pdf", "test2.pdf", "-o", "output_dir", "-f", "epub", "md", "--network", "online"])
    assert args.input == ["test1.pdf", "test2.pdf"]
    assert args.output == "output_dir"
    assert args.format == ["epub", "md"]
    assert args.network == "online"

def test_cli_parser_missing_required():
    parser = get_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-i", "test1.pdf"]) # missing output
