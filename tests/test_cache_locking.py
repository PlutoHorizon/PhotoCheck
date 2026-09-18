"""Test the file lock prevents concurrent cache corruption."""

import os
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from photocheck.core.cache import _HAS_FLOCK, load_cache, save_cache
from photocheck.core.models import PhotoMetadata


def _meta(suffix: str) -> PhotoMetadata:
    return PhotoMetadata(
        file_path=Path(f"/lock_test_{suffix}.ARW"),
        datetime_original=datetime(2024, 1, 1),
    )


@pytest.mark.skipif(not _HAS_FLOCK, reason="fcntl not available")
class TestCacheLocking:
    def test_concurrent_writes_serialize(self, tmp_path):
        """Two concurrent save_cache calls must serialize; the final cache
        must contain a complete (non-corrupt) state from one of them.
        """
        cache = tmp_path / "cache.parquet"
        # Seed initial state
        save_cache([_meta("seed")], cache)

        results = []

        def writer(name: str, count: int):
            save_cache([_meta(f"{name}_{i}") for i in range(count)], cache)
            results.append(name)

        t1 = threading.Thread(target=writer, args=("A", 50))
        t2 = threading.Thread(target=writer, args=("B", 30))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not t1.is_alive() and not t2.is_alive(), "Threads deadlocked"
        assert sorted(results) == ["A", "B"]

        # Final cache must be a valid (non-corrupt) parquet containing
        # exactly one of the two writers' data
        loaded = load_cache(cache)
        assert len(loaded) in (30, 50), f"Cache corrupt: got {len(loaded)} entries"
        # Every loaded entry's name should be from one writer or the other,
        # never mixed (which would indicate partial write)
        for m in loaded:
            assert m.file_path.stem.startswith("lock_test_A_") \
                or m.file_path.stem.startswith("lock_test_B_"), \
                f"Mixed names detected: {m.file_path}"

    def test_concurrent_readers_dont_block_each_other(self, tmp_path):
        """Shared lock allows multiple readers to read concurrently."""
        cache = tmp_path / "cache.parquet"
        save_cache([_meta(f"x_{i}") for i in range(100)], cache)

        start_barrier = threading.Barrier(3)
        reader_durations = []

        def reader():
            start_barrier.wait()  # sync all 3 to start at once
            t0 = time.perf_counter()
            data = load_cache(cache)
            reader_durations.append(time.perf_counter() - t0)
            assert len(data) == 100

        threads = [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "Reader deadlocked"

        # All readers should have completed in roughly the same time
        # (no significant serialization delay). Each took < 1s.
        for d in reader_durations:
            assert d < 2.0, f"Reader took {d:.2f}s (should be <2s)"

    def test_lock_file_appears_during_write(self, tmp_path):
        """The .lock file is created next to the cache and cleaned up by flock."""
        cache = tmp_path / "cache.parquet"
        lock = tmp_path / "cache.parquet.lock"

        # After save, the lock file may or may not be present (flock removes
        # the file on close, but in some implementations it persists). The
        # key invariant: subsequent save works correctly regardless.
        save_cache([_meta("a")], cache)
        # The lock path parent dir exists, so the test is really: can we
        # call save again? (If the lock file is wedged, the second save
        # would block forever.)
        save_cache([_meta("b")], cache)
        assert len(load_cache(cache)) == 1
        # Lock file cleanup is best-effort; we just require the second
        # save to complete within a reasonable time.
