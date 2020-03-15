import importlib

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
MODEL_MODULES = ["redclay.auth"]


def load_models(modules=None):
    if modules is None:
        modules = MODEL_MODULES
    for module_name in modules:
        importlib.import_module(module_name)
    return Base.metadata
