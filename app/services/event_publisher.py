import json
import logging
from typing import Any, Dict
from datetime import datetime, timezone
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes fulfillment lifecycle events (e.g., booking confirmed, rejected,
    SLA timeout, alternate needed) over Redis Pub/Sub to be consumed by upstream
    services or event listeners.
    """

    def __init__(self, redis_url: str = settings.REDIS_URL, channel: str = settings.REDIS_EVENTS_CHANNEL):
        self.redis_url = redis_url
        self.channel = channel
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                # Normalize Celery's CERT_NONE to redis-py's none
                clean_url = self.redis_url.replace("ssl_cert_reqs=CERT_NONE", "ssl_cert_reqs=none")
                self._client = redis.Redis.from_url(clean_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Could not connect to Redis at {self.redis_url}: {e}")
                return None
        return self._client

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Publish an event payload to the configured Redis Pub/Sub channel.
        Returns True if successfully published, False otherwise.
        """
        envelope = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        serialized = json.dumps(envelope, default=str)
        try:
            cli = self.client
            if cli:
                cli.publish(self.channel, serialized)
                logger.info(f"Published event '{event_type}' to Redis channel '{self.channel}'")
                return True
            else:
                logger.warning(f"Redis client not available. Event '{event_type}' was logged but not published.")
                return False
        except Exception as e:
            logger.error(f"Failed to publish event '{event_type}' to Redis: {e}")
            return False


event_publisher = EventPublisher()
