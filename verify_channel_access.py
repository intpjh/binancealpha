import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

# Load environment variables
load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME", "new_listings_monitor")
source_bot_id_str = os.getenv("SOURCE_BOT_ID")

def parse_entity_id(entity_id_str):
    try:
        return int(entity_id_str)
    except ValueError:
        return entity_id_str

source_bot_id = parse_entity_id(source_bot_id_str)

async def main():
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.start()
    
    print(f"Checking access to: {source_bot_id}")
    try:
        # Get the entity to verify access
        entity = await client.get_entity(source_bot_id)
        print(f"Successfully found channel/entity: {entity.title if hasattr(entity, 'title') else entity.id}")
        
        # Fetch the latest message
        messages = await client.get_messages(entity, limit=1)
        if messages:
            last_msg = messages[0]
            print("\n✅ Success! Latest message read:")
            print(f"Date: {last_msg.date}")
            print(f"Content: {last_msg.text[:100]}...") # Show first 100 chars
        else:
            print("\n✅ Connection success, but the channel is empty.")
            
    except Exception as e:
        print(f"\n❌ Error: Could not access the channel. Reason: {e}")
        print("Please check if the account has joined the channel or if the ID/Username is correct.")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
