"""Readable database failures without SQL statements or bound evidence parameters."""
from sqlalchemy.exc import SQLAlchemyError

DATABASE_FAILURE_MESSAGE = (
    "A database error prevented the report from being saved. Please retry the investigation."
)


def public_failure_message(error: Exception | str) -> str:
    message = str(error)
    if isinstance(error, SQLAlchemyError) or "[SQL:" in message or message.startswith("(psycopg."):
        return DATABASE_FAILURE_MESSAGE
    return message
