import functools


def cached(f):
    property_name = "_redclay_cached_" + f.__name__
    unset = object()

    @property
    @functools.wraps(f)
    def wrapped(obj):
        value = getattr(obj, property_name, unset)
        if value is unset:
            value = f(obj)
            setattr(obj, property_name, value)
        return value

    return wrapped
