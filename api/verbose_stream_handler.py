import asyncio
import re
import sys
import io
import queue
import threading
from contextlib import redirect_stdout, redirect_stderr
from typing import AsyncGenerator, Optional
from api.models import StreamMessage

class VerboseStreamCapture:
    """Capture and parse verbose output from Agent execution"""
    
    def __init__(self):
        self.sync_queue = queue.Queue()  # Thread-safe queue for sync context
        self.buffer = ""
        self.sent_thoughts = set()
        self.sent_actions = set()
        self.sent_observations = set()
        self.lock = threading.Lock()
        
    def put_message_sync(self, message: StreamMessage):
        """Put message into thread-safe queue"""
        self.sync_queue.put(message)
        
    async def get_message(self) -> Optional[StreamMessage]:
        """Get message from queue with timeout"""
        try:
            # Non-blocking get from sync queue
            return self.sync_queue.get_nowait()
        except queue.Empty:
            return None
    
    def parse_and_send_content(self, text: str):
        """Parse text content and extract meaningful parts"""
        self.buffer += text
        
        # Parse different patterns
        self._parse_thoughts()
        self._parse_actions()
        self._parse_observations()
        self._parse_final_answer()
    
    def _parse_thoughts(self):
        """Extract thought patterns"""
        # Look for thought patterns
        thought_patterns = [
            r'Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:|Observation:|\n\n|$))',
            r'> Entering new.*?\n(.+?)(?=\nAction:|$)',
            r'思考[：:]\s*(.+?)(?=\n|$)',
        ]
        
        for pattern in thought_patterns:
            matches = re.finditer(pattern, self.buffer, re.DOTALL | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                if content and content not in self.sent_thoughts and len(content) > 5:
                    self.sent_thoughts.add(content)
                    message = StreamMessage(type="thought", content=content)
                    self.put_message_sync(message)
    
    def _parse_actions(self):
        """Extract action patterns"""
        action_patterns = [
            r'Action:\s*(.+?)(?=\n)',
            r'Action Input:\s*(.+?)(?=\n)',
            r'正在使用工具[：:]\s*(.+?)(?=\n|$)',
        ]
        
        for pattern in action_patterns:
            matches = re.finditer(pattern, self.buffer, re.DOTALL | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                if content and content not in self.sent_actions:
                    self.sent_actions.add(content)
                    message = StreamMessage(type="action", content=f"执行: {content}")
                    self.put_message_sync(message)
    
    def _parse_observations(self):
        """Extract observation patterns"""
        observation_patterns = [
            r'Observation:\s*(.+?)(?=\nThought:|$)',
            r'工具执行结果[：:]\s*(.+?)(?=\n|$)',
        ]
        
        for pattern in observation_patterns:
            matches = re.finditer(pattern, self.buffer, re.DOTALL | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                if content and content not in self.sent_observations and len(content) > 5:
                    self.sent_observations.add(content)
                    # Truncate long observations
                    display_content = content[:200] + "..." if len(content) > 200 else content
                    message = StreamMessage(type="observation", content=display_content)
                    self.put_message_sync(message)
    
    def _parse_final_answer(self):
        """Extract final answer and stream it token by token"""
        final_patterns = [
            r'Final Answer:\s*(.+?)(?=\n> Finished|$)',
            r'最终答案[：:]\s*(.+?)(?=\n|$)',
        ]
        
        for pattern in final_patterns:
            matches = re.finditer(pattern, self.buffer, re.DOTALL | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    # Stream the final answer token by token
                    self._stream_text_as_tokens(content)
                    # Send done signal
                    done_message = StreamMessage(type="done", content="")
                    self.put_message_sync(done_message)
                    return
    
    def _stream_text_as_tokens(self, text: str):
        """Stream text as individual tokens/characters"""
        # Split text into words and punctuation for more natural streaming
        import re
        # Split by word boundaries but keep delimiters
        tokens = re.findall(r'\S+|\s+', text)
        
        for i, token in enumerate(tokens):
            if i == 0:
                # First token, send as response type
                message = StreamMessage(type="response", content=token)
                self.put_message_sync(message)
            else:
                # Subsequent tokens, send as token type
                message = StreamMessage(type="token", content=token)
                self.put_message_sync(message)

class StreamingStdoutCapture:
    """Custom stdout capture that processes output in real-time"""
    
    def __init__(self, stream_handler: VerboseStreamCapture):
        self.stream_handler = stream_handler
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
    def write(self, text: str):
        """Capture and process stdout writes"""
        # Also write to original stdout for debugging
        self.original_stdout.write(text)
        self.original_stdout.flush()
        
        # Process the text for streaming
        if text.strip():
            self.stream_handler.parse_and_send_content(text)
        
        return len(text)
    
    def flush(self):
        """Flush the stream"""
        self.original_stdout.flush()

async def run_agent_with_streaming(agent_chain, message: str) -> AsyncGenerator[StreamMessage, None]:
    """Run agent with verbose output streaming"""
    
    # Create stream capture
    stream_capture = VerboseStreamCapture()
    stdout_capture = StreamingStdoutCapture(stream_capture)
    
    # Create a task to run the agent
    async def agent_runner():
        try:
            # Redirect stdout to capture verbose output
            with redirect_stdout(stdout_capture):
                # Run agent in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: agent_chain.invoke({"input": message})
                )
                
                # If no final answer was captured, send the result
                if result and "output" in result:
                    final_message = StreamMessage(type="response", content=result["output"])
                    stream_capture.put_message_sync(final_message)
                    done_message = StreamMessage(type="done", content="")
                    stream_capture.put_message_sync(done_message)
                    
        except Exception as e:
            error_message = StreamMessage(type="error", content=f"执行错误: {str(e)}")
            stream_capture.put_message_sync(error_message)
            done_message = StreamMessage(type="done", content="")
            stream_capture.put_message_sync(done_message)
    
    # Start the agent task
    agent_task = asyncio.create_task(agent_runner())
    
    # Stream messages as they come
    done_received = False
    while not done_received:
        message_obj = await stream_capture.get_message()
        
        if message_obj:
            yield message_obj
            if message_obj.type == "done":
                done_received = True
        elif agent_task.done():
            # Agent finished but no done message, send one
            done_message = StreamMessage(type="done", content="")
            yield done_message
            done_received = True
        else:
            # Small delay to prevent busy waiting
            await asyncio.sleep(0.01)
    
    # Wait for agent to complete
    await agent_task
