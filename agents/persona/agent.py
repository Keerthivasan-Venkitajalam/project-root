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
logger = logging.getLogger("persona-agent")

# OpenAI client setup
client = AsyncOpenAI()

class PersonaAgent:
    def __init__(self, agent_id: str, mcp_server_url: str, redis_url: str = None):
        self.agent_id = agent_id
        self.mcp_server_url = mcp_server_url
        self.redis_url = redis_url
        self.connection = None
        self.personas = {
            "default": [
                {
                    "name": "Tech-savvy Millennial",
                    "age": 32,
                    "occupation": "Software Developer",
                    "tech_literacy": "High",
                    "goals": ["Efficiency", "Advanced features", "Personalization"],
                    "pain_points": ["Slow interfaces", "Limited functionality", "Poor documentation"]
                },
                {
                    "name": "Non-technical Senior",
                    "age": 72,
                    "occupation": "Retired Teacher",
                    "tech_literacy": "Low",
                    "goals": ["Simple tasks", "Connection with family", "Easy navigation"],
                    "pain_points": ["Complicated UIs", "Small text", "Rapidly changing features"]
                },
                {
                    "name": "Busy Professional",
                    "age": 45,
                    "occupation": "Marketing Executive",
                    "tech_literacy": "Medium",
                    "goals": ["Quick task completion", "Mobile accessibility", "Professional appearance"],
                    "pain_points": ["Time-consuming processes", "Distractions", "Incompatibility across devices"]
                }
            ]
        }
        self.analysis_history = []  # Store previous persona analyses

    async def connect(self):
        """Connect to the MCP server and register"""
        try:
            self.connection = await websockets.connect(self.mcp_server_url)
            
            # Register with capabilities
            register_msg = {
                "type": "REGISTER",
                "sender": self.agent_id,
                "recipient": "",
                "content": json.dumps(["PERSONA"]),
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
            
            # Load any existing personas from Redis
            personas_data = await self.redis.get(f"{self.agent_id}:personas")
            if personas_data:
                self.personas.update(json.loads(personas_data))
                
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
                # Process a persona analysis task
                await self.handle_persona_task(message)
                
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

    async def handle_persona_task(self, message: Dict):
        """Process a persona analysis task"""
        content = json.loads(message.get("content", "{}"))
        task_description = content.get("task", "")
        constraints = content.get("constraints", [])
        context = content.get("context", {})
        
        # Check if specific personas are requested
        requested_personas = content.get("personas", [])
        
        # Generate persona-based analysis
        persona_analysis = await self.generate_persona_analysis(
            task_description,
            requested_personas,
            constraints,
            context
        )
        
        # Record this analysis in history
        self.analysis_history.append({
            "timestamp": time.time(),
            "task": task_description,
            "analysis": persona_analysis,
            "trace_id": message.get("trace_id")
        })
        
        # Limit history size to prevent unbounded growth
        if len(self.analysis_history) > 50:
            self.analysis_history = self.analysis_history[-50:]
        
        # Store in Redis if available
        if hasattr(self, 'redis'):
            await self.redis.set(
                f"{self.agent_id}:analysis:{message.get('trace_id')}",
                json.dumps({
                    "task": task_description,
                    "analysis": persona_analysis,
                    "timestamp": time.time()
                }),
                ex=86400  # expire after 24 hours
            )
        
        # Send response
        response_msg = {
            "type": "RESPONSE",
            "sender": self.agent_id,
            "recipient": message.get("sender"),
            "content": persona_analysis,
            "timestamp": int(time.time()),
            "trace_id": message.get("trace_id"),
            "parent_id": message.get("parent_id"),
            "metadata": message.get("metadata")  # Pass through metadata
        }
        
        await self.connection.send(json.dumps(response_msg))
        logger.info(f"Sent persona analysis for task from {message.get('sender')}")
    
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
        
        if message_type == "persona_update":
            # Another agent is informing us about updated personas
            personas_group = content.get("group_name")
            personas_data = content.get("personas", [])
            
            if personas_group and personas_data:
                self.personas[personas_group] = personas_data
                logger.info(f"Updated personas [{personas_group}] from agent {message.get('sender')}")
                
                # Store in Redis if available
                if hasattr(self, 'redis'):
                    await self.redis.set(
                        f"{self.agent_id}:personas",
                        json.dumps(self.personas),
                        ex=604800  # expire after 7 days
                    )
                
                # Acknowledge the update
                ack_msg = {
                    "type": "A2A",
                    "sender": self.agent_id,
                    "recipient": message.get("sender"),
                    "content": json.dumps({
                        "message_type": "persona_update_ack",
                        "status": "success"
                    }),
                    "timestamp": int(time.time()),
                    "trace_id": message.get("trace_id"),
                    "parent_id": message.get("message_id")
                }
                
                await self.connection.send(json.dumps(ack_msg))
        else:
            logger.warning(f"Unhandled A2A message type: {message_type}")
        
    async def generate_persona_analysis(self, task: str, requested_personas: List[str], constraints: List, context: Dict) -> str:
        """Generate persona-based analysis"""
        try:
            # Determine which personas to use
            personas_to_use = []
            if requested_personas:
                # Use specific requested personas
                for persona_name in requested_personas:
                    for group, personas in self.personas.items():
                        for persona in personas:
                            if persona.get("name", "").lower() == persona_name.lower():
                                personas_to_use.append(persona)
            
            # If no specific personas were found, use default personas
            if not personas_to_use:
                personas_to_use = self.personas.get("default", [])
            
            # Build a context with task, personas, and constraints
            context_str = json.dumps(context, indent=2) if context else "No additional context"
            personas_str = json.dumps(personas_to_use, indent=2)
            
            prompt = f"""As a user research and persona AI agent, analyze how the following design task would be received by different user personas:

Task: {task}

User Personas:
{personas_str}

Constraints:
{chr(10).join(['- ' + c for c in constraints])}

Context:
{context_str}

For each persona, please provide a detailed analysis of:
1. How they would interact with this design
2. Key pain points they might experience
3. Features that would resonate with them
4. Accessibility considerations specific to this persona
5. Recommended design adjustments to better serve this persona
"""

            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert user researcher specializing in persona-based design analysis. You help design teams understand how different user types interact with their products."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating persona analysis: {str(e)}")
            return f"Error generating persona analysis: {str(e)}"
    
    async def respond_to_query(self, query: str) -> str:
        """Respond to a direct query from another agent"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert user researcher specializing in persona-based design analysis. You help design teams understand how different user types interact with their products."},
                    {"role": "user", "content": f"Another AI agent is asking you: {query}. Respond with your user research expertise."}
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
    
    agent = PersonaAgent("persona-agent", mcp_url, redis_url)
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())