from telethon import TelegramClient

# Replace these with your own values from https://my.telegram.org
api_id = '26531646'
api_hash = 'bdd2d8da1fda08be9a06d17cc9acee54'

# Replace 'testingbuffet' with your target group/channel username or ID
target_chat = 'testingbuffet'

# Define the message components
image_url = "https://example.com/image.jpg"  # Replace with actual image URL or path
location = "U-TOWN"  # Replace with extracted location
food_item = "Pizza, Pasta"  # Replace with extracted food items
clear_by = "5 PM today"  # Replace with clear-by time
organiser_status = "I am the organiser"  # or "I am not the organiser but organiser approved"


# Construct the formatted message
formatted_message = f"""
📷 [Image]({image_url})

**Location:** {location}
**Food Item:** {food_item}
**Clear By:** {clear_by}
{organiser_status}
"""

# Initialize the Telegram client
client = TelegramClient('session_name', api_id, api_hash)

async def send_message():
    await client.start()  # Ensure the client is started
    await client.send_message(target_chat, formatted_message, link_preview=False)  # Send the message with formatting
    print(f"Message sent to {target_chat}: {formatted_message}")

# Running the send_message function
with client:
    client.loop.run_until_complete(send_message())
