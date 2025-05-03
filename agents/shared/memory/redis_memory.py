import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shared-memory")

class RedisMemory:
    """Shared memory implementation using Redis"""
    
    def __init__(self, redis_url: str, namespace: str = "mcp"):
        self.redis_url = redis_url
        self.namespace = namespace
        self.redis = None
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to Redis server"""
        try:
            import redis.asyncio as redis
            self.redis = await redis.from_url(self.redis_url)
            # Test connection
            await self.redis.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True
        except ImportError:
            logger.error("Redis package not installed. Please install with: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            return False
    
    def _make_key(self, key_type: str, key_id: str) -> str:
        """Create a namespaced Redis key"""
        return f"{self.namespace}:{key_type}:{key_id}"
    
    async def store(self, key_type: str, key_id: str, data: Any, expiry: int = None) -> bool:
        """Store data in Redis with optional expiry time (in seconds)"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            # Convert data to JSON if it's not a string
            if not isinstance(data, str):
                data = json.dumps(data)
            
            key = self._make_key(key_type, key_id)
            if expiry:
                await self.redis.setex(key, expiry, data)
            else:
                await self.redis.set(key, data)
            
            return True
        except Exception as e:
            logger.error(f"Error storing data in Redis: {str(e)}")
            return False
    
    async def retrieve(self, key_type: str, key_id: str, as_json: bool = True) -> Optional[Any]:
        """Retrieve data from Redis"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return None
        
        try:
            key = self._make_key(key_type, key_id)
            data = await self.redis.get(key)
            
            if data is None:
                return None
                
            # Convert from bytes to string
            if isinstance(data, bytes):
                data = data.decode('utf-8')
                
            # Parse JSON if requested
            if as_json and data:
                return json.loads(data)
            
            return data
        except Exception as e:
            logger.error(f"Error retrieving data from Redis: {str(e)}")
            return None
    
    async def delete(self, key_type: str, key_id: str) -> bool:
        """Delete data from Redis"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            key = self._make_key(key_type, key_id)
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting data from Redis: {str(e)}")
            return False
    
    async def list_keys(self, key_type: str, pattern: str = "*") -> List[str]:
        """List keys matching a pattern"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return []
        
        try:
            search_pattern = self._make_key(key_type, pattern)
            keys = await self.redis.keys(search_pattern)
            # Strip namespace prefix from keys
            prefix = f"{self.namespace}:{key_type}:"
            return [k.decode('utf-8').replace(prefix, '') for k in keys]
        except Exception as e:
            logger.error(f"Error listing keys in Redis: {str(e)}")
            return []
    
    async def publish(self, channel: str, message: Union[str, Dict]) -> bool:
        """Publish a message to a Redis channel"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return False
        
        try:
            if not isinstance(message, str):
                message = json.dumps(message)
            
            channel_name = f"{self.namespace}:channel:{channel}"
            await self.redis.publish(channel_name, message)
            return True
        except Exception as e:
            logger.error(f"Error publishing to Redis channel: {str(e)}")
            return False
    
    async def subscribe(self, channel: str, callback) -> None:
        """Subscribe to a Redis channel with a callback function"""
        if not self.connected:
            logger.warning("Not connected to Redis")
            return
        
        try:
            channel_name = f"{self.namespace}:channel:{channel}"
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel_name)
            
            # Start listening in a separate task
            asyncio.create_task(self._message_listener(pubsub, callback))
            logger.info(f"Subscribed to channel: {channel}")
        except Exception as e:
            logger.error(f"Error subscribing to Redis channel: {str(e)}")
    
    async def _message_listener(self, pubsub, callback) -> None:
        """Background task to listen for messages and call the callback"""
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    # Parse message data
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    
                    try:
                        # Try to parse as JSON
                        data = json.loads(data)
                    except:
                        # Keep as string if not valid JSON
                        pass
                    
                    # Call the callback with the message data
                    await callback(data)
                
                # Small delay to avoid high CPU usage
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in message listener: {str(e)}")
                await asyncio.sleep(1)  # Longer delay on error


class MemoryFactory:
    """Factory for creating shared memory instances"""
    
    @staticmethod
    async def create_memory(memory_type: str, config: Dict) -> Any:
        """Create a shared memory instance based on type"""
        if memory_type.lower() == "redis":
            redis_url = config.get("redis_url", "redis://localhost:6379")
            namespace = config.get("namespace", "mcp")
            
            memory = RedisMemory(redis_url, namespace)
            connected = await memory.connect()
            
            if connected:
                return memory
            else:
                return None
        else:
            logger.error(f"Unsupported memory type: {memory_type}")
            return None


# Convenience functions for testing
async def test_redis_memory():
    # Example usage
    memory = await MemoryFactory.create_memory("redis", {
        "redis_url": "redis://localhost:6379", 
        "namespace": "test"
    })
    
    if memory:
        # Store data
        await memory.store("agent", "agent1", {"status": "active", "timestamp": time.time()})
        
        # Retrieve data
        data = await memory.retrieve("agent", "agent1")
        print(f"Retrieved data: {data}")
        
        # List keys
        keys = await memory.list_keys("agent")
        print(f"Agent keys: {keys}")
        
        # Publish-subscribe example
        async def message_handler(message):
            print(f"Received message: {message}")
        
        await memory.subscribe("updates", message_handler)
        await memory.publish("updates", {"event": "test", "data": "Hello World"})
        
        # Wait a moment for the message to be received
        await asyncio.sleep(1)
        
        # Delete data
        await memory.delete("agent", "agent1")

if __name__ == "__main__":
    asyncio.run(test_redis_memory())