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
logger = logging.getLogger("ux-flow-agent")

# OpenAI client setup
client = AsyncOpenAI()

class UXFlowAgent:
    def __init__(self, agent_id: str, mcp_server_url: str):
        self.agent_id = agent_id
        self.mcp_server_url = mcp_server_url
        self.connection = None
        self.flow_history = []  # Store previous UX flow designs

    async def connect(self):
        """Connect to the MCP server and register"""
        try:
            self.connection = await websockets.connect(self.mcp_server_url)
            
            # Register with capabilities
            register_msg = {
                "type": "REGISTER",
                "sender": self.agent_id,
                "recipient": "",
                "content": json.dumps(["UX_FLOW"]),
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
            # Process a UX flow task
            await self.handle_ux_task(message)
            
        elif msg_type == "QUERY":
            # Handle a query from another agent
            await self.handle_query(message)
            
        elif msg_type == "A2A":
            # Handle direct agent-to-agent communication
            await self.handle_a2a_message(message)

    async def handle_ux_task(self, message: Dict):
        """Process a UX flow task and generate recommendations"""
        content = json.loads(message.get("content", "{}"))
        task_description = content.get("task", "")
        constraints = content.get("constraints", [])
        context = content.get("context", {})
        
        # If this is a task that requires coordination with the aesthetic agent
        # we might want to query the aesthetic agent first
        needs_aesthetic_input = self.check_if_needs_aesthetic_input(task_description)
        
        if needs_aesthetic_input:
            # Let's first try to get some aesthetic input
            aesthetic_input = await self.query_aesthetic_agent(task_description)
            # Enhance context with aesthetic input
            context["aesthetic_input"] = aesthetic_input
        
        # Generate UX flow recommendations
        ux_recommendations = await self.generate_ux_recommendations(
            task_description,
            constraints,
            context
        )
        
        # Record this design decision in history
        self.flow_history.append({
            "timestamp": time.time(),
            "task": task_description,
            "recommendations": ux_recommendations,
            "trace_id": message.get("trace_id")
        })
        
        # Limit history size to prevent unbounded growth
        if len(self.flow_history) > 50:
            self.flow_history = self.flow_history[-50:]
        
        # Send response
        response_msg = {
            "type": "RESPONSE",
            "sender": self.agent_id,
            "recipient": message.get("sender"),
            "content": ux_recommendations,
            "timestamp": int(time.time()),
            "trace_id": message.get("trace_id"),
            "parent_id": message.get("parent_id"),
            "metadata": message.get("metadata")  # Pass through metadata
        }
        
        await self.connection.send(json.dumps(response_msg))
        logger.info(f"Sent UX flow recommendations for task from {message.get('sender')}")
    
    def check_if_needs_aesthetic_input(self, task_description: str) -> bool:
        """Check if the task would benefit from aesthetic agent input"""
        # Simple keyword-based check - could be more sophisticated
        aesthetic_keywords = ["visual", "look", "design", "color", "style", "layout", "appearance"]
        return any(keyword in task_description.lower() for keyword in aesthetic_keywords)
    
    async def query_aesthetic_agent(self, task_description: str) -> str:
        """Query the aesthetic agent for input on this task"""
        try:
            query_id = str(uuid.uuid4())
            
            # Create a query message
            query_msg = {
                "type": "QUERY",
                "sender": self.agent_id,
                "recipient": "aesthetic-agent",  # Assuming this is the registered ID
                "content": json.dumps({
                    "query": f"For a UX flow design task: {task_description}, what aesthetic considerations should I keep in mind?"
                }),
                "timestamp": int(time.time()),
                "trace_id": str(uuid.uuid4()),
                "message_id": query_id
            }
            
            # Track query to match with response
            query_result = asyncio.Future()
            
            # Set up a one-time response handler
            original_process_message = self.process_message
            
            async def response_interceptor(msg):
                if (msg.get("type") == "RESPONSE" and 
                    msg.get("parent_id") == query_id and
                    msg.get("sender") == "aesthetic-agent"):
                    
                    # Extract the response content
                    content = msg.get("content", "{}")
                    if isinstance(content, str):
                        try:
                            data = json.loads(content)
                            response = data.get("response", "No aesthetic input provided")
                        except json.JSONDecodeError:
                            response = content  # Just use the raw content
                    else:
                        response = "Invalid response format from aesthetic agent"
                        
                    # Set the result
                    if not query_result.done():
                        query_result.set_result(response)
                    
                # Always call the original handler
                await original_process_message(msg)
            
            # Replace the message handler temporarily
            self.process_message = response_interceptor
            
            # Send the query
            await self.connection.send(json.dumps(query_msg))
            logger.info(f"Sent query to aesthetic-agent: {query_id}")
            
            # Wait for the response with a timeout
            try:
                aesthetic_input = await asyncio.wait_for(query_result, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for aesthetic agent response")
                aesthetic_input = "No response from aesthetic agent (timeout)"
            
            # Restore the original message handler
            self.process_message = original_process_message
            
            return aesthetic_input
            
        except Exception as e:
            logger.error(f"Error querying aesthetic agent: {str(e)}")
            return "Error obtaining aesthetic input"
    
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
        """Handle a direct agent-to-agent message"""
        # Process A2A message (collaborative work with another agent)
        # Implementation depends on use cases for direct agent communication
        pass
    
    async def generate_ux_recommendations(self, task: str, constraints: list, context: Dict) -> str:
        """Generate UX flow recommendations using LLM"""
        try:
            # Check for aesthetic input in the context
            aesthetic_input = context.get("aesthetic_input", "No aesthetic input available")
            
            # Build a prompt with task, constraints and context
            context_str = json.dumps(context, indent=2) if context else "No additional context"
            
            prompt = f"""As a UX Flow design AI agent, generate user experience flow recommendations for this task:

Task: {task}

Constraints:
{chr(10).join(['- ' + c for c in constraints])}

Aesthetic Considerations:
{aesthetic_input}

Context:
{context_str}

Please provide detailed recommendations for:
1. User Flow Diagram (describe key screens and interactions)
2. Information Architecture
3. Key User Journeys
4. Interaction Patterns
5. Usability Considerations
6. Accessibility Recommendations
"""

            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert UX designer AI specializing in user flows, interaction design, and information architecture."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating UX recommendations: {str(e)}")
            return "Error generating UX flow recommendations. Please try again."
    
    async def respond_to_query(self, query: str) -> str:
        """Respond to a direct query from another agent"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert UX designer AI responding to queries from other specialized AI agents."},
                    {"role": "user", "content": f"Another AI agent is asking you: {query}. Respond with your UX design expertise."}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error responding to query: {str(e)}")
            return "Error processing your query. Please try again."

# Run the agent
async def main():
    agent = UXFlowAgent("ux-flow-agent", "ws://localhost:8080")
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())