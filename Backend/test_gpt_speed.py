import time
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def test_simple_prompt():
    t0 = time.time()
    resp = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.0
    )
    print("Response:", resp.choices[0].message.content)
    print(f"Took {time.time()-t0:.3f} seconds")

if __name__ == "__main__":
    test_simple_prompt()
