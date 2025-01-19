from telethon import TelegramClient
from supabase import create_client, Client
import asyncio
import os
import time
from datetime import datetime, timedelta
from asyncio import Lock
from pytz import timezone
import requests
from urllib.parse import quote
from datetime import datetime, timedelta

db_lock = Lock()

# Replace these with your own values from https://my.telegram.org
api_id = os.getenv('SEND_API_ID')
api_hash = os.getenv('SEND_API_HASH')

client = TelegramClient('send_session', api_id, api_hash)

# Replace 'testingbuffet' with your target group/channel username or ID
target_chat = 'testingbuffet'

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Define the message components
image_url = "https://example.com/image.jpg"  # Replace with actual image URL or path
location = "U-TOWN"  # Replace with extracted location
food_item = "Pizza, Pasta"  # Replace with extracted food items
clear_by = "5 PM today"  # Replace with clear-by time
organiser_status = "I am the organiser"  # or "I am not the organiser but organiser approved"

# Encode the URL
def encode_url(url):
    return quote(url, safe=":/")

# Construct the formatted message
formatted_message = f"""
📷 [Image]({image_url})

**Location:** {location}
**Food Item:** {food_item}
**Clear By:** {clear_by}
{organiser_status}
"""

# Initialize the Telegram client

async def send_message(image_url, message):
    async with db_lock:  # Ensure only one coroutine accesses the database at a time
        await client.start()

        # Validate and encode the image URL
        if image_url:
            image_url = encode_url(image_url)
            try:
                response = requests.head(image_url, timeout=5)  # Check if URL is valid
                if response.status_code != 200:
                    print(f"Invalid image URL: {image_url}")
                    image_url = None  # Mark image URL as invalid
            except Exception as e:
                print(f"Error validating image URL: {e}")
                image_url = None  # Mark image URL as invalid

        if image_url:
            # Send the image with the caption
            await client.send_file(target_chat, image_url, caption=message, link_preview=False)
        else:
            # Send only the message
            await client.send_message(target_chat, message, link_preview=False)


def get_latest_messages(last_poll_time):
    """Poll the database for messages created after the last poll time."""
    response = supabase.table("messages") \
        .select("*") \
        .gt("created_at", last_poll_time.isoformat()) \
        .eq("is_cleared", False) \
        .eq("is_sent_from_telegram", False) \
        .execute()
    return response.data



async def poll_database():
    last_poll_time = datetime.utcnow()  # Initialise the last poll time to the current time
    polling_interval = 5  # Polling interval in seconds
    sgt_tz = timezone('Asia/Singapore')  # Define Singapore Timezone

    while True:
        current_poll_time = datetime.utcnow()  # Current time at the start of this poll
        new_messages = get_latest_messages(last_poll_time)

        for message in new_messages:
            # Extract and format fields
            raw_message = message.get('raw_message', 'N/A')
            room_code = message.get('roomCode', 'N/A')
            dietary_restrictions = message.get('dietary_restrictions', "N/A")

            # Convert UTC to SGT for created_at
            created_at_utc = datetime.fromisoformat(message.get('created_at', ''))
            created_at_sgt = created_at_utc.astimezone(sgt_tz).strftime('%Y-%m-%d %H:%M:%S %Z')

            # Handle optional clear_by field
            clear_by_utc = message.get('clear_by')
            if clear_by_utc:
                clear_by_sgt = datetime.fromisoformat(clear_by_utc).astimezone(sgt_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                clear_by_sgt = "Not specified"

            image_url = message.get('image_url')

            # Construct the improved formatted message
            formatted_message = f"""
📄 **Description:** {raw_message}
🏢 **Location:** {room_code}
⏰ **Created At:** {created_at_sgt}
🕒 **Clear By:** {clear_by_sgt} 
🥗 **Dietary Restrictions:** {dietary_restrictions}
"""

            print("New message detected:", message)
            await send_message(image_url, formatted_message)  # Send the message with or without an image

        last_poll_time = current_poll_time  # Update the last poll time to the current poll time
        await asyncio.sleep(polling_interval)  # Wait for the next polling cycle
async def main():
    print("Starting polling for new messages...")
    try:
        await poll_database()
    except KeyboardInterrupt:
        print("Stopped polling.")

# Run the main loop
if __name__ == "__main__":
    asyncio.run(main())
