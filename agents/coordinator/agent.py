import asyncio
import json
import uuid
import time
import websockets
from typing import Dict, List, Optional, Any
import logging
from openai import AsyncOpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coordinator-agent")

# OpenAI client setup
client = AsyncOpenAI()

class CoordinatorAgent:
    def __init__(self, agent_id: str, mcp_server_url: str):
        self.agent_id = agent_id
        self.mcp_server_url = mcp_server_url
        self.connection = None
        self.agents = {}  # tracked agents and their capabilities
        self.active_tasks = {}  # track ongoing tasks
        self.task_responses = {}  # collect responses for tasks

    async def connect(self):
        """Connect to the MCP server and register"""
        try:
            self.connection = await websockets.connect(self.mcp_server_url)
            
            # Register with capabilities
            register_msg = {
                "type": "REGISTER",
                "sender": self.agent_id,
                "recipient": "",
                "content": json.dumps(["COORDINATION"]),
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
        
        if msg_type == "REGISTER":
            # An agent is registering, track its capabilities
            sender = message.get("sender")
            capabilities = json.loads(message.get("content", "[]"))
            self.agents[sender] = {"capabilities": capabilities}
            logger.info(f"Agent registered: {sender} with capabilities {capabilities}")
            
        elif msg_type == "TASK":
            # User task received, break it down and delegate
            await self.handle_user_task(message)
            
        elif msg_type == "RESPONSE":
            # Response from an agent for a task
            await self.handle_agent_response(message)

    async def handle_user_task(self, message: Dict):
        """Break down a user task and delegate to appropriate agents"""
        content = json.loads(message.get("content", "{}"))
        task_description = content.get("task", "")
        trace_id = message.get("trace_id")
        
        # Use LLM to analyze the task and break it down
        task_breakdown = await self.analyze_task(task_description)
        
        # Create a new task tracker
        task_id = str(uuid.uuid4())
        self.active_tasks[task_id] = {
            "trace_id": trace_id,
            "original_message": message,
            "subtasks": task_breakdown,
            "pending_responses": len(task_breakdown),
            "started_at": time.time()
        }
        
        # Delegate subtasks to appropriate agents
        for subtask in task_breakdown:
            capability_needed = subtask["capability"]
            agent_id = self.find_agent_for_capability(capability_needed)
            
            if not agent_id:
                logger.warning(f"No agent found for capability: {capability_needed}")
                continue
                
            # Send the subtask to the agent
            subtask_msg = {
                "type": "TASK",
                "sender": self.agent_id,
                "recipient": agent_id,
                "content": json.dumps({
                    "task": subtask["description"],
                    "context": subtask.get("context", {}),
                    "constraints": subtask.get("constraints", [])
                }),
                "timestamp": int(time.time()),
                "trace_id": trace_id,
                "parent_id": task_id,
                "metadata": json.dumps({
                    "subtask_id": subtask["id"],
                    "priority": subtask.get("priority", "MEDIUM")
                })
            }
            
            await self.connection.send(json.dumps(subtask_msg))
            logger.info(f"Delegated subtask {subtask['id']} to agent {agent_id}")
    
    async def handle_agent_response(self, message: Dict):
        """Process responses from agents for subtasks"""
        parent_id = message.get("parent_id")
        if not parent_id or parent_id not in self.active_tasks:
            logger.warning(f"Received response for unknown task: {parent_id}")
            return
            
        task = self.active_tasks[parent_id]
        metadata = json.loads(message.get("metadata", "{}"))
        subtask_id = metadata.get("subtask_id")
        
        # Store the response
        if "responses" not in task:
            task["responses"] = {}
        
        task["responses"][subtask_id] = {
            "agent": message.get("sender"),
            "content": message.get("content"),
            "timestamp": message.get("timestamp")
        }
        
        task["pending_responses"] -= 1
        
        # If all responses received, synthesize and send final response
        if task["pending_responses"] <= 0:
            await self.synthesize_results(parent_id)
    
    async def analyze_task(self, task_description: str) -> List[Dict]:
        """Use LLM to analyze the task and break it down into subtasks"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI task coordinator. Break down design tasks into subtasks that can be assigned to specialized agents."},
                    {"role": "user", "content": f"Break down this design task into subtasks for different agents with different capabilities: {task_description}. For each subtask, specify which capability is needed (AESTHETIC, UX_FLOW, ACCESSIBILITY, PERSONA), a detailed description, any constraints, and priority (HIGH/MEDIUM/LOW)."}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add unique IDs to each subtask
            for i, subtask in enumerate(result.get("subtasks", [])):
                subtask["id"] = f"subtask-{uuid.uuid4()}"
                
            return result.get("subtasks", [])
            
        except Exception as e:
            logger.error(f"Error analyzing task: {str(e)}")
            # Return a simple default breakdown
            return [
                {
                    "id": f"subtask-{uuid.uuid4()}",
                    "capability": "AESTHETIC",
                    "description": f"Provide design suggestions for: {task_description}",
                    "priority": "HIGH"
                }
            ]
    
    def find_agent_for_capability(self, capability: str) -> Optional[str]:
        """Find an agent with the required capability"""
        for agent_id, details in self.agents.items():
            if capability in details.get("capabilities", []):
                return agent_id
        return None
        
    async def synthesize_results(self, task_id: str):
        """Synthesize results from all subtasks into a final response"""
        task = self.active_tasks[task_id]
        responses = task.get("responses", {})
        
        # Use LLM to synthesize the results
        try:
            response_texts = []
            for subtask_id, response in responses.items():
                subtask_info = next((s for s in task["subtasks"] if s["id"] == subtask_id), None)
                if subtask_info:
                    response_texts.append(f"Agent {response['agent']} ({subtask_info['capability']}): {response['content']}")
            
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI coordinator synthesizing design inputs from multiple specialized agents."},
                    {"role": "user", "content": f"Synthesize these agent responses into a cohesive design solution:\n\n{chr(10).join(response_texts)}"}
                ]
            )
            
            synthesis = response.choices[0].message.content
            
            # Send the synthesized response back to the original requester
            original_msg = task["original_message"]
            response_msg = {
                "type": "RESPONSE",
                "sender": self.agent_id,
                "recipient": original_msg.get("sender"),
                "content": synthesis,
                "timestamp": int(time.time()),
                "trace_id": task["trace_id"],
                "parent_id": original_msg.get("message_id")
            }
            
            await self.connection.send(json.dumps(response_msg))
            logger.info(f"Sent synthesized response for task {task_id}")
            
            # Clean up
            del self.active_tasks[task_id]
            
        except Exception as e:
            logger.error(f"Error synthesizing results: {str(e)}")

# Run the agent
async def main():
    agent = CoordinatorAgent("coordinator-agent", "ws://localhost:8080")
    await agent.connect()

if __name__ == "__main__":
    asyncio.run(main())