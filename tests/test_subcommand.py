from redclay.shell_command import subcommand, run_from_argv


def test_run_right_command():
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
