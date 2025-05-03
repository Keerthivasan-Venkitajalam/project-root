import asyncio
import unittest
import json
import sys
import os
import time
import websockets
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.coordinator.agent import CoordinatorAgent
from agents.accessibility.agent import AccessibilityAgent
from agents.shared.memory.redis_memory import RedisMemory, MemoryFactory


class TestAgentInteractions(unittest.TestCase):
    """Integration tests for agent interactions"""
    
    def setUp(self):
        # Create mocks for WebSockets
        self.websocket_connect_patcher = patch('websockets.connect')
        self.websocket_connect_mock = self.websocket_connect_patcher.start()
        
        # Configure WebSocket mock
        self.coordinator_ws = AsyncMock()
        self.accessibility_ws = AsyncMock()
        
        # Configure connect to return different mocks based on URL
        async def mock_connect(url, **kwargs):
            if url == "ws://mcp-server:8080":
                return self.coordinator_ws
            else:
                return self.accessibility_ws
                
        self.websocket_connect_mock.side_effect = mock_connect
        
        # Create a mock for Redis
        self.redis_patcher = patch('redis.asyncio.Redis.from_url')
        self.redis_mock = self.redis_patcher.start()
        
        # Configure the Redis mock
        self.redis_instance = MagicMock()
        self.redis_mock.return_value = self.redis_instance
        
        # Set up Redis mock methods
        self.redis_instance.ping = AsyncMock(return_value=True)
        self.redis_instance.set = AsyncMock(return_value=True)
        self.redis_instance.get = AsyncMock(return_value=None)
        
        # Create OpenAI mock
        self.openai_patcher = patch('openai.AsyncOpenAI')
        self.openai_mock = self.openai_patcher.start()
        
        # Create event loop for async tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Set up response queue for WebSocket mocks
        self.coordinator_responses = []
        self.accessibility_responses = []
        
        async def coordinator_recv():
            if self.coordinator_responses:
                return self.coordinator_responses.pop(0)
            # Default message if queue is empty
            return json.dumps({
                "type": "QUERY",
                "sender": "ui-client",
                "recipient": "coordinator-agent",
                "content": json.dumps({"query": "How can I make this design accessible?"}),
                "trace_id": "test-trace-1",
                "message_id": "test-message-1"
            })
            
        async def accessibility_recv():
            if self.accessibility_responses:
                return self.accessibility_responses.pop(0)
            # Default message if queue is empty
            return json.dumps({
                "type": "TASK",
                "sender": "coordinator-agent",
                "recipient": "accessibility-agent",
                "content": json.dumps({
                    "task": "Analyze accessibility of a mobile app design",
                    "constraints": ["WCAG 2.1 AA compliance required"],
                    "context": {}
                }),
                "trace_id": "test-trace-1",
                "message_id": "test-message-2",
                "parent_id": "test-message-1"
            })
        
        self.coordinator_ws.recv = coordinator_recv
        self.accessibility_ws.recv = accessibility_recv
        
    def tearDown(self):
        # Stop the patchers
        self.websocket_connect_patcher.stop()
        self.redis_patcher.stop()
        self.openai_patcher.stop()
        
        # Close the event loop
        self.loop.close()
    
    async def setup_redis_memory(self):
        """Set up and return a Redis memory instance for testing"""
        memory = await MemoryFactory.create_memory("redis", {
            "redis_url": "redis://localhost:6379",
            "namespace": "test"
        })
        return memory
    
    async def _run_agent_communication_test(self):
        """Main test function for agent communication"""
        # Create a shared memory instance
        shared_memory = await self.setup_redis_memory()
        
        # Create agent instances
        coordinator = CoordinatorAgent("coordinator-agent", "ws://mcp-server:8080", "redis://localhost:6379")
        accessibility = AccessibilityAgent("accessibility-agent", "ws://localhost:8080", "redis://localhost:6379")
        
        # Mock OpenAI responses
        coordinator_completion = MagicMock()
        coordinator_completion.choices = [MagicMock()]
        coordinator_completion.choices[0].message.content = "I'll ask the accessibility agent for advice."
        
        accessibility_completion = MagicMock()
        accessibility_completion.choices = [MagicMock()]
        accessibility_completion.choices[0].message.content = "Here are accessibility recommendations: [detailed list]"
        
        # Configure mock to return different responses for each agent
        openai_instance = self.openai_mock.return_value
        openai_instance.chat.completions.create = AsyncMock()
        
        # We'll use side effect to return different responses based on the prompt
        async def mock_create(**kwargs):
            prompt = kwargs.get('messages', [{}])[-1].get('content', '')
            if 'accessibility' in prompt.lower():
                return accessibility_completion
            else:
                return coordinator_completion
        
        openai_instance.chat.completions.create.side_effect = mock_create
        
        # Queue up WebSocket responses
        self.coordinator_responses = [
            json.dumps({
                "type": "QUERY",
                "sender": "ui-client",
                "recipient": "coordinator-agent",
                "content": json.dumps({"query": "How can I make this design accessible?"}),
                "trace_id": "test-trace-1",
                "message_id": "test-message-1"
            })
        ]
        
        self.accessibility_responses = [
            json.dumps({
                "type": "TASK",
                "sender": "coordinator-agent",
                "recipient": "accessibility-agent",
                "content": json.dumps({
                    "task": "Analyze accessibility of a mobile app design",
                    "constraints": ["WCAG 2.1 AA compliance required"],
                    "context": {}
                }),
                "trace_id": "test-trace-1",
                "message_id": "test-message-2", 
                "parent_id": "test-message-1"
            })
        ]
        
        # Start the agents
        coordinator_task = asyncio.create_task(self._run_agent_with_timeout(coordinator))
        accessibility_task = asyncio.create_task(self._run_agent_with_timeout(accessibility))
        
        # Wait for a short time to allow message exchange
        await asyncio.sleep(1)
        
        # Cancel the tasks (they would run indefinitely otherwise)
        coordinator_task.cancel()
        accessibility_task.cancel()
        
        try:
            await coordinator_task
        except asyncio.CancelledError:
            pass
            
        try:
            await accessibility_task
        except asyncio.CancelledError:
            pass
        
        # Verify the interactions
        # 1. Coordinator registers with MCP server
        register_call = json.loads(self.coordinator_ws.send.call_args_list[0][0][0])
        self.assertEqual(register_call["type"], "REGISTER")
        self.assertEqual(register_call["sender"], "coordinator-agent")
        
        # 2. Accessibility agent registers with MCP server
        register_call = json.loads(self.accessibility_ws.send.call_args_list[0][0][0])
        self.assertEqual(register_call["type"], "REGISTER")
        self.assertEqual(register_call["sender"], "accessibility-agent")
        
        # Check if coordinator agent sent a message to accessibility agent
        coordinator_sent_messages = [
            json.loads(call[0][0]) 
            for call in self.coordinator_ws.send.call_args_list 
            if json.loads(call[0][0]).get("recipient") == "accessibility-agent"
        ]
        
        self.assertTrue(len(coordinator_sent_messages) > 0)
        
        # Check if data was stored in Redis
        self.redis_instance.set.assert_called()
        
    async def _run_agent_with_timeout(self, agent):
        """Run an agent with a timeout to prevent hanging tests"""
        try:
            # Initialize agent connection
            connect_task = asyncio.create_task(agent.connect())
            
            # Wait for a short time
            await asyncio.sleep(1)
            
            # Return the task for later cancellation
            return connect_task
        except Exception as e:
            print(f"Error running agent: {str(e)}")
            return None
    
    def test_agent_communication(self):
        """Test communication between agents"""
        self.loop.run_until_complete(self._run_agent_communication_test())


if __name__ == '__main__':
    unittest.main()