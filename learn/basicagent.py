from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """ Get weather for a given city """
    return f"It's sunny in {city} today!"

agent = create_agent(
    model = "google_genai:gemini-2.5-flash-lite" , 
    tools = [get_weather] , 
    system_prompt = " Ypu are a helpful assistant"
)

result = agent.invoke(
    {
        "messages" :
        [
            {
                "role": "user",
                "content": "What is the weather like in JAipur?"
            }
        ]
    }
)

print(result["messages"][-1].content_blocks)