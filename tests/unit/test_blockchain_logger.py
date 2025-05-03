import asyncio
import unittest
import json
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.shared.memory.blockchain_logger import BlockchainLogger, create_blockchain_logger


class TestBlockchainLogger(unittest.TestCase):
    """Test cases for Solana blockchain logger"""
    
    def setUp(self):
        # Create a mock for Solana AsyncClient
        self.solana_client_patcher = patch('solana.rpc.async_api.AsyncClient')
        self.solana_client_mock = self.solana_client_patcher.start()
        
        # Configure the mock
        self.client_instance = MagicMock()
        self.solana_client_mock.return_value = self.client_instance
        
        # Set up response for get_version
        version_future = asyncio.Future()
        version_future.set_result({"result": {"solana-core": "1.14.0"}})
        self.client_instance.get_version.return_value = version_future
        
        # Mock Keypair class
        self.keypair_patcher = patch('solana.keypair.Keypair')
        self.keypair_mock = self.keypair_patcher.start()
        
        # Configure keypair mock
        self.keypair_instance = MagicMock()
        self.keypair_mock.generate.return_value = self.keypair_instance
        self.keypair_instance.public_key = "mockedPublicKey12345"
        
        # Create event loop for async tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def tearDown(self):
        # Stop the patchers
        self.solana_client_patcher.stop()
        self.keypair_patcher.stop()
        
        # Close the event loop
        self.loop.close()
    
    def test_blockchain_logger_creation(self):
        """Test creating blockchain logger"""
        # Run the async test
        logger = self.loop.run_until_complete(
            create_blockchain_logger("test-agent", {"rpc_url": "http://localhost:8899"})
        )
        
        # Verify the result
        self.assertIsInstance(logger, BlockchainLogger)
        self.solana_client_mock.assert_called_once_with("http://localhost:8899")
        self.client_instance.get_version.assert_called_once()
        self.keypair_mock.generate.assert_called_once()
    
    def test_log_contribution(self):
        """Test logging a contribution to the blockchain"""
        # Create logger instance
        logger = BlockchainLogger("test-agent", "http://localhost:8899")
        logger.client = self.client_instance
        logger.keypair = self.keypair_instance
        logger.connected = True
        
        # Mock the internal methods
        logger._build_log_contribution_transaction = MagicMock(return_value={"simulate": True})
        logger._send_transaction = MagicMock(return_value=f"simulated_tx_{int(time.time())}")
        
        # Log a contribution
        result = self.loop.run_until_complete(
            logger.log_contribution(
                "test-agent",
                "trace-123",
                content="Test contribution",
                message_type="TEST",
                metadata={"test": True}
            )
        )
        
        # Verify the result
        self.assertTrue(result.startswith("simulated_tx_"))
        logger._build_log_contribution_transaction.assert_called_once()
        logger._send_transaction.assert_called_once_with({"simulate": True})
    
    def test_rate_contribution(self):
        """Test rating a contribution"""
        # Create logger instance
        logger = BlockchainLogger("test-agent", "http://localhost:8899")
        logger.client = self.client_instance
        logger.keypair = self.keypair_instance
        logger.connected = True
        
        # Mock the internal methods
        logger._build_rate_contribution_transaction = MagicMock(return_value={"simulate": True})
        logger._send_transaction = MagicMock(return_value=f"simulated_tx_{int(time.time())}")
        
        # Rate a contribution
        result = self.loop.run_until_complete(
            logger.rate_contribution(
                f"simulated_tx_{int(time.time())}",
                rating=8,
                feedback="Good contribution"
            )
        )
        
        # Verify the result
        self.assertTrue(result.startswith("simulated_tx_"))
        logger._build_rate_contribution_transaction.assert_called_once()
        logger._send_transaction.assert_called_once_with({"simulate": True})


if __name__ == '__main__':
    unittest.main()