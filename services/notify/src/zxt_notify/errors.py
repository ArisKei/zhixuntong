class NotificationError(RuntimeError):
    """A delivery failure safe to translate into the API's 503 error response."""

    def __init__(self, channel: str, message: str) -> None:
        self.channel = channel
        super().__init__(message)
