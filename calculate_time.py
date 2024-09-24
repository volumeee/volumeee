import os
from datetime import datetime, timezone
from github import Github

# Constants
START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)  # Adjust this to your actual start date

def get_stored_times():
    # Initialize with existing data from README.md or empty
    return {}

def format_time(minutes):
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"

def calculate_percentages(stored_times, total_time):
    return {lang: (time / total_time * 100 if total_time > 0 else 0) for lang, time in stored_times.items()}

def create_text_graph(percent):
    bar_length = 20
    filled_length = int(bar_length * percent // 100)
    return '█' * filled_length + '-' * (bar_length - filled_length)

def update_readme(new_times):
    stored_times = get_stored_times()
    for lang, minutes in new_times.items():
        stored_times[lang] = stored_times.get(lang, 0) + minutes
    
    total_time = sum(stored_times.values())
    percentages = calculate_percentages(stored_times, total_time)
    
    sorted_languages = sorted(stored_times.items(), key=lambda x: x[1], reverse=True)
    
    now = datetime.now(timezone.utc)
    start_date = START_DATE.strftime("%d %B %Y")
    end_date = now.strftime("%d %B %Y")
    
    new_content = f'```typescript\nFrom: {start_date} - To: {end_date}\n\nTotal Time: {format_time(total_time)}\n\n'
    
    for language, minutes in sorted_languages:
        time_str = format_time(minutes)
        percent = percentages[language]
        graph = create_text_graph(percent)
        new_content += f'{language:<18} {time_str:>14}  {graph} {percent:>7.2f}%\n'
    
    new_content += '```\n'
    
    # Update README.md
    with open('README.md', 'r+') as file:
        content = file.read()
        # Update logic to replace the old block with new_content here
        # This example assumes you're replacing a specific section
        new_file_content = content.replace('```typescript\n...', new_content)  # Update this to match your README structure
        file.seek(0)
        file.write(new_file_content)
        file.truncate()

if __name__ == "__main__":
    new_times = {}  # Populate this dictionary with your language times
    update_readme(new_times)
