import argparse
import importlib


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subparsers = None

    @property
    def subparsers(self):
        if self._subparsers is None:
            self._subparsers = self.add_subparsers()
        return self._subparsers

    def add_subcommand(self, import_path):
        subcommand = self.load_subcommand(import_path)
        subparser = self.subparsers.add_parser(subcommand.get_name())
        subparser.set_defaults(subcommand=subcommand)

    def load_subcommand(self, import_path):
        module_name, _, runner_name = import_path.rpartition(".")
        module = importlib.import_module(module_name)
        runner = getattr(module, runner_name)
        return runner.redclay_subcommand


class Subcommand:
    def __init__(self, run):
        self.run = run

    def get_name(self):
        return self.run.__name__

    def run_with_args(self, args):
        # For the moment, ignore the args
        self.run()


def subcommand(*args, **kwargs):
    def wrap(f):
        subcommand = Subcommand(f, *args, **kwargs)
        f.redclay_subcommand = subcommand
        return f

    return wrap


def run_from_argv(*args):
    parser = ArgumentParser(description="a Georgia MUD")
    parser.add_subcommand("redclay.game.run_server")

    args = parser.parse_args(*args)
    args.subcommand.run_with_args(args)
