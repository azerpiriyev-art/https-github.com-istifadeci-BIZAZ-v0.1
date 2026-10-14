"""Delete in-app notifications older than the approved 180-day retention window.

Run daily as the BIZAZ system administrator using the backend virtual environment.
The database transaction commits atomically; only notification rows are deleted.
"""
from sqlalchemy import text

from app.database import engine


def main() -> int:
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "DELETE FROM notifications "
                "WHERE created_at < now() - INTERVAL '180 days'"
            )
        )
        deleted_count = result.rowcount or 0

    print(f"Notification retention purge complete; deleted={deleted_count}")
    return deleted_count


if __name__ == "__main__":
    main()
