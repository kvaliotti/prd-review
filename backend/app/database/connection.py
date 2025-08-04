import time
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.core.config import settings
from app.core.logging import db_logger
from app.core.monitoring import record_database_operation, database_connections


# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=10,  # Number of connections to maintain in the pool
    max_overflow=20,  # Additional connections beyond pool_size
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Set to True for SQL query logging in development
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Database monitoring events
@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    """Event handler for new database connections"""
    database_connections.inc()
    db_logger.debug("New database connection established")


@event.listens_for(engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Event handler for connection checkout from pool"""
    db_logger.debug("Database connection checked out from pool")


@event.listens_for(engine, "checkin")
def on_checkin(dbapi_connection, connection_record):
    """Event handler for connection checkin to pool"""
    db_logger.debug("Database connection returned to pool")


@event.listens_for(engine, "invalidate")
def on_invalidate(dbapi_connection, connection_record, exception):
    """Event handler for connection invalidation"""
    database_connections.dec()
    db_logger.warning("Database connection invalidated", error=str(exception) if exception else None)


def get_db():
    """Dependency to get database session with monitoring"""
    start_time = time.time()
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db_logger.error("Database session error", error=str(e))
        db.rollback()
        raise
    finally:
        duration = time.time() - start_time
        record_database_operation("session", duration)
        db.close()


@asynccontextmanager
async def get_db_context():
    """Async context manager for database sessions"""
    start_time = time.time()
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db_logger.error("Database context error", error=str(e))
        db.rollback()
        raise
    finally:
        duration = time.time() - start_time
        record_database_operation("context", duration)
        db.close()


def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        db_logger.info("Database tables created successfully")
    except Exception as e:
        db_logger.error("Failed to create database tables", error=str(e))
        raise


def check_database_health() -> bool:
    """Check database connectivity and health"""
    try:
        start_time = time.time()
        db = SessionLocal()
        
        # Simple query to test connection
        db.execute(text("SELECT 1"))
        db.close()
        
        duration = time.time() - start_time
        record_database_operation("health_check", duration)
        
        db_logger.debug("Database health check passed", duration=duration)
        return True
        
    except Exception as e:
        db_logger.error("Database health check failed", error=str(e))
        return False


def get_db_stats():
    """Get database connection pool statistics"""
    try:
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    except Exception as e:
        db_logger.error("Failed to get database stats", error=str(e))
        return None


class DatabaseSession:
    """Database session context manager with monitoring"""
    
    def __init__(self, operation_name: str = "unknown"):
        self.operation_name = operation_name
        self.start_time = None
        self.db = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.db.rollback()
                db_logger.error(
                    "Database operation failed",
                    operation=self.operation_name,
                    error=str(exc_val) if exc_val else None
                )
            else:
                self.db.commit()
        finally:
            duration = time.time() - self.start_time
            record_database_operation(self.operation_name, duration)
            self.db.close()


# Utility functions for common operations
def execute_with_monitoring(operation_name: str, func, *args, **kwargs):
    """Execute database operation with monitoring"""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        db_logger.debug("Database operation completed", operation=operation_name)
        return result
    except Exception as e:
        db_logger.error("Database operation failed", operation=operation_name, error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        record_database_operation(operation_name, duration) 