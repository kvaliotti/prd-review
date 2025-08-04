import time
from typing import Callable
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from app.core.logging import get_logger

logger = get_logger("monitoring")

# Create a custom registry for better control
REGISTRY = CollectorRegistry()

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently in progress',
    registry=REGISTRY
)

# Application Metrics
active_users = Gauge(
    'active_users_total',
    'Number of active users',
    registry=REGISTRY
)

total_chats = Gauge(
    'total_chats',
    'Total number of chats in the system',
    registry=REGISTRY
)

total_messages = Gauge(
    'total_messages',
    'Total number of messages in the system',
    registry=REGISTRY
)

llm_requests_total = Counter(
    'llm_requests_total',
    'Total requests to LLM',
    ['status'],
    registry=REGISTRY
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    registry=REGISTRY
)

# Database Metrics
database_connections = Gauge(
    'database_connections_active',
    'Active database connections',
    registry=REGISTRY
)

database_queries_total = Counter(
    'database_queries_total',
    'Total database queries',
    ['operation'],
    registry=REGISTRY
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    registry=REGISTRY
)

# Authentication Metrics
auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['status'],
    registry=REGISTRY
)

# Error Metrics
errors_total = Counter(
    'errors_total',
    'Total application errors',
    ['error_type', 'endpoint'],
    registry=REGISTRY
)


class MetricsMiddleware:
    """Middleware to collect HTTP metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope["method"]
        path = scope["path"]
        
        # Skip metrics collection for metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return
        
        # Normalize path for metrics (remove IDs, etc.)
        normalized_path = self._normalize_path(path)
        
        # Start tracking
        start_time = time.time()
        http_requests_in_progress.inc()
        
        status_code = 500  # Default to error
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            errors_total.labels(
                error_type=type(e).__name__,
                endpoint=normalized_path
            ).inc()
            logger.error("Request error", path=path, error=str(e))
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            http_requests_in_progress.dec()
            
            http_requests_total.labels(
                method=method,
                endpoint=normalized_path,
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=normalized_path
            ).observe(duration)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics to avoid cardinality explosion"""
        # Replace chat IDs with placeholder
        import re
        path = re.sub(r'/chats/\d+', '/chats/{id}', path)
        path = re.sub(r'/users/\d+', '/users/{id}', path)
        return path


def record_llm_request(duration: float, success: bool = True):
    """Record LLM request metrics"""
    status = "success" if success else "error"
    llm_requests_total.labels(status=status).inc()
    llm_request_duration_seconds.observe(duration)


def record_auth_attempt(success: bool = True):
    """Record authentication attempt"""
    status = "success" if success else "failure"
    auth_attempts_total.labels(status=status).inc()


def record_database_operation(operation: str, duration: float):
    """Record database operation metrics"""
    database_queries_total.labels(operation=operation).inc()
    database_query_duration_seconds.labels(operation=operation).observe(duration)


def update_application_metrics(user_count: int, chat_count: int, message_count: int):
    """Update application-level metrics"""
    active_users.set(user_count)
    total_chats.set(chat_count)
    total_messages.set(message_count)


async def get_metrics() -> Response:
    """Endpoint to expose Prometheus metrics"""
    try:
        metrics_data = generate_latest(REGISTRY)
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error("Failed to generate metrics", error=str(e))
        return Response(
            content="Error generating metrics",
            status_code=500
        )


class DatabaseMetricsCollector:
    """Collect database-related metrics"""
    
    @staticmethod
    async def collect_from_db(db_session):
        """Collect metrics from database"""
        try:
            # Count users, chats, messages
            from app.models import User, Chat, Message
            
            user_count = db_session.query(User).count()
            chat_count = db_session.query(Chat).count()
            message_count = db_session.query(Message).count()
            
            update_application_metrics(user_count, chat_count, message_count)
            
        except Exception as e:
            logger.error("Failed to collect database metrics", error=str(e))


# Health check metrics
health_check_status = Gauge(
    'health_check_status',
    'Health check status (1 = healthy, 0 = unhealthy)',
    ['service'],
    registry=REGISTRY
)

def update_health_status(service: str, is_healthy: bool):
    """Update health status for a service"""
    health_check_status.labels(service=service).set(1 if is_healthy else 0) 