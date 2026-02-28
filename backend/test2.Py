import os
from dotenv import load_dotenv
from mistralai import Mistral

load_dotenv()

client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

print("Testing Mistral stream structure...")
stream = client.chat.stream(
    model="ministral-8b-latest",
    messages=[{"role": "user", "content": "Count to 5"}],
)

for i, event in enumerate(stream):
    print(f"\n--- Event {i} ---")
    print(f"Event type: {type(event)}")
    print(f"Event dir: {[attr for attr in dir(event) if not attr.startswith('_')]}")
    print(f"Event: {event}")
    
    if i >= 3:  # Afficher seulement les 3 premiers événements
        print("...")
        break