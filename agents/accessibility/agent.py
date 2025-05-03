import asyncio
import json
import uuid
import time
import websockets
from typing import Dict, List, Any
import logging
from openai import AsyncOpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("accessibility-agent")

# OpenAI client setup
client = AsyncOpenAI()

class AccessibilityAgent:
    def __init__(self, agent_id: str, mcp_server_url: str, redis_url: str = None):
        self.agent_id = agent_id
        self.mcp_server_url = mcp_server_url
        self.redis_url = redis_url
        self.connection = None
        self.accessibility_standards = {
            "WCAG_2_1": ["Perceivable", "Operable", "Understandable", "Robust"],
            "ADA": ["Text alternatives", "Time-based media", "Adaptable content", "Distinguishable content"],
            "Section_508": ["Software applications", "Web content", "Telecommunications", "Video/multimedia"]
        }
        self.recommendation_history = []  # Store previous accessibility recommendations

    async def connect(self):
        """Connect to the MCP server and register"""
        try:
            self.connection = await websockets.connect(self.mcp_server_url)
            
            # Register with capabilities
            register_msg = {
                "type": "REGISTER",
                "sender": self.agent_id,
                "recipient": "",
                "content": json.dumps(["ACCESSIBILITY"]),
                "timestamp": int(time.time()),
                "trace_id": str(uuid.uuid4())
            }
            
            await self.connection.send(json.dumps(register_msg))
            logger.info(f"Connected to MCP server as {self.agent_id}")
            
            # If Redis is configured, initialize the shared memory
            if self.redis_url:
                await self.init_shared_memory()
            
            # Start message handling loop
            await self.message_loop()
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            # Attempt reconnection after delay
            await asyncio.sleep(5)
            await self.connect()
            
    async def init_shared_memory(self):
        """Initialize connection to Redis for shared memory"""
        try:
            import redis.asyncio as redis
            self.redis = await redis.from_url(self.redis_url)
            logger.info("Connected to Redis shared memory")
            
            # Load any existing accessibility standards from Redis
            standards = await self.redis.get(f"{self.agent_id}:standards")
            if standards:
                self.accessibility_standards.update(json.loads(standards))
                
        except ImportError:
            logger.warning("Redis package not installed. Shared memory features disabled.")
            self.redis_url = None
        except Exception as e:
            logger.error(f"Error connecting to Redis: {str(e)}")
            self.redis_url = None
            
    async def message_loop(self):
        """Main message processing loop"""
        try:
            while True:
                message = await self.connection.recv()
                await self.process_message(json.loads(message))
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to MCP server closed")
            # Attempt reconnection after delay
            await asyncio.sleep(5)
            await self.connect()
        except Exception as e:
            logger.error(f"Error in message loop: {str(e)}")
            
    async def process_message(self, message: Dict):
        """Process incoming messages"""
        try:
            msg_type = message.get("type")
            
            if msg_type == "TASK":
                # Process an accessibility task
                await self.handle_accessibility_task(message)
                
            elif msg_type == "QUERY":
                # Handle a query from another agent
                await self.handle_query(message)
                
            elif msg_type == "A2A":
                # Handle direct agent-to-agent communication
                await self.handle_a2a_message(message)
                
            # Log valid message processing to blockchain if enabled
            if hasattr(self, 'blockchain_logger'):
                await self.blockchain_logger.log_contribution(
                    self.agent_id,
                    message.get("trace_id", "unknown"),
                    message_type=msg_type
                )
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Send error response if possible
            if message.get("sender"):
                await self.send_error_response(message, str(e))

    async def send_error_response(self, original_message: Dict, error_msg: str):
        """Send an error response for a failed request"""
        try:
            response_msg = {
                "type": "RESPONSE",
                "sender": self.agent_id,
                "recipient": original_message.get("sender"),
                "content": json.dumps({"error": error_msg}),
                "timestamp": int(time.time()),
                "trace_id": original_message.get("trace_id"),
                "parent_id": original_message.get("message_id")
            }
            
            await self.connection.send(json.dumps(response_msg))
            logger.info(f"Sent error response to {original_message.get('sender')}")
        except Exception as e:
            logger.error(f"Failed to send error response: {str(e)}")

    async def handle_accessibility_task(self, message: Dict):
        """Process an accessibility analysis task"""
        content = json.loads(message.get("content", "{}"))
        task_description = content.get("task", "")
        constraints = content.get("constraints", [])
        context = content.get("context", {})
        
        # Extract design details if available
        design_data = content.get("design_data", {})
        
        # Generate accessibility recommendations
        accessibility_recommendations = await self.generate_accessibility_recommendations(
            task_description,
            design_data,
            constraints,
            context
        )
        
        # Record this recommendation in history
        self.recommendation_history.append({
            "timestamp": time.time(),
            "task": task_description,
            "recommendations": accessibility_recommendations,
            "trace_id": message.get("trace_id")
        })
        
        # Limit history size to prevent unbounded growth
        if len(self.recommendation_history) > 50:
            self.recommendation_history = self.recommendation_history[-50:]
        
        # Store in Redis if available
        if hasattr(self, 'redis'):
            await self.redis.set(
                f"{self.agent_id}:recommendation:{message.get('trace_id')}",
                json.dumps({
                    "task": task_description,
                    "recommendations": accessibility_recommendations,
                    "timestamp": time.time()
                }),
                ex=86400  # expire after 24 hours
            )
        
        # Send response
        response_msg = {
            "type": "RESPONSE",
            "sender": self.agent_id,
            "recipient": message.get("sender"),
            "content": accessibility_recommendations,
            "timestamp": int(time.time()),
            "trace_id": message.get("trace_id"),
            "parent_id": message.get("parent_id"),
            "metadata": message.get("metadata")  # Pass through metadata
        }
        
        await self.connection.send(json.dumps(response_msg))
        logger.info(f"Sent accessibility recommendations for task from {message.get('sender')}")
    
    async def handle_query(self, message: Dict):
        """Handle a direct query from another agent"""
        content = json.loads(message.get("content", "{}"))
        query = content.get("query", "")
        
        # Generate a response to the query
        query_response = await self.respond_to_query(query)
        
        # Send response
        response_msg = {
            "type": "RESPONSE",
            "sender": self.agent_id,
            "recipient": message.get("sender"),
            "content": json.dumps({"response": query_response}),
            "timestamp": int(time.time()),
            "trace_id": message.get("trace_id"),
            "parent_id": message.get("message_id")
        }
        
        await self.connection.send(json.dumps(response_msg))
        logger.info(f"Sent query response to {message.get('sender')}")
    
    async def handle_a2a_message(self, message: Dict):
        """Handle direct communications from other agents"""
        content = json.loads(message.get("content", "{}"))
        message_type = content.get("message_type", "")
        
        if message_type == "standards_update":
            # Another agent is informing us about updated standards
            new_standards = content.get("standards", {})
            if new_standards:
                self.accessibility_standards.update(new_standards)
                logger.info(f"Updated accessibility standards from agent {message.get('sender')}")
                
                # Acknowledge the update
                ack_msg = {
                    "type": "A2A",
                    "sender": self.agent_id,
                    "recipient": message.get("sender"),
                    "content": json.dumps({
                        "message_type": "standards_update_ack",
                        "status": "success"
                    }),
                    "timestamp": int(time.time()),
                    "trace_id": message.get("trace_id"),
                    "parent_id": message.get("message_id")
                }
                
                await self.connection.send(json.dumps(ack_msg))
        else:
            logger.warning(f"Unhandled A2A message type: {message_type}")
        
    async def generate_accessibility_recommendations(self, task: str, design_data: Dict, constraints: List, context: Dict) -> str:
        """Generate accessibility recommendations"""
        try:
            # Build a context with task, design data, constraints and accessibility standards
            context_str = json.dumps(context, indent=2) if context else "No additional context"
            design_str = json.dumps(design_data, indent=2) if design_data else "No design data provided"
            
            standards_info = []
            for std_name, std_criteria in self.accessibility_standards.items():
                standards_info.append(f"{std_name}: {', '.join(std_criteria)}")
            
            prompt = f"""As an accessibility expert AI agent, analyze the following design task and provide accessibility recommendations:

Task: {task}

Design Information:
{design_str}

Constraints:
{chr(10).join(['- ' + c for c in constraints])}

Context:
{context_str}

Accessibility Standards to Consider:
{chr(10).join(['- ' + s for s in standards_info])}

Please provide detailed recommendations for:
1. Visual Accessibility (color contrast, text size, etc.)
2. Screen Reader Compatibility
3. Keyboard Navigation
4. Alternative Input Methods
5. Cognitive Accessibility Considerations
6. Specific WCAG 2.1 Success Criteria Compliance
"""

            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert on digital accessibility and inclusive design. You provide practical recommendations to make digital interfaces accessible to people with disabilities."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating accessibility recommendations: {str(e)}")
            return f"Error generating accessibility recommendations: {str(e)}"
    
    async def respond_to_query(self, query: str) -> str:
        """Respond to a direct query from another agent"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert on digital accessibility and inclusive design. You provide practical recommendations to make digital interfaces accessible to people with disabilities."},
                    {"role": "user", "content": f"Another AI agent is asking you: {query}. Respond with your accessibility expertise."}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error responding to query: {str(e)}")
            return f"Error processing your query: {str(e)}"

# Run the agent
async def main():
    # Get environment variables or use defaults
    import os
    mcp_url = os.environ.get("MCP_SERVER_URL", "ws://localhost:8080")
    redis_url = os.environ.get("REDIS_URL", None)
    
    agent = AccessibilityAgent("accessibility-agent", mcp_url, redis_url)
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())