"""
Redis client for distributed resilience coordination.

Supports:
- Leader election with TTL-based expiry
- State publishing to cluster
- Vote collection for consensus
- Cluster state aggregation
"""

import redis.asyncio as aioredis
import asyncio
import json
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for distributed coordination."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL (default: localhost:6379)
        """
        self.redis_url = redis_url
        self.redis = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish connection to Redis.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.redis = await aioredis.from_url(self.redis_url)
            # Test connection
            await self.redis.ping()
            self.connected = True
            logger.info(f"Connected to Redis: {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                await self.redis.close()
                self.connected = False
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    async def leader_election(self, instance_id: str, ttl: int = 30) -> bool:
        """Attempt leader election with TTL-based expiry.
        
        Uses SET with NX (only if not exists) to ensure only one leader.
        TTL ensures automatic failover on instance failure.
        
        Args:
            instance_id: Unique instance identifier
            ttl: Time to live for leadership (seconds, default: 30)
            
        Returns:
            True if elected leader, False if leader already exists
        """
        if not self.connected:
            logger.warning("Redis not connected, cannot perform leader election")
            return False

        try:
            result = await self.redis.set(
                "astra:resilience:leader",
                instance_id,
                nx=True,  # Only set if key doesn't exist
                ex=ttl,   # Set expiry
            )
            if result:
                logger.info(f"Instance {instance_id} elected as leader (TTL: {ttl}s)")
            else:
                logger.debug(f"Instance {instance_id} did not win leader election")
            return result
        except Exception as e:
            logger.error(f"Leader election failed: {e}")
            return False

    async def renew_leadership(self, instance_id: str, ttl: int = 30) -> bool:
        """Renew leadership TTL if currently leader.
        
        Uses atomic Lua script to prevent TOCTOU race condition.
        Script checks if key value equals instance_id, then atomically sets TTL.
        
        Args:
            instance_id: Current instance ID (must match leader)
            ttl: New TTL (seconds)
            
        Returns:
            True if renewed, False if not leader
        """
        if not self.connected:
            return False

        try:
            # Lua script for atomic check-and-expire operation
            # Returns 1 (true) if value matches and TTL was set
            # Returns 0 (false) if value doesn't match
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                redis.call("EXPIRE", KEYS[1], ARGV[2])
                return 1
            else
                return 0
            end
            """
            
            # Execute script atomically
            result = await self.redis.eval(
                lua_script,
                1,  # number of keys
                "astra:resilience:leader",  # KEYS[1]
                instance_id,  # ARGV[1]
                ttl,  # ARGV[2]
            )
            
            renewed = bool(result)
            if renewed:
                logger.debug(f"Leadership renewed for {instance_id} (TTL: {ttl}s)")
            else:
                logger.debug(f"Leadership renewal failed for {instance_id} (not current leader)")
            
            return renewed
        except Exception as e:
            logger.error(f"Failed to renew leadership: {e}")
            return False

    async def get_leader(self) -> Optional[str]:
        """Get current leader instance ID.
        
        Returns:
            Instance ID of current leader, or None if no leader
        """
        if not self.connected:
            return None

        try:
            leader = await self.redis.get("astra:resilience:leader")
            return leader.decode() if leader else None
        except Exception as e:
            logger.error(f"Failed to get leader: {e}")
            return None

    async def publish_state(self, channel: str, state: Dict[str, Any]) -> int:
        """Publish resilience state to cluster via pub/sub.
        
        Args:
            channel: Channel name (e.g., "astra:resilience:state")
            state: State dictionary to publish
            
        Returns:
            Number of subscribers that received the message
        """
        if not self.connected:
            logger.warning("Redis not connected, cannot publish state")
            return 0

        try:
            subscribers = await self.redis.publish(channel, json.dumps(state))
            logger.debug(f"Published state to {subscribers} subscribers on {channel}")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish state: {e}")
            return 0

    async def register_vote(
        self, instance_id: str, vote: Dict[str, Any], ttl: int = 30
    ) -> bool:
        """Register instance vote in cluster consensus.
        
        Args:
            instance_id: Instance ID voting
            vote: Vote data (e.g., circuit breaker state, fallback mode)
            ttl: Vote expiry time (seconds)
            
        Returns:
            True if registered, False otherwise
        """
        if not self.connected:
            return False

        try:
            key = f"astra:resilience:vote:{instance_id}"
            vote["timestamp"] = datetime.utcnow().isoformat()
            await self.redis.set(key, json.dumps(vote), ex=ttl)
            logger.debug(f"Registered vote from {instance_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register vote: {e}")
            return False

    async def get_cluster_votes(self, prefix: str = "astra:resilience:vote") -> Dict[str, Any]:
        """Retrieve all instance votes for consensus.
        
        Args:
            prefix: Key prefix for votes (default: astra:resilience:vote)
            
        Returns:
            Dict mapping instance_id to vote data
        """
        if not self.connected:
            return {}

        try:
            # Get all vote keys
            keys = await self.redis.keys(f"{prefix}:*")
            if not keys:
                logger.debug("No votes found in cluster")
                return {}

            # Batch get all values
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            values = await pipe.execute()

            # Parse votes
            votes = {}
            for key, value in zip(keys, values):
                if value:
                    try:
                        instance_id = key.decode().split(":")[-1]
                        votes[instance_id] = json.loads(value)
                    except (json.JSONDecodeError, IndexError) as e:
                        logger.warning(f"Failed to parse vote from {key}: {e}")

            logger.debug(f"Retrieved {len(votes)} votes from cluster")
            return votes
        except Exception as e:
            logger.error(f"Failed to get cluster votes: {e}")
            return {}

    async def get_instance_health(self, instance_id: str) -> Optional[Dict]:
        """Get last known health state of instance.
        
        Args:
            instance_id: Instance ID to query
            
        Returns:
            Health state dict or None if not found
        """
        if not self.connected:
            return None

        try:
            key = f"astra:health:{instance_id}"
            health = await self.redis.get(key)
            if health:
                return json.loads(health)
            return None
        except Exception as e:
            logger.error(f"Failed to get health for {instance_id}: {e}")
            return None

    async def publish_health(
        self, instance_id: str, health: Dict[str, Any], ttl: int = 60
    ) -> bool:
        """Publish instance health state to cluster.
        
        Args:
            instance_id: Instance ID publishing health
            health: Health state dictionary
            ttl: Health data TTL (seconds)
            
        Returns:
            True if published, False otherwise
        """
        if not self.connected:
            return False

        try:
            key = f"astra:health:{instance_id}"
            health["timestamp"] = datetime.utcnow().isoformat()
            await self.redis.set(key, json.dumps(health), ex=ttl)
            logger.debug(f"Published health for {instance_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish health: {e}")
            return False

    async def get_all_instance_health(self) -> Dict[str, Dict]:
        """Get health states of all instances.
        
        Returns:
            Dict mapping instance_id to health state
        """
        if not self.connected:
            return {}

        try:
            keys = await self.redis.keys("astra:health:*")
            if not keys:
                return {}

            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            values = await pipe.execute()

            health_states = {}
            for key, value in zip(keys, values):
                if value:
                    try:
                        instance_id = key.decode().split(":")[-1]
                        health_states[instance_id] = json.loads(value)
                    except (json.JSONDecodeError, IndexError) as e:
                        logger.warning(f"Failed to parse health from {key}: {e}")

            logger.debug(f"Retrieved health for {len(health_states)} instances")
            return health_states
        except Exception as e:
            logger.error(f"Failed to get all instance health: {e}")
            return {}

    async def clear_stale_votes(self, prefix: str = "astra:resilience:vote") -> int:
        """Remove expired/stale votes (cleanup).
        
        Args:
            prefix: Key prefix for votes
            
        Returns:
            Number of votes cleared
        """
        if not self.connected:
            return 0

        try:
            keys = await self.redis.keys(f"{prefix}:*")
            if not keys:
                return 0

            pipe = self.redis.pipeline()
            for key in keys:
                pipe.delete(key)
            results = await pipe.execute()

            cleared = sum(1 for r in results if r)
            if cleared > 0:
                logger.debug(f"Cleared {cleared} stale votes")
            return cleared
        except Exception as e:
            logger.error(f"Failed to clear stale votes: {e}")
            return 0

    async def subscribe_to_channel(self, channel: str):
        """Subscribe to pub/sub channel (returns pubsub object).
        
        Args:
            channel: Channel name to subscribe to
            
        Returns:
            Subscription object for listening to messages
        """
        if not self.connected:
            return None

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel}: {e}")
            return None

    async def health_check(self) -> bool:
        """Perform health check on Redis connection.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self.connected:
            return False

        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self.connected = False
            return False
