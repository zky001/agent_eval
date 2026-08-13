from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp, matching how DateTime columns are stored in SQLite.

    ``datetime.utcnow()`` is deprecated since Python 3.12; this keeps a single
    replacement point without changing the stored representation.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
