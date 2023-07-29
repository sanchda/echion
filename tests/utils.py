import sys
import typing as t
from pathlib import Path
from shutil import which
from subprocess import PIPE
from subprocess import CalledProcessError
from subprocess import CompletedProcess
from subprocess import Popen
from subprocess import run
from tempfile import TemporaryDirectory
from time import sleep

import pytest
from austin.stats import AustinFileReader
from austin.stats import MetricType
from austin.stats import Sample


PY = sys.version_info[:2]


class Data:
    def __init__(self, file: Path) -> None:
        self.source = file
        self.samples = []

        with AustinFileReader(str(file)) as afr:
            for s in afr:
                self.samples.append(Sample.parse(s, MetricType.TIME)[0])

            self.metadata = afr.metadata


class DataSummary:
    def __init__(self, data: Data) -> None:
        self.data = data
        self.metadata = data.metadata

        self.threads: t.Dict[str, dict] = {}
        self.total_metric = 0
        self.nsamples = 0

        for sample in data.samples:
            self.nsamples += 1
            frames = sample.frames
            v = sample.metric.value

            self.total_metric += v
            stacks = self.threads.setdefault(sample.thread, {})

            stack = tuple((f.function, f.line) for f in frames)
            stacks[stack] = stacks.get(stack, 0) + v

            fstack = tuple(f.function for f in frames)
            stacks[fstack] = stacks.get(fstack, 0) + v

    @property
    def nthreads(self):
        return len(self.threads)

    def query(self, thread_name, frames):
        stacks = self.threads[thread_name]
        for stack in stacks:
            for i in range(0, len(stack) - len(frames) + 1):
                if stack[i : i + len(frames)] == frames:
                    return stacks[stack]
        return None

    def assert_stack(self, thread, frames, predicate):
        try:
            stack = self.threads[thread][frames]
        except KeyError:
            if thread not in self.threads:
                raise AssertionError(
                    f"Expected thread {thread}, found {self.threads.keys()}"
                ) from None
            raise AssertionError(
                f"Expected stack {frames}, found {self.threads[thread].keys()}"
            ) from None

        assert predicate(stack), stack


def run_echion(*args: str) -> CompletedProcess:
    try:
        return run(
            [
                "echion",
                *args,
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except CalledProcessError as e:
        print(e.stdout.decode())
        print(e.stderr.decode())
        raise


def run_target(target: Path, *args: str) -> t.Tuple[CompletedProcess, t.Optional[Data]]:
    with TemporaryDirectory(prefix="echion") as td:
        output_file = Path(td) / "output.echion"

        result = run_echion(
            "-o",
            str(output_file),
            *args,
            sys.executable,
            "-m",
            f"tests.{target}",
        )

        return result, (Data(output_file) if output_file.is_file() else None)


def run_with_signal(target: Path, signal: int, delay: float, *args: str) -> Popen:
    p = Popen(
        [
            t.cast(str, which("echion")),
            *args,
            sys.executable,
            "-m",
            f"tests.{target}",
        ],
        stdout=PIPE,
        stderr=PIPE,
    )

    sleep(delay)

    p.send_signal(signal)

    p.wait()

    return p


stealth = pytest.mark.parametrize("stealth", [tuple(), ("--stealth",)])
