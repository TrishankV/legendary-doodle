from langchain_core.tools import tool
# from langchain.chats_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from urllib import request , error
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent 
from deepagents import create_deep_agent 

SYSTEM_PROMPT = """You ae a literadtry data assitant 


## Capabilities
- 'fetchtextfromurl' : loads document text from a URL into a converstion
Do not guess line counts or posititons-ground them in tool results from the saved file 
"""

@tool
def fetchtextfromurl(url: str) -> str :
    """ Fetch the document from a URL
    """
    req = request.Request(
        url,
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
    )
    try:
        with request.urlopen(req, timeout = 120) as res :
            raw = res.read()
    except error.HTTPError as e :
        return f"Fetched failed : {e.code} {e.reason1}"
    text = raw.decode('utf-8' , errors = "replace")
    return text

checkpointer = InMemorySaver()

model = init_chat_model(
    "gemini-2.5-flash",
    model_provider="google_genai",
    temperature = 0.5 ,
    timeout = 600 , 
    max_tokens = 25000,
    streaming = True ,
)

agent = create_agent(
    model = model , 
    tools = [fetchtextfromurl] ,
    system_prompt = SYSTEM_PROMPT ,
    checkpointer = checkpointer ,
)

deep_agent = create_deep_agent(
    model = model , 
    tools = [fetchtextfromurl] ,
    system_prompt = SYSTEM_PROMPT ,
    checkpointer = checkpointer ,)

content = f"""Project Gutenberg hosts a full plain-text copy of F. Scott Fitzgerald's The Great Gatsby.
URL: https://www.gutenberg.org/files/64317/64317-0.txt

Answer as much as you can:

1) How many lines in the complete Gutenberg file contain the substring `Gatsby` (count lines, not occurrences within a line, each line ends with a line break).
2) The 1-based line number of the first line in the file that contains `Daisy`.
3) A two-sentence neutral synopsis.

Do your best on (1) and (2). If at any point you realize you cannot **verify** an exact answer with
your available tools and reasoning, do not fabricate numbers: use `null` for that field and spell out
the limitation in `how_you_computed_counts`. If you encounter any errors please report what the error was and what the error message was."""


agent_result = agent.invoke(
    {"messages": [{"role": "user", "content": content}]} ,
    config={"configurable": {"thread_id": "great-gatsby-lc"}}
)

deep_agent_result = deep_agent.invoke(
    {"messages": [{"role": "user", "content": content}]},
    config={"configurable": {"thread_id": "great-gatsby-da"}},
)
print(agent_result["messages"][-1].content_blocks)
print("\n")
print(deep_agent_result["messages"][-1].content_blocks)