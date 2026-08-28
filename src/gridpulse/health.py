import os

MEMINFO = "/proc/meminfo"


def swap_total_kb(path: str = MEMINFO) -> int:
    """Read SwapTotal from /proc/meminfo, in kB."""
    with open(path) as f:
        for line in f:
            if line.startswith("SwapTotal:"):
                return int(line.split()[1])
    raise RuntimeError(f"{path} has no SwapTotal line")


def check_swap(path: str = MEMINFO) -> int:
    # Load-bearing rather than a nicety: without swap this VM cannot hold Dagster's
    # processes, and when it vanished in August the machine was unreachable for days.
    if not os.path.exists(path):
        raise RuntimeError(f"{path} not found, so swap cannot be verified")
    total = swap_total_kb(path)
    if total <= 0:
        raise RuntimeError(
            "swap is not active on this host. Dagster will run out of memory: "
            "recreate the swapfile and check the /etc/fstab entry survived."
        )
    return total
