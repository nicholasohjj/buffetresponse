import json
import re
import csv

# Load venues.json
with open('venues.json', 'r') as venue_file:
    venues = json.load(venue_file)

# Extract room codes and room names from venues.json
venue_identifiers = []
venue_mapping = {}
for venue in venues:
    full_room_code = venue['roomCode'].lower()
    full_room_name = venue['roomName'].lower()
    venue_identifiers.append(re.escape(full_room_name))  # Use room names first
    venue_identifiers.append(re.escape(full_room_code))  # Add room codes later
    venue_mapping[full_room_code] = venue
    venue_mapping[full_room_name] = venue

# Sort identifiers by length to match longer ones first (specificity matters)
venue_identifiers.sort(key=len, reverse=True)

# Compile regex to handle spaces, punctuation, and strict matching
venue_pattern = re.compile(r'\b(' + '|'.join(venue_identifiers) + r')\b', re.IGNORECASE)

# Load messages.txt
with open('messages.txt', 'r') as message_file:
    messages = message_file.readlines()

# Prepare filtered messages
filtered_messages = []

for message in messages:
    match = venue_pattern.search(message)
    if match:
        matched_identifier = match.group(1).lower()
        venue = venue_mapping.get(matched_identifier, {})
        if venue:
            filtered_messages.append({
                "raw_message": message.strip(),
                "roomCode": venue['roomCode'],
                "longitude": venue['coordinate']['longitude'],
                "latitude": venue['coordinate']['latitude']
            })



# Save to CSV
with open('filtered_messages.csv', 'w', newline='') as csvfile:
    fieldnames = ["raw_message", "roomCode", "longitude", "latitude"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(filtered_messages)

print("Filtering complete. Check 'filtered_messages.csv' for results.")
