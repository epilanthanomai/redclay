import pytest

from redclay.textutil import LineBuffer

@pytest.fixture
def line_buffer():
    return LineBuffer()


def test_buffer_initially_empty(line_buffer):
    assert not line_buffer.has_line()
    assert line_buffer.pop() is None


def test_buffer_incomplete_line(line_buffer):
    line_buffer.append('abc')
    assert not line_buffer.has_line()
    assert line_buffer.pop() is None


def test_buffer_one_line(line_buffer):
    line_buffer.append('abc\n')
    assert line_buffer.has_line()
    assert line_buffer.pop() == 'abc\n'

    assert not line_buffer.has_line()
    assert line_buffer.pop() is None


def test_buffer_one_line_plus(line_buffer):
    line_buffer.append('abc\ndef')
    assert line_buffer.has_line()
    assert line_buffer.pop() == 'abc\n'

    assert not line_buffer.has_line()
    assert line_buffer.pop() is None


def test_buffer_multiple_lines(line_buffer):
    line_buffer.append('abc\ndef\n')
    assert line_buffer.has_line()
    assert line_buffer.pop() == 'abc\n'

    assert line_buffer.has_line()
    assert line_buffer.pop() == 'def\n'

    assert not line_buffer.has_line()
    assert line_buffer.pop() is None


def test_buffer_multiple_appends(line_buffer):
    line_buffer.append('a')
    assert not line_buffer.has_line()
    line_buffer.append('b')
    assert not line_buffer.has_line()
    line_buffer.append('\n')
    assert line_buffer.has_line()
    assert line_buffer.pop() == 'ab\n'

    line_buffer.append('c')
    assert not line_buffer.has_line()
    line_buffer.append('d')
    assert not line_buffer.has_line()
    line_buffer.append('\n')
    assert line_buffer.has_line()
    assert line_buffer.pop() == 'cd\n'


def test_buffer_complex(line_buffer):
    line_buffer.append('abc\nd')
    assert line_buffer.pop() == 'abc\n'
    line_buffer.append('ef\n\ngh')
    assert line_buffer.pop() == 'def\n'
    assert line_buffer.pop() == '\n'
    assert not line_buffer.has_line()
