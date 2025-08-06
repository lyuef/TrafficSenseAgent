import os
import yaml
import asyncio
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from TrafficSense.TrafficTools import (
    demo_longhua_result,
    demo_longhua_simulation,
    demo_longhua_solution
)
from TrafficSense.Conversationbot import ConversationBot
from api.streaming_handler import StreamingCallbackHandler
from api.verbose_stream_handler import run_agent_with_streaming

class AgentService:
    """Service class to manage the Traffic Analysis Agent"""
    
    def __init__(self):
        self.bot = None
        self.streaming_handler = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the LLM and ConversationBot"""
        # Load configuration
        OPENAI_CONFIG = yaml.load(open('config.yaml'), Loader=yaml.FullLoader)
        
        # Initialize LLM based on config with streaming enabled
        if OPENAI_CONFIG['OPENAI_API_TYPE'] == 'azure':
            os.environ["OPENAI_API_TYPE"] = OPENAI_CONFIG['OPENAI_API_TYPE']
            os.environ["OPENAI_API_VERSION"] = OPENAI_CONFIG['AZURE_API_VERSION']
            os.environ["OPENAI_API_BASE"] = OPENAI_CONFIG['AZURE_API_BASE']
            os.environ["OPENAI_API_KEY"] = OPENAI_CONFIG['AZURE_API_KEY']
            llm = AzureChatOpenAI(
                azure_deployment=OPENAI_CONFIG['AZURE_MODEL'],
                temperature=0,
                max_tokens=4096,
                request_timeout=60,
                streaming=True  # Enable streaming
            )
        elif OPENAI_CONFIG['OPENAI_API_TYPE'] == 'openai':
            os.environ["OPENAI_API_KEY"] = OPENAI_CONFIG['OPENAI_KEY']
            llm = ChatOpenAI(
                temperature=0,
                model='gpt-3.5-turbo-16k-0613',
                max_tokens=4096,
                request_timeout=60,
                streaming=True  # Enable streaming
            )
        elif OPENAI_CONFIG['OPENAI_API_TYPE'] == 'openrouter':
            os.environ["OPENAI_API_KEY"] = OPENAI_CONFIG['OPENROUTER_API_KEY']
            os.environ["OPENAI_API_BASE"] = OPENAI_CONFIG['OPENROUTER_API_BASE']
            llm = ChatOpenAI(
                temperature=0,
                model=OPENAI_CONFIG['OPENROUTER_MODEL'],
                max_tokens=4096,
                request_timeout=60,
                openai_api_base=OPENAI_CONFIG['OPENROUTER_API_BASE'],
                openai_api_key=OPENAI_CONFIG['OPENROUTER_API_KEY'],
                streaming=True  # Enable streaming
            )
        
        # Initialize tools
        toolModels = [
            demo_longhua_solution(),
            demo_longhua_simulation(),
            demo_longhua_result()
        ]
        
        # Bot prefix (same as original)
        botPrefix = """
