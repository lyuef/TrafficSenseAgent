#!/usr/bin/env python3
"""
Test script for streaming API functionality
"""
import asyncio
import json
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.agent_service import AgentService
from api.models import StreamMessage

async def test_streaming():
    """Test the streaming functionality"""
    print("🚀 Starting verbose streaming test...")
    
    try:
        # Initialize agent service
        agent_service = AgentService()
        print("✅ Agent service initialized")
        
        # Test message
        test_message = "回答我两个问题1.现在深圳龙华区的交通情况怎么样2.99*99 = ？"
        print(f"📝 Test message: {test_message}")
        print("=" * 50)
        
        # Stream the response
        message_count = 0
        message_types = {"thought": 0, "action": 0, "observation": 0, "response": 0, "token": 0, "error": 0}
        token_buffer = ""
        
        async for message in agent_service.chat_stream(test_message):
            message_count += 1
            message_types[message.type] = message_types.get(message.type, 0) + 1
            
            if message.type == "token":
                # Accumulate tokens for real-time display
                token_buffer += message.content
                print(message.content, end="", flush=True)
            else:
                # For non-token messages, display normally
                if token_buffer:
                    print()  # New line after tokens
                    token_buffer = ""
                
                # Truncate long content for display
                content = message.content[:100] + "..." if len(message.content) > 100 else message.content
                print(f"[{message_count}] {message.type.upper()}: {content}")
            
            if message.type == "done":
                if token_buffer:
                    print()  # Final new line
                print("=" * 50)
                print("✅ Streaming completed successfully!")
                print(f"📊 Message statistics: {message_types}")
                break
                
    except Exception as e:
        print(f"❌ Error during streaming test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Testing TrafficGPT Streaming API")
    print("=" * 50)
    
    # Run the test
    asyncio.run(test_streaming())
