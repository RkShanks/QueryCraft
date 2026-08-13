"""Application lifecycle state used by operational readiness probes."""


class ReadinessState:
    """Track whether startup completed and shutdown has begun."""

    def __init__(self) -> None:
        self._startup_complete = False
        self._shutdown_started = False

    @property
    def accepts_traffic(self) -> bool:
        return self._startup_complete and not self._shutdown_started

    def begin_startup(self) -> None:
        self._startup_complete = False
        self._shutdown_started = False

    def complete_startup(self) -> None:
        self._startup_complete = True

    def begin_shutdown(self) -> None:
        self._shutdown_started = True
