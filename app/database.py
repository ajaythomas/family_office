from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
"""
autocommit=False: This is the default and recommended setting. It ensures all operations happen within a transaction. You must explicitly call session.commit() to save changes or session.rollback() to discard them.
autoflush=False: Disables "automatic" flushing. Normally, SQLAlchemy sends pending changes to the database right before you issue a query so the results are accurate. With this set to False, you must manually call session.flush() if you need the database to process changes (like generating an ID) before the final commit.

This "strict" configuration is popular because it prevents "magic" behavior that can lead to bugs in complex applications
Explicit Transactions: You decide exactly when a "unit of work" starts and ends.
Performance: By disabling autoflush, you prevent the session from sending unnecessary intermediate SQL commands to the database every time you run a query().Safety: It forces you to be intentional about data persistence, making it harder to accidentally save partial or incorrect data
"""
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal() # 1. Setup: Create the session
    try:
        """
        yield keyword is used within a dependency function to ensure a database session is opened before a request and automatically closed after the request is finished. Manages the lifecycle of a session.
        Scoped Sessions: It ensures each web request gets its own fresh session that is destroyed when the request is finished
        """
        yield db        # 2. Handoff: Give the session to the route/function
    finally:
        db.close()      # 3. Cleanup: Close connection after the work is done
