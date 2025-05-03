import asyncio
import json
import uuid
import time
import websockets
from typing import Dict, Any
import logging
from openai import AsyncOpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aesthetic-agent")

# OpenAI client setup
client = AsyncOpenAI()

class AestheticAgent:
    def __init__(self, agent_id: str, mcp_server_url: str):
        self.agent_id = agent_id
        self.mcp_server_url = mcp_server_url
        self.connection = None
        self.design_memory = []  # Store previous design decisions

    async def connect(self):
        """Connect to the MCP server and register"""
        try:
            self.connection = await websockets.connect(self.mcp_server_url)
            
            # Register with capabilities
            register_msg = {
                "type": "REGISTER",
                "sender": self.agent_id,
                "recipient": "",
                "content": json.dumps(["AESTHETIC"]),
                "timestamp": int(time.time()),
                "trace_id": str(uuid.uuid4())
            }
            
            await self.connection.send(json.dumps(register_msg))
            logger.info(f"Connected to MCP server as {self.agent_id}")
            
            # Start message handling loop
            await self.message_loop()
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            
    async def message_loop(self):
        """Main message processing loop"""
        try:
            while True:
                message = await self.connection.recv()
                await self.process_message(json.loads(message))
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to MCP server closed")
        except Exception as e:
            logger.error(f"Error in message loop: {str(e)}")
            
    async def process_message(self, message: Dict):
        """Process incoming messages"""
        msg_type = message.get("type")
        
        if msg_type == "TASK":
            # Process a design task
            await self.handle_design_task(message)
            
        elif msg_type == "QUERY":
            # Handle a query from another agent
            await self.handle_query(message)
            
        elif msg_type == "FEEDBACK":
            # Process feedback on a previous design
            await self.handle_feedback(message)

    async def handle_design_task(self, message: Dict):
        """Process a design task and generate aesthetic suggestions"""
        content = json.loads(message.get("content", "{}"))
        task_description = content.get("task", "")
        constraints = content.get("constraints", [])
        context = content.get("context", {})
        
        # Enhanced context with design memory
        enhanced_context = self.enhance_context(context)
        
        # Generate aesthetic design suggestions using LLM
        design_suggestions = await self.generate_design_suggestions(
            task_description, 
            constraints, 
            enhanced_context
        )
        
        # Record this design decision in memory
        self.design_memory.append({
            "timestamp": time.time(),
            "task": task_description,
            "suggestions": design_suggestions,
            "trace_id": message.get("trace_id")
        })
        
        # Limit memory size to prevent unbounded growth
        if len(self.design_memory) > 50:
            self.design_memory = self.design_memory[-50:]
        
        # Send response
        response_msg = {
            "type": "RESPONSE",
            "sender": self.agent_id,
            "recipient": message.get("sender"),
            "content": design_suggestions,
            "timestamp": int(time.time()),
            "trace_id": message.get("trace_id"),
            "parent_id": message.get("parent_id"),
            "metadata": message.get("metadata")  # Pass through metadata
        }
        
        await self.connection.send(json.dumps(response_msg))
        logger.info(f"Sent design suggestions for task from {message.get('sender')}")
    
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
    
    async def handle_feedback(self, message: Dict):
        """Process feedback on a previous design"""
        content = json.loads(message.get("content", "{}"))
        feedback = content.get("feedback", "")
        original_trace_id = content.get("original_trace_id", "")
        
        # Find the original design in memory
        original_design = next(
            (item for item in self.design_memory if item["trace_id"] == original_trace_id), 
            None
        )
        
        if original_design:
            # Update the design memory with feedback
            original_design["feedback"] = feedback
            logger.info(f"Recorded feedback for trace {original_trace_id}")
            
            # Send acknowledgment
            ack_msg = {
                "type": "RESPONSE",
                "sender": self.agent_id,
                "recipient": message.get("sender"),
                "content": json.dumps({"status": "feedback_recorded"}),
                "timestamp": int(time.time()),
                "trace_id": message.get("trace_id"),
                "parent_id": message.get("message_id")
            }
            
            await self.connection.send(json.dumps(ack_msg))
        else:
            logger.warning(f"Received feedback for unknown design: {original_trace_id}")
    
    def enhance_context(self, context: Dict) -> Dict:
        """Enhance context with design memory"""
        enhanced = context.copy()
        
        # Add recent design decisions and feedback
        recent_designs = [
            {
                "task": item["task"],
                "suggestions": item["suggestions"][:100] + "..." if len(item["suggestions"]) > 100 else item["suggestions"],
                "feedback": item.get("feedback", "No feedback")
            }
            for item in self.design_memory[-5:] if "feedback" in item
        ]
        
        if recent_designs:
            enhanced["recent_design_history"] = recent_designs
            
        return enhanced
        
    async def generate_design_suggestions(self, task: str, constraints: list, context: Dict) -> str:
        """Generate aesthetic design suggestions using LLM"""
        try:
            # Build a prompt with task, constraints and context
            context_str = json.dumps(context, indent=2) if context else "No additional context"
            
            prompt = f"""As an aesthetic design AI agent, generate visual design suggestions for this task:

Task: {task}

Constraints:
{chr(10).join(['- ' + c for c in constraints])}

Context:
{context_str}

Please provide detailed suggestions for:
1. Color palette (with hex codes)
2. Typography recommendations
3. Visual style/mood board direction
4. Key visual elements
5. Layout considerations
"""

            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert aesthetic designer AI with knowledge of color theory, typography, and visual design principles."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating design suggestions: {str(e)}")
            return "Error generating design suggestions. Please try again."
    
    async def respond_to_query(self, query: str) -> str:
        """Respond to a direct query from another agent"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert aesthetic designer AI responding to queries from other specialized AI agents."},
                    {"role": "user", "content": f"Another AI agent is asking you: {query}. Respond with your aesthetic design expertise."}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error responding to query: {str(e)}")
            return "Error processing your query. Please try again."

# Run the agent
async def main():
    agent = AestheticAgent("aesthetic-agent", "ws://localhost:8080")
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())