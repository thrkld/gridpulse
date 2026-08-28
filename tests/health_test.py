import pytest

from gridpulse import health


@pytest.fixture
def meminfo(tmp_path):
    """Write a fake /proc/meminfo so the test never reads the real host."""

    def write(body):
        path = tmp_path / "meminfo"
        path.write_text(body)
        return str(path)

    return write


def test_reads_the_swap_total(meminfo):
    """The figure comes from the SwapTotal line, not the first number in the file."""
    path = meminfo("MemTotal:  862348 kB\nMemFree: 91234 kB\nSwapTotal: 2097148 kB\n")
    assert health.check_swap(path) == 2097148


def test_absent_swap_raises(meminfo):
    """Swap reading zero is the August outage, so it has to fail rather than pass quietly."""
    path = meminfo("MemTotal:  862348 kB\nSwapTotal:       0 kB\n")
    with pytest.raises(RuntimeError, match="swap is not active"):
        health.check_swap(path)


def test_missing_meminfo_raises(meminfo):
    """Not being able to read the file is unknown, and unknown must not look like healthy."""
    with pytest.raises(RuntimeError, match="not found"):
        health.check_swap("/nonexistent/meminfo")


def test_meminfo_without_a_swap_line_raises(meminfo):
    """A file we can read but cannot find the field in is still an unanswered question."""
    path = meminfo("MemTotal:  862348 kB\nMemFree: 91234 kB\n")
    with pytest.raises(RuntimeError, match="no SwapTotal"):
        health.check_swap(path)