[WHO ARE YOU]
You are a AI to assist human with traffic simulation control, making traffic and transportation decisions, or providing traffic analysis reports. Although you have access to a set of tools, your abilities are not limited to the tools at your disposal
[YOUR ACTION GUIDLINES]
1. You need to determine whether the human message is a traffic simulation control command or a question before making any move. If it is a traffic simulation control command, just execute the command and don't do any further information analysis. If
2. You need to remeber the human message exactly. Your only purpose is to complete the task that is explicitly expressed in the human message. 
3. Whenever you are about to come up with a thought, recall the human message to check if you already have enough information for the final answer. If so, you shouldn't infer or fabricate any more needs or questions based on your own ideas. 
4. Remember what tools you have used, DONOT use the same tool repeatedly. Try to use the least amount of tools.
5. If you can not find any appropriate tool for your task, try to do it using your own ability and knowledge as a chat AI. 
6. When you encounter tabular content in Observation, make sure you output the tabular content in markdown format into your final answer.
7. When you realize that existing tools are not solving the problem at hand, you need to end your actions and ask the human for more information as your final answer.
[THINGS YOU CANNOT DO]
You are forbidden to fabricate any tool names. 
You are forbidden to fabricate any input parameters when calling tools!
[HOW TO GENERATE TRAFFIC REPORTS]
Act as a human. And provide as much information as possible, including file path and tabular datasets.
When human need to provede a report of the traffic situation of a road network, they usually start by observing the operation of the network, 
find a few intersections in the network that are in a poor operating condition, as well as their locations, try to optimize them, 
and evaluate which parameters have become better and which ones are worse after the optimization. And form a report of the complete thought process in markdown format.
For example:
Macroscopic traffic operations on the entire road network can be viewed on the basis of road network heatmaps: 'replace the correct filepath here'.
To be more specific, these 5 intersections are in the worst operation status.
|    |   Juction_id |   speed_avg |   volume_avg |   timeLoss_avg |
|---:|-------------:|------------:|-------------:|---------------:|
|  0 |         4605 |     8.02561 |       734.58 |        8155.83 |
|  1 |         4471 |     8.11299 |       797.92 |       16500.6  |
|  2 |         4493 |     8.36199 |       532.26 |        8801.71 |
|  3 |         4616 |     8.62853 |       898.08 |        5897.33 |
|  4 |         4645 |     9.38659 |       360.03 |       11689    |
the locations of these intersections are shown in the map: 'replace the correct filepath here'.
I tried to optimize the traffic signal shceme of them and run the simulation again.
The new traffic stauts of these 5 intersections are as follows:
|    |   Juction_id |   speed_avg |   volume_avg |   timeLoss_avg |
|---:|-------------:|------------:|-------------:|---------------:|
|  0 |         4605 |     5.02561 |      1734.58 |        9155.83 |
|  1 |         4471 |     5.11299 |      1797.92 |       17500.6  |
|  2 |         4493 |     5.36199 |      1532.26 |        9901.71 |
|  3 |         4616 |     5.62853 |      1898.08 |        6897.33 |
|  4 |         4645 |     5.38659 |      1360.03 |       13689    |
According to the data above, after optimization, Traffic volume has increased at these intersections, but average speeds have slowed and time loss have become greater.
"""
        
        # Initialize ConversationBot
        self.bot = ConversationBot(llm, toolModels, botPrefix, verbose=True)
    
    async def chat_stream(self, message: str):
        """Process message with true LangChain astream_events for token streaming"""
        from api.models import StreamMessage
        
        # Track current agent state to determine token type
        current_state = "thinking"  # thinking, acting, responding
        accumulated_content = ""
        
        # Use LangChain's astream_events for true token-level streaming
        async for event in self.bot.agent_chain.astream_events(
            {"input": message}, 
            version="v2"
        ):
            event_type = event["event"]
            
            # Stream LLM tokens in real-time with appropriate type
            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, 'content') and chunk.content:
                    accumulated_content += chunk.content
                    
                    # Determine token type based on current state and content
                    token_type = self._determine_token_type(accumulated_content, current_state)
                    
                    # Update state based on content patterns
                    if "Action:" in accumulated_content:
                        current_state = "acting"
                    elif "Final Answer:" in accumulated_content:
                        current_state = "responding"
                    elif "Thought:" in accumulated_content:
                        current_state = "thinking"
                    
                    yield StreamMessage(type=token_type, content=chunk.content)
            
            # Capture agent thoughts
            elif event_type == "on_chain_start" and "AgentExecutor" in event.get("name", ""):
                current_state = "thinking"
                yield StreamMessage(type="thought_start", content="开始思考...")
            
            # Capture tool calls
            elif event_type == "on_tool_start":
                current_state = "acting"
                tool_name = event.get("name", "Unknown")
                yield StreamMessage(type="action_start", content=f"调用工具: {tool_name}")
            
            # Capture tool results
            elif event_type == "on_tool_end":
                output = event["data"].get("output", "")
                # Truncate long outputs
                display_output = output[:200] + "..." if len(output) > 200 else output
                yield StreamMessage(type="observation", content=f"工具结果: {display_output}")
                current_state = "thinking"  # Back to thinking after tool execution
            
            # Capture final result
            elif event_type == "on_chain_end" and "AgentExecutor" in event.get("name", ""):
                output = event["data"].get("output", {})
                if isinstance(output, dict) and "output" in output:
                    yield StreamMessage(type="response_complete", content=output["output"])
                elif isinstance(output, str):
                    yield StreamMessage(type="response_complete", content=output)
                
                # Send completion signal
                yield StreamMessage(type="done", content="")
                break
            
            # Handle errors
            elif event_type == "on_chain_error":
                error_msg = str(event["data"].get("error", "Unknown error"))
                yield StreamMessage(type="error", content=f"执行错误: {error_msg}")
                yield StreamMessage(type="done", content="")
                break
    
    def _determine_token_type(self, accumulated_content: str, current_state: str) -> str:
        """Determine the appropriate token type based on content and state"""
        # Check for specific patterns in the accumulated content
        if "Thought:" in accumulated_content and not ("Action:" in accumulated_content or "Final Answer:" in accumulated_content):
            return "thought_token"
        elif "Action:" in accumulated_content and "Final Answer:" not in accumulated_content:
            return "action_token"
        elif "Final Answer:" in accumulated_content:
            return "response_token"
        else:
            # Fallback to current state
            if current_state == "thinking":
                return "thought_token"
            elif current_state == "acting":
                return "action_token"
            elif current_state == "responding":
                return "response_token"
            else:
                return "token"  # Generic fallback
    
    async def _run_agent(self, message: str):
        """Run the agent in an async context"""
        loop = asyncio.get_event_loop()
        # Run the synchronous agent in a thread pool
        result = await loop.run_in_executor(None, self.bot.dialogue, message)
        return result
    
    def chat_sync(self, message: str) -> Dict[str, Any]:
        """Process message synchronously (non-streaming)"""
        try:
            # Capture thoughts by temporarily storing them
            original_memory = self.bot.agent_memory.buffer
            
            # Get response
            response = self.bot.dialogue(message)
            
            # Get updated memory for thoughts
            new_memory = self.bot.agent_memory.buffer
            thoughts = new_memory[len(original_memory):] if len(new_memory) > len(original_memory) else ""
            
            return {
                "response": response,
                "thoughts": thoughts,
                "status": "success"
            }
        except Exception as e:
            return {
                "response": f"Error processing request: {str(e)}",
                "thoughts": "",
                "status": "error"
            }
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.bot.agent_memory.clear()
        return {"status": "success", "message": "Conversation history cleared"}
