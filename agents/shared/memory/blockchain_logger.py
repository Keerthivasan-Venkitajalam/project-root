import asyncio
import json
import logging
import hashlib
import base64
import time
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("blockchain-logger")

class BlockchainLogger:
    """Interface to the Solana blockchain for logging agent contributions"""
    
    def __init__(self, agent_id: str, rpc_url: str = None, private_key: str = None):
        self.agent_id = agent_id
        self.rpc_url = rpc_url or "http://localhost:8899"  # Default to local Solana node
        self.private_key = private_key
        self.connected = False
        self.client = None
        self.program_id = "AGENTreg1111111111111111111111111111111111"  # From the Solana program
    
    async def connect(self) -> bool:
        """Initialize connection to the Solana blockchain"""
        try:
            # We'll use a try/except to gracefully handle missing dependencies
            # in environments where blockchain integration isn't needed
            try:
                from solana.rpc.async_api import AsyncClient
                from solana.keypair import Keypair
                from solana.publickey import PublicKey
                from solana.transaction import Transaction
                import solana.system_program as sp
                self.solana_modules = {
                    "AsyncClient": AsyncClient,
                    "Keypair": Keypair,
                    "PublicKey": PublicKey,
                    "Transaction": Transaction,
                    "system_program": sp
                }
            except ImportError:
                logger.warning("Solana packages not installed. Run 'pip install solana' to enable blockchain features.")
                return False

            # Initialize client
            self.client = self.solana_modules["AsyncClient"](self.rpc_url)
            
            # Test connection
            version = await self.client.get_version()
            if version.get("result"):
                self.connected = True
                logger.info(f"Connected to Solana node at {self.rpc_url}, version: {version['result']['solana-core']}")
                
                # Initialize keypair
                if self.private_key:
                    try:
                        # Convert string private key to bytes and create keypair
                        decoded_key = base64.b64decode(self.private_key)
                        self.keypair = self.solana_modules["Keypair"].from_secret_key(decoded_key)
                        logger.info(f"Using provided keypair with public key: {self.keypair.public_key}")
                    except Exception as e:
                        logger.error(f"Error loading private key: {str(e)}")
                        # Generate a new keypair if loading fails
                        self.keypair = self.solana_modules["Keypair"].generate()
                        logger.info(f"Generated new keypair with public key: {self.keypair.public_key}")
                else:
                    # Generate new keypair if none provided
                    self.keypair = self.solana_modules["Keypair"].generate()
                    logger.info(f"Generated new keypair with public key: {self.keypair.public_key}")
                    
                return True
            else:
                logger.error("Failed to get Solana node version")
                return False
            
        except Exception as e:
            logger.error(f"Error connecting to Solana blockchain: {str(e)}")
            return False
    
    async def log_contribution(self, agent_id: str, trace_id: str, content: str = None, 
                              message_type: str = None, metadata: Dict = None) -> Optional[str]:
        """Log a contribution to the blockchain"""
        if not self.connected:
            logger.warning("Not connected to Solana blockchain")
            return None
        
        try:
            # Create a hash of the content
            if content:
                content_bytes = content.encode('utf-8')
            else:
                # If no content provided, use a combination of available data
                combined_data = f"{agent_id}:{trace_id}:{message_type}:{json.dumps(metadata) if metadata else ''}:{time.time()}"
                content_bytes = combined_data.encode('utf-8')
                
            content_hash = hashlib.sha256(content_bytes).digest()
            
            # Prepare contribution metadata
            contribution_type = message_type or "GENERIC"
            metadata_json = json.dumps(metadata or {})
            
            # Create a transaction to call the log_contribution instruction
            # In a real implementation, this would involve more complex
            # Solana transaction building logic to interact with the program
            
            # This is a simplified placeholder for the actual transaction logic
            # that would call our Solana program
            transaction = await self._build_log_contribution_transaction(
                agent_id, 
                trace_id, 
                content_hash, 
                contribution_type, 
                metadata_json
            )
            
            if transaction:
                # Sign and send the transaction
                result = await self._send_transaction(transaction)
                if result:
                    logger.info(f"Successfully logged contribution to blockchain: {result}")
                    return result
            
            logger.warning("Failed to create or send transaction")
            return None
            
        except Exception as e:
            logger.error(f"Error logging contribution to blockchain: {str(e)}")
            return None
    
    async def rate_contribution(self, contribution_id: str, rating: int, feedback: str = "") -> Optional[str]:
        """Rate a previously logged contribution"""
        if not self.connected:
            logger.warning("Not connected to Solana blockchain")
            return None
        
        try:
            # Create a transaction to call the rate_contribution instruction
            transaction = await self._build_rate_contribution_transaction(
                contribution_id,
                rating,
                feedback
            )
            
            if transaction:
                # Sign and send the transaction
                result = await self._send_transaction(transaction)
                if result:
                    logger.info(f"Successfully rated contribution on blockchain: {result}")
                    return result
            
            logger.warning("Failed to create or send rating transaction")
            return None
            
        except Exception as e:
            logger.error(f"Error rating contribution on blockchain: {str(e)}")
            return None
    
    async def _build_log_contribution_transaction(self, agent_id: str, trace_id: str, 
                                                content_hash: bytes, contribution_type: str, 
                                                metadata: str) -> Any:
        """Build a Solana transaction to log a contribution"""
        # Placeholder for the actual transaction building logic
        # In a real implementation, this would use the Solana Python SDK
        # to create a transaction that calls the log_contribution instruction
        # in the agent_registry program
        
        # For demonstration purposes, we'll log the attempt
        logger.info(f"Would build transaction to log contribution: agent={agent_id}, trace_id={trace_id}, type={contribution_type}")
        
        # Simulate successful transaction creation
        return {
            "simulate": True,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "content_hash": content_hash.hex(),
            "type": contribution_type
        }
    
    async def _build_rate_contribution_transaction(self, contribution_id: str, 
                                                 rating: int, feedback: str) -> Any:
        """Build a Solana transaction to rate a contribution"""
        # Placeholder for the actual transaction building logic
        
        # For demonstration purposes, we'll log the attempt
        logger.info(f"Would build transaction to rate contribution: id={contribution_id}, rating={rating}")
        
        # Simulate successful transaction creation
        return {
            "simulate": True,
            "contribution_id": contribution_id,
            "rating": rating,
            "feedback": feedback
        }
    
    async def _send_transaction(self, transaction: Any) -> Optional[str]:
        """Send a transaction to the Solana blockchain"""
        # In a real implementation, this would sign and send the transaction
        # and return the transaction signature
        
        # For demonstration purposes, just simulate a successful transaction
        if transaction.get("simulate"):
            # Return a fake transaction signature
            return f"simulated_tx_{int(time.time())}"
        
        return None


# Factory method to create blockchain logger instances
async def create_blockchain_logger(agent_id: str, config: Dict) -> Optional[BlockchainLogger]:
    """Create and initialize a blockchain logger"""
    rpc_url = config.get("rpc_url")
    private_key = config.get("private_key")
    
    logger_instance = BlockchainLogger(agent_id, rpc_url, private_key)
    connected = await logger_instance.connect()
    
    if connected:
        return logger_instance
    else:
        return None


# Example usage
async def test_blockchain_logger():
    config = {
        "rpc_url": "http://localhost:8899",
        "private_key": None  # In production, this would be a real private key
    }
    
    blockchain_logger = await create_blockchain_logger("test-agent", config)
    
    if blockchain_logger:
        # Log a contribution
        contribution_id = await blockchain_logger.log_contribution(
            "test-agent",
            "trace-123",
            content="This is a test contribution",
            message_type="TEST",
            metadata={"test": True, "importance": "high"}
        )
        
        if contribution_id:
            # Rate the contribution
            await blockchain_logger.rate_contribution(
                contribution_id,
                rating=8,
                feedback="Good quality contribution"
            )

if __name__ == "__main__":
    asyncio.run(test_blockchain_logger())