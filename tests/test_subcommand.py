from unittest.mock import patch
from redclay.shell_command import subcommand, run_from_argv


@patch("redclay.shell_command.get_session_maker")
@patch("redclay.shell_command.managed_session")
def test_run_right_command(mock_get_session_maker, mock_managed_session):
    test_value = {}

    @subcommand()
    def subcommand_one():
        test_value["command"] = "subcommand_one"

    @subcommand()
    def subcommand_two():
        test_value["command"] = "subcommand_two"

    subcommands = [subcommand_one, subcommand_two]
    run_from_argv(subcommands, ["subcommand_two"])

    assert test_value["command"] == "subcommand_two"
