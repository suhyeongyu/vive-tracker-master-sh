"""Rate Limiter - Accurate loop rate control with drift correction"""

import time
import warnings


class RateLimiter:
    """Accurate rate limiting with drift correction.

    Uses absolute time tracking to prevent cumulative drift.
    Detects and warns when loop execution time exceeds target period.

    Simplified API: reset() before loop, sleep() in loop.
    First sleep() call after reset() initializes timing and returns immediately.
    Subsequent sleep() calls maintain target frequency with drift correction.

    Args:
        rate_hz: Target loop frequency in Hz
        precise: Use hybrid busy-wait for lower jitter (default: True)
            - True: sleep most of the time, busy-wait last 1ms for precision
            - False: pure time.sleep() (lower CPU, higher jitter)
        busy: Pure busy-wait, no sleep (default: False)
            - True: 100% CPU on this thread, immune to OS scheduler resolution
            - Overrides `precise` when True

    Example:
        limiter = RateLimiter(20.0)  # 20 Hz, precise mode
        limiter.reset()  # Always call before starting loop

        while running:
            # ... do work ...
            limiter.sleep()  # First call: init only, later: rate limiting
    """

    # Busy-wait threshold: last N seconds before target time
    BUSY_WAIT_THRESHOLD = 0.001  # 1ms

    def __init__(self, rate_hz: float, precise: bool = True, busy: bool = False):
        """Initialize rate limiter.

        Args:
            rate_hz: Target loop frequency in Hz
            precise: Use hybrid busy-wait for lower jitter (default: True)
            busy: Pure busy-wait, no sleep (default: False). Overrides `precise`.
        """
        self.rate_hz = rate_hz
        self.period = 1.0 / rate_hz
        self.precise = precise
        self.busy = busy
        self.next_time = None
        self.overrun_count = 0

    def sleep(self) -> None:
        """Sleep until next iteration time.

        First call after reset(): Initialize timing and return immediately.
        Subsequent calls: Sleep to maintain target frequency with drift correction.

        Automatically adjusts for drift and detects overruns.
        """
        if self.next_time is None:
            # First call: initialize to current time, no sleep
            self.next_time = time.perf_counter()
            return

        # Schedule next iteration (absolute time)
        self.next_time += self.period

        # Calculate sleep time
        now = time.perf_counter()
        sleep_time = self.next_time - now

        if sleep_time > 0:
            if self.busy:
                # Pure busy-wait: immune to OS scheduler resolution
                while time.perf_counter() < self.next_time:
                    pass
            elif self.precise:
                # Hybrid: sleep most, busy-wait last 1ms
                coarse_sleep = sleep_time - self.BUSY_WAIT_THRESHOLD
                if coarse_sleep > 0:
                    time.sleep(coarse_sleep)
                # Busy-wait for remaining time (precision)
                while time.perf_counter() < self.next_time:
                    pass
            else:
                # Pure sleep (lower CPU, higher jitter)
                time.sleep(sleep_time)
        elif sleep_time < -self.period:
            # Severe overrun: warn and reset timing
            self.overrun_count += 1
            delay_ms = -sleep_time * 1000
            warnings.warn(
                f"Rate limiter overrun: {delay_ms:.1f}ms late "
                f"(target: {self.period*1000:.1f}ms @ {self.rate_hz}Hz, "
                f"total overruns: {self.overrun_count})"
            )
            # Reset to current time to prevent cascade
            self.next_time = time.perf_counter()
        # else: Minor overrun (<1 period), let drift correction handle it

    def reset(self) -> None:
        """Reset state for new control loop.

        Should be called before starting a new loop.
        Clears timing state and overrun counter for clean start.
        """
        self.next_time = None
        self.overrun_count = 0

    @property
    def total_overruns(self) -> int:
        """Get total number of severe overruns detected."""
        return self.overrun_count