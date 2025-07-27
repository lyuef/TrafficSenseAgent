from rich import print
from typing import Any, List
from langchain.agents import Tool, create_react_agent, AgentExecutor
from langchain_openai import AzureChatOpenAI,ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from typing import Union

class ConversationBot:
    def __init__(
            self, llm: Union[ChatOpenAI,AzureChatOpenAI], toolModels: List,
            customedPrefix: str, verbose: bool = False
    ) -> Any:
        tools = []

        for ins in toolModels:
            """初始化工具链 每个ins是一个实现了inference方法的class"""
            func = getattr(ins, 'inference')
            # 增强工具描述，帮助ReAct更好地选择工具
            tools.append(
                Tool(
                    name=func.name,
                    description=func.description,
                    func=func
                )
            )
        # 使用ReAct Agent替代ZeroShotAgent
        self.agent_memory = ConversationBufferMemory(memory_key="chat_history")
        
        # 创建交通专业的prompt template
        traffic_react_template = """
{customedPrefix}

🚦 作为交通分析专家，请遵循以下推理模式：

You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do as a traffic expert. Consider:
- What traffic data or analysis is needed?
- What is the logical sequence of actions?
- Do I need current status before optimization?
- Should I verify results after changes?
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

🔍 交通分析最佳实践：
- 分析前先获取当前状态
- 优化前必须了解问题所在
- 优化后要验证改进效果
- 报告中要包含数据支撑和文件路径

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

        # 使用自定义模板
        prompt = PromptTemplate.from_template(traffic_react_template)
        prompt = prompt.partial(customedPrefix=customedPrefix)
        
        agent = create_react_agent(llm, tools, prompt)
        self.agent_chain = AgentExecutor(
            agent=agent, 
            tools=tools,
            verbose=verbose,
            memory=self.agent_memory,
            max_iterations=12, 
            early_stopping_method="generate",
            handle_parsing_errors="Use the LLM output directly as your final answer!"
        )
    def dialogue(self, input: str):
        print('TransGPT is running with ReAct reasoning, Please wait for a moment...')
        res = self.agent_chain.invoke(
                {"input":input}
            )
        # print('History: ', self.agent_memory.buffer)
        return res["output"]
