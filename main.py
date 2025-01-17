import json
import re
import csv
from telethon import TelegramClient, events
from dotenv import load_dotenv
import os

load_dotenv()

# Replace these with your own values from https://my.telegram.org
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

client = TelegramClient('session_name', api_id, api_hash)

# Load venues.json
with open('venues.json', 'r') as venue_file:
    venues = json.load(venue_file)

# Preprocess venue names for flexible matching
venue_mapping = {}
venue_patterns = []

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

# CSV setup
csv_file = 'filtered_messages.csv'
fieldnames = ["raw_message", "roomCode", "longitude", "latitude"]

# Ensure the CSV has a header
with open(csv_file, 'w', newline='', encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

# Set to track processed messages
processed_messages = set()

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



# Event listener for new messages
@client.on(events.NewMessage(chats='testingbuffet'))
async def handler(event):
    raw_message = event.message.message.strip()  # Get the text of the incoming message

    # Avoid processing the same message multiple times
    if raw_message in processed_messages:
        return
    
        # Check if the message indicates food has been cleared
    if is_food_cleared(raw_message):
        print(f"Skipping message as it indicates food is cleared: '{raw_message}'")
        return  

    # Find the best match for the venue
    venue = find_best_match(raw_message)
    if venue:
        filtered_message = {
            "raw_message": raw_message,
            "roomCode": venue['roomCode'],
            "longitude": venue['coordinate']['longitude'],
            "latitude": venue['coordinate']['latitude']
        }

        # Append to CSV
        with open(csv_file, 'a', newline='', encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(filtered_message)

        print(f"Filtered message: {filtered_message}")


print("Listening for messages...")
client.start()
client.run_until_disconnected()
