import argparse
import importlib
import inspect

from redclay.funcutil import cached


class ArgumentParser(argparse.ArgumentParser):
    @cached
    def subparsers(self):
        return self.add_subparsers()

    def add_subcommand(self, spec):
        subcommand = getattr(spec, "redclay_subcommand", None) or self.load_subcommand(
            spec
        )
        subcommand.add_to_parser(self)

    def load_subcommand(self, import_path):
        module_name, _, runner_name = import_path.rpartition(".")
        module = importlib.import_module(module_name)
        runner = getattr(module, runner_name)
        return runner.redclay_subcommand


class Subcommand:
    def __init__(self, run, arguments):
        self.run = run
        self.arguments = arguments

    def get_name(self):
        return self.run.__name__

    def add_to_parser(self, parser):
        subparser = parser.subparsers.add_parser(self.get_name())
        subparser.set_defaults(subcommand=self)
        for args, kwargs in self.arguments:
            subparser.add_argument(*args, **kwargs)

    def run_with_args(self, args):
        forward_args = self.args_to_forward(args)
        self.run(**forward_args)

    def args_to_forward(self, args):
        sig = inspect.signature(self.run)
        if self.uses_kwargs(sig):
            return vars(args)
        else:
            names = self.keyword_parameters(sig)
            forward_args = self.dict_subset(vars(args), names)
            return forward_args

    def uses_kwargs(self, signature):
        return any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values())

    def keyword_parameters(self, signature):
        return [
            param.name
            for param in signature.parameters.values()
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
        ]

    def dict_subset(self, d, names):
        return {name: value for (name, value) in d.items() if name in names}


def argument(*args, **kwargs):
    return args, kwargs


def subcommand(*arguments):
    def wrap(f):
        subcommand = Subcommand(f, arguments)
        f.redclay_subcommand = subcommand
        return f

    return wrap


def run_from_argv(subcommands, *args):
    parser = ArgumentParser(description="a Georgia MUD")
    for subcommand in subcommands:
        parser.add_subcommand(subcommand)

    args = parser.parse_args(*args)
    args.subcommand.run_with_args(args)
