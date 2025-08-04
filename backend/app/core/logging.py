import logging
import logging.config
import sys
from typing import Any, Dict

import structlog
from structlog.types import Processor


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application"""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Configure structlog
    timestamper = structlog.processors.TimeStamper(fmt="ISO")
    shared_processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if sys.stderr.isatty():
        # Pretty printing for development
        shared_processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON for production
        shared_processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


class LoggingMiddleware:
    """Middleware to log HTTP requests and responses"""
    
    def __init__(self, app, logger_name: str = "api"):
        self.app = app
        self.logger = get_logger(logger_name)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request_logger = self.logger.bind(
            method=scope["method"],
            path=scope["path"],
            client=scope.get("client", [None, None])[0]
        )
        
        request_logger.info("Request started")
        
        # Wrap send to capture response status
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                request_logger.bind(
                    status_code=message["status"]
                ).info("Request completed")
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            request_logger.bind(
                error=str(exc),
                error_type=type(exc).__name__
            ).error("Request failed")
            raise


# Application loggers
security_logger = get_logger("security")
chat_logger = get_logger("chat")
llm_logger = get_logger("llm")
db_logger = get_logger("database")
auth_logger = get_logger("auth") 