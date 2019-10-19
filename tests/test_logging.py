from redclay.logging import logging_context, get_logging_context


def test_logging_context_initially_empty():
    assert get_logging_context() == {}


def test_logging_context_adds_fields():
    with logging_context(foo=1, bar=2):
        assert get_logging_context() == {"foo": 1, "bar": 2}
    assert get_logging_context() == {}


def test_nested_logging_context_shadows_fields():
    with logging_context(foo=1, bar=2):
        with logging_context(bar=5, baz=9):
            assert get_logging_context() == {"foo": 1, "bar": 5, "baz": 9}
        assert get_logging_context() == {"foo": 1, "bar": 2}
    assert get_logging_context() == {}
