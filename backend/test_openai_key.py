import os
from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv

async def test_openai_key():
    # Load environment variables from .env file
    load_dotenv()
    
    # Load API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment variables")
        return
    
    print(f"API Key found (first 10 chars): {api_key[:10]}...")
    
    try:
        client = AsyncOpenAI(api_key=api_key)
        
        print("Testing OpenAI API with a simple 'hi' message...")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "hi"}
            ],
            max_tokens=50
        )
        
        reply = response.choices[0].message.content
        print(f"SUCCESS! OpenAI API responded: {reply}")
        
    except Exception as e:
        print(f"ERROR: OpenAI API call failed")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_openai_key())
