import argparse
import contextlib
import importlib
import inspect

from redclay.dbsession import managed_session
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
        context = self.make_exec_context()
        context.update(**vars(args))
        forward_args = self.args_to_forward(context)
        with self.enter_context_managers(forward_args) as run_context:
            self.run(**run_context)

    def args_to_forward(self, arg_dict):
        sig = inspect.signature(self.run)
        if self.uses_kwargs(sig):
            return arg_dict
        else:
            names = self.keyword_parameters(sig)
            return self.dict_subset(arg_dict, names)

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

    def make_exec_context(self):
        return {"session": managed_session()}

    @contextlib.contextmanager
    def enter_context_managers(self, arg_dict):
        with contextlib.ExitStack() as stack:
            yield {
                name: self.enter_if_context_manager(val, stack)
                for (name, val) in arg_dict.items()
            }

    def enter_if_context_manager(self, val, stack):
        return stack.enter_context(val) if hasattr(val, "__enter__") else val


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
