import asyncio
import unittest
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.shared.memory.redis_memory import RedisMemory, MemoryFactory


class TestRedisMemory(unittest.TestCase):
    """Test cases for Redis-based shared memory"""
    
    def setUp(self):
        # Create a mock for Redis
        self.redis_mock_patcher = patch('redis.asyncio.Redis.from_url')
        self.redis_mock = self.redis_mock_patcher.start()
        
        # Configure the mock
        self.redis_instance = MagicMock()
        self.redis_mock.return_value = self.redis_instance
        
        # Create event loop for async tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def tearDown(self):
        # Stop the patcher
        self.redis_mock_patcher.stop()
        
        # Close the event loop
        self.loop.close()
    
    def test_create_memory_factory(self):
        """Test creating memory from factory"""
        # Run the async test
        result = self.loop.run_until_complete(
            MemoryFactory.create_memory("redis", {"redis_url": "redis://localhost:6379"})
        )
        
        # Verify the result
        self.assertIsInstance(result, RedisMemory)
        self.redis_mock.assert_called_once_with("redis://localhost:6379")
    
    def test_store_retrieve_data(self):
        """Test storing and retrieving data"""
        # Configure mock for set and get
        self.redis_instance.set = MagicMock(return_value=asyncio.Future())
        self.redis_instance.set.return_value.set_result(True)
        
        self.redis_instance.get = MagicMock(return_value=asyncio.Future())
        self.redis_instance.get.return_value.set_result(json.dumps({"test": "data"}).encode())
        
        # Create memory instance
        memory = RedisMemory("redis://localhost:6379", "test")
        memory.redis = self.redis_instance
        memory.connected = True
        
        # Store data
        store_result = self.loop.run_until_complete(
            memory.store("agent", "test-agent", {"test": "data"})
        )
        
        # Retrieve data
        retrieve_result = self.loop.run_until_complete(
            memory.retrieve("agent", "test-agent")
        )
        
        # Verify results
        self.assertTrue(store_result)
        self.assertEqual(retrieve_result, {"test": "data"})
        self.redis_instance.set.assert_called_once_with("test:agent:test-agent", '{"test": "data"}')
        self.redis_instance.get.assert_called_once_with("test:agent:test-agent")
    
    def test_delete_data(self):
        """Test deleting data"""
        # Configure mock for delete
        self.redis_instance.delete = MagicMock(return_value=asyncio.Future())
        self.redis_instance.delete.return_value.set_result(1)
        
        # Create memory instance
        memory = RedisMemory("redis://localhost:6379", "test")
        memory.redis = self.redis_instance
        memory.connected = True
        
        # Delete data
        delete_result = self.loop.run_until_complete(
            memory.delete("agent", "test-agent")
        )
        
        # Verify results
        self.assertTrue(delete_result)
        self.redis_instance.delete.assert_called_once_with("test:agent:test-agent")
    
    def test_list_keys(self):
        """Test listing keys"""
        # Sample keys returned by Redis
        sample_keys = [b"test:agent:agent1", b"test:agent:agent2"]
        
        # Configure mock for keys
        self.redis_instance.keys = MagicMock(return_value=asyncio.Future())
        self.redis_instance.keys.return_value.set_result(sample_keys)
        
        # Create memory instance
        memory = RedisMemory("redis://localhost:6379", "test")
        memory.redis = self.redis_instance
        memory.connected = True
        
        # List keys
        keys_result = self.loop.run_until_complete(
            memory.list_keys("agent")
        )
        
        # Verify results
        self.assertEqual(keys_result, ["agent1", "agent2"])
        self.redis_instance.keys.assert_called_once_with("test:agent:*")
    
    def test_pubsub(self):
        """Test publish-subscribe functionality"""
        # Configure mocks for pubsub
        self.redis_instance.publish = MagicMock(return_value=asyncio.Future())
        self.redis_instance.publish.return_value.set_result(1)
        
        pubsub_mock = MagicMock()
        self.redis_instance.pubsub = MagicMock(return_value=pubsub_mock)
        pubsub_mock.subscribe = MagicMock(return_value=asyncio.Future())
        pubsub_mock.subscribe.return_value.set_result(None)
        
        # Create memory instance
        memory = RedisMemory("redis://localhost:6379", "test")
        memory.redis = self.redis_instance
        memory.connected = True
        
        # Test publish
        publish_result = self.loop.run_until_complete(
            memory.publish("updates", {"event": "test"})
        )
        
        # Verify results
        self.assertTrue(publish_result)
        self.redis_instance.publish.assert_called_once_with(
            "test:channel:updates", 
            '{"event": "test"}'
        )
        
        # Test subscribe
        callback = MagicMock()
        self.loop.run_until_complete(
            memory.subscribe("updates", callback)
        )
        
        # Verify results
        self.redis_instance.pubsub.assert_called_once()
        pubsub_mock.subscribe.assert_called_once_with("test:channel:updates")


if __name__ == '__main__':
    unittest.main()