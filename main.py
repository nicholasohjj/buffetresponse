import json
import re
import csv
import os
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from dotenv import load_dotenv
from supabase import create_client, Client
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image


load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram configuration
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
client = TelegramClient('session_name', api_id, api_hash)

# Directory to save images
IMAGE_SAVE_PATH = 'images/'
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

# Initialise the BLIP image captioning model
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

# Load venues.json
with open('venues.json', 'r') as venue_file:
    venues = json.load(venue_file)

# Preprocess venue names for flexible matching
venue_mapping = {}
venue_patterns = []

# Supabase realtime event handler
def handle_realtime_update(payload):
    print("Realtime update received:", payload)

    # Extract new message details
    new_message = payload['new']
    if not new_message or new_message.get("is_sent_from_telegram", True):
        return  # Ignore already processed messages

    raw_message = new_message['raw_message']
    venue = find_best_match(raw_message)
    file_url = new_message.get("image_url")
    image_description = new_message.get("image_description")

    if venue:
        # Update message with venue details
        updated_data = {
            "roomCode": venue['roomCode'],
            "longitude": venue['coordinate']['longitude'],
            "latitude": venue['coordinate']['latitude'],
            "is_sent_from_telegram": True
        }

        supabase.table('messages').update(updated_data).eq("id", new_message['id']).execute()
        print(f"Processed realtime message ID {new_message['id']} and updated with venue info.")
    else:
        print(f"No venue matched for realtime message ID {new_message['id']}.")


def is_food_cleared(message):
    clearance_patterns = [
        r'\b(food|snacks|refreshments) (is|are) (cleared|gone|finished|unavailable|out)\b',
        r'\bcleared\b',
        r'\bno (food|snacks|refreshments)\b',
        r'\b(nothing|none) (left|available)\b'
    ]
    for pattern in clearance_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    return False

for venue in venues:
    room_code = venue['roomCode'].lower()
    normalised_code = re.sub(r'[^a-z0-9]', '', room_code)  # Remove spaces, dashes, etc.
    venue_mapping[normalised_code] = venue

    # Create regex patterns for flexible matching
    patterns = [
        room_code,                    # Original room code
        re.sub(r'\s+', '', room_code),  # Remove spaces
        re.sub(r'[^a-z0-9]', '', room_code)  # Remove non-alphanumeric characters
    ]
    venue_patterns.append((set(patterns), venue))

# Helper function to normalise and match messages dynamically
def find_best_match(message):
    original_message = message.strip().replace('-', ' ')

    venue_code_pattern = r'[a-z]{2,4}-\d{1,2}-\d{1,4}'  # Removed \b
    building_code_pattern = r'\b[a-z]{2,4}\d{0,2}\b' # Matches E4A, AS8, E4A8 etc.

    # Extract full venue codes first
    extracted_venue_codes = re.findall(venue_code_pattern, original_message, re.IGNORECASE)

    # Remove matched venue codes from the message to prevent overlap (still useful even if only one match)
    remaining_message = re.sub(venue_code_pattern, '', original_message, flags=re.IGNORECASE)

    # Extract building codes from the remaining message
    extracted_building_codes = re.findall(building_code_pattern, remaining_message, re.IGNORECASE)

    print(f"Original message: '{original_message}'")
    print(f"Extracted building codes: {extracted_building_codes}")
    print(f"Extracted venue codes: {extracted_venue_codes}")

    # Step 1: Match extracted venue codes
    for code in extracted_venue_codes:
        normalised_code = re.sub(r'[^a-z0-9]', '', code.lower())
        for venue in venues:
            patterns = {venue['roomCode'].lower(), re.sub(r'[^a-z0-9]', '', venue['roomCode'].lower())}
            if 'aliases' in venue:
                for alias in venue['aliases']:
                    alias_normalised = re.sub(r'[^a-z0-9]', '', alias.lower())
                    patterns.add(alias_normalised)

            if normalised_code in patterns:
                print(f"Matched venue code '{code}' to venue '{venue['roomCode']}'")
                return venue

    # Step 2: Match extracted building codes
    for code in extracted_building_codes:
        normalised_code = code.lower()
        for venue in venues:
            building_code = venue['roomCode'].split('-')[0].lower()
            if normalised_code == building_code:
                print(f"Matched building code '{code}' to venue '{venue['roomCode']}'")
                return venue

    # Step 3: Fallback to token combination logic
    cleaned_message = re.sub(r'[^a-z0-9\s]', '', original_message.lower())
    tokens = cleaned_message.split()

    # Generate token combinations
    token_combinations = set(tokens)  # Single tokens
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens) + 1):
            token_combinations.add(''.join(tokens[i:j]))

    print(f"Token combinations: {token_combinations}")

    for venue in venues:
        patterns = {venue['roomCode'].lower(), re.sub(r'[^a-z0-9]', '', venue['roomCode'].lower())}
        if 'aliases' in venue:
            for alias in venue['aliases']:
                alias_normalised = re.sub(r'[^a-z0-9]', '', alias.lower())
                patterns.add(alias_normalised)

        if any(combination in patterns for combination in token_combinations):
            print(f"Matched token combination to venue '{venue['roomCode']}'")
            return venue

    print(f"No match found for '{original_message}'")
    return None

async def upload_to_supabase(file_path, file_name):
    """Upload a file to Supabase storage."""
    try:
        with open(file_path, 'rb') as file:
            supabase.storage.from_('images').upload(f"images/{file_name}", file)
            response = supabase.storage.from_("images").get_public_url(f"images/{file_name}")
            return response


    except Exception as e:
        print(f"Error uploading to Supabase: {e}")
        return None

async def describe_food_in_image(image_path):
    """Generate a description focusing on food in the image."""
    try:
        image = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        outputs = model.generate(**inputs)
        description = processor.decode(outputs[0], skip_special_tokens=True)
        return description
    except Exception as e:
        print(f"Error describing food: {e}")
        return None


# Event listener for new messages
@client.on(events.NewMessage(chats='testingbuffet'))
async def handler(event):
    if event.sender.username == 'usernamename123':
        print(f"Skipping message from ignored user: {event.sender.username}")
        return  # Ignore the message
    
    raw_message = event.message.message.strip()  # Get the text of the incoming message
    
        # Check if the message indicates food has been cleared
    if is_food_cleared(raw_message):
        print(f"Skipping message as it indicates food is cleared: '{raw_message}'")
        return  

    # Find the best match for the venue
    venue = find_best_match(raw_message)

    file_url = None
    image_description = None

    if event.message.media and isinstance(event.message.media, MessageMediaPhoto) and venue:
        image_file_path = f"{event.message.id}.jpg"
        await client.download_media(event.message.media, file=image_file_path)
        print(f"Image downloaded: {image_file_path}")
        file_url = await upload_to_supabase(image_file_path, f"{event.message.id}.jpg")

        print("Uploaded")
        image_description = await describe_food_in_image(image_file_path)

        print("Image", image_description)

        os.remove(image_file_path)  # Clean up after upload

    if venue:
        data = {
            "raw_message": raw_message,
            "roomCode": venue['roomCode'],
            "longitude": venue['coordinate']['longitude'],
            "latitude": venue['coordinate']['latitude'],
            "image_url": file_url,
            "image_description": image_description,
            "is_sent_from_telegram": True
        }

        # Insert data into Supabase
        try:
            response = supabase.table('messages').insert(data).execute()
        except Exception as e:
            print(f"Failed to insert data: {e}")



print("Listening for messages...")
client.start()
client.run_until_disconnected()
