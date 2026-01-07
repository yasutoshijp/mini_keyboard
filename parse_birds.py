from bs4 import BeautifulSoup
import json
import os
import re

# Use the full file
input_file = 'bird_list_full.html'
if not os.path.exists(input_file):
    print(f"Error: {input_file} not found.")
    exit(1)

with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('tr')
tokyo_birds = []
base_url = "https://www.bird-research.jp/1_shiryo/"

for row in rows:
    cols = row.find_all('td')
    if len(cols) >= 7:
        name_cell = cols[1]
        memo_cell = cols[2]
        location_cell = cols[4]
        mp3_cell = cols[6]
        
        # Get text, handling nested tags
        name = name_cell.get_text(strip=True)
        memo = memo_cell.get_text(strip=True)
        location = location_cell.get_text(strip=True)
        
        # Filter for Tokyo
        if "東京都" in location:
            mp3_link = mp3_cell.find('a')
            if mp3_link:
                href = mp3_link.get('href')
                if not href:
                    continue
                
                # Construct full URL
                if href.startswith('http'):
                    full_url = href
                else:
                    # Remove leading slash if any
                    href = href.lstrip('/')
                    full_url = base_url + href
                
                # Clean up name (remove newlines etc)
                name = re.sub(r'\s+', '', name)
                
                tokyo_birds.append({
                    "name": name,
                    "memo": memo,
                    "url": full_url,
                    "location": location,
                    "filename": os.path.basename(full_url).replace('.mp3', '.wav')
                })

# Deduplicate? If the same name exists, maybe append memo
# But the user said dial rotation plays bird names. 
# If there are 89 entries, maybe some names repeat.
# Let's keep them all for now and see.

print(f"Found {len(tokyo_birds)} bird recordings in Tokyo.")

with open('bird_songs.json', 'w', encoding='utf-8') as f:
    json.dump(tokyo_birds, f, ensure_ascii=False, indent=2)
