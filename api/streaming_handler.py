import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult
from api.models import StreamMessage

class StreamingCallbackHandler(BaseCallbackHandler):
    """Enhanced callback handler for real token-level streaming Agent responses"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.thoughts = []
        self.current_text = ""
        self.last_sent_position = 0
        self.current_stream_content = ""
        self.in_final_answer = False
        self.buffer_size = 5  # Send tokens in small chunks
        
    async def get_message(self) -> Optional[StreamMessage]:
        """Get the next message from the queue"""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
    
    def _put_message_safe(self, message: StreamMessage):
        """Safely put message in queue, handling both sync and async contexts"""
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            asyncio.create_task(self.queue.put(message))
        except RuntimeError:
            # No event loop running, we're in sync context
            # Store messages in a temporary list for later processing
            if not hasattr(self, '_pending_messages'):
                self._pending_messages = []
            self._pending_messages.append(message)
    
    async def _flush_pending_messages(self):
        """Flush any pending messages to the queue"""
        if hasattr(self, '_pending_messages'):
            for message in self._pending_messages:
                await self.queue.put(message)
            self._pending_messages.clear()
    
    def _parse_and_send_incremental_text(self, new_text: str):
        """Parse incremental text and send appropriate messages"""
        self.current_text += new_text
        
        # Look for complete patterns in the accumulated text
        patterns = [
            (r'Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:|$))', 'thought'),
            (r'Action:\s*(.+?)(?=\n)', 'action'),
            (r'Action Input:\s*(.+?)(?=\n)', 'action'),
            (r'Observation:\s*(.+?)(?=\n(?:Thought:|Final Answer:|$))', 'observation'),
            (r'Final Answer:\s*(.+?)(?=$)', 'response')
        ]
        
        for pattern, msg_type in patterns:
            matches = re.finditer(pattern, self.current_text, re.DOTALL | re.MULTILINE)
            for match in matches:
                content = match.group(1).strip()
                if content and content not in [t.get('content', '') for t in self.thoughts]:
                    if msg_type == 'thought':
                        self.thoughts.append({'type': msg_type, 'content': content})
                    
                    message = StreamMessage(type=msg_type, content=content)
                    self._put_message_safe(message)
                    
                    # If this is a final answer, send done signal
                    if msg_type == 'response':
                        done_message = StreamMessage(type="done", content="")
                        self._put_message_safe(done_message)
    
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""
        # Reset for new conversation
        self.current_text = ""
        self.last_sent_position = 0
        self.thoughts = []
        self.current_stream_content = ""
        self.in_final_answer = False
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. This is the key for real streaming."""
        if token:
            # Add token to current stream content
            self.current_stream_content += token
            
            # Check if we're in a final answer section
            if "Final Answer:" in self.current_stream_content and not self.in_final_answer:
                self.in_final_answer = True
                # Extract content after "Final Answer:"
                final_answer_start = self.current_stream_content.find("Final Answer:") + len("Final Answer:")
                self.current_stream_content = self.current_stream_content[final_answer_start:].strip()
            
            # If we're in final answer mode, stream tokens directly
            if self.in_final_answer:
                # Send token immediately for real-time streaming
                if token.strip():  # Only send non-whitespace tokens
                    message = StreamMessage(type="token", content=token)
                    self._put_message_safe(message)
            else:
                # For non-final answer content, use the existing parsing logic
                self._parse_and_send_incremental_text(token)
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        # Process any remaining text
        if hasattr(response, 'generations') and response.generations:
            for generation in response.generations:
                for gen in generation:
                    if hasattr(gen, 'text'):
                        self._parse_and_send_incremental_text(gen.text)
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Run when LLM errors."""
        message = StreamMessage(type="error", content=f"LLM Error: {str(error)}")
        self._put_message_safe(message)
    
    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Run when chain starts running."""
        pass
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Run when chain ends running."""
        # Ensure we send a done message if not already sent
        if "output" in outputs and not any(t.get('type') == 'response' for t in self.thoughts):
            content = outputs["output"]
            message = StreamMessage(type="response", content=content)
            self._put_message_safe(message)
            # Signal completion
            done_message = StreamMessage(type="done", content="")
            self._put_message_safe(done_message)
    
    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Run when chain errors."""
        message = StreamMessage(type="error", content=f"Chain Error: {str(error)}")
        self._put_message_safe(message)
    
    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        tool_name = serialized.get("name", "Unknown Tool")
        content = f"正在使用工具: {tool_name}"
        message = StreamMessage(type="action", content=content)
        self._put_message_safe(message)
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running."""
        content = f"工具执行结果: {output[:200]}..." if len(output) > 200 else f"工具执行结果: {output}"
        message = StreamMessage(type="observation", content=content)
        self._put_message_safe(message)
    
    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Run when tool errors."""
        message = StreamMessage(type="error", content=f"Tool Error: {str(error)}")
        self._put_message_safe(message)
    
    def on_text(self, text: str, **kwargs: Any) -> None:
        """Run on arbitrary text - enhanced parsing."""
        if text.strip():
            self._parse_and_send_incremental_text(text)
    
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Run on agent action."""
        content = f"执行动作: {action.tool}"
        if hasattr(action, 'tool_input') and action.tool_input:
            content += f" - {action.tool_input}"
        message = StreamMessage(type="action", content=content)
        self._put_message_safe(message)
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Run on agent end."""
        content = finish.return_values.get("output", "")
        if content:
            message = StreamMessage(type="response", content=content)
            self._put_message_safe(message)
        
        # Signal completion
        done_message = StreamMessage(type="done", content="")
        self._put_message_safe(done_message)
