import os
from datetime import datetime, timezone
from github import Github

# Constants
START_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)  # Adjust this to your actual start date

def get_stored_times():
    # Example: Retrieve existing data from README.md
    stored_times = {}
    try:
        with open('README.md', 'r') as file:
            content = file.read()
            # Extract the section between language_times_start and language_times_end
            start = content.index("<!-- language_times_start -->")
            end = content.index("<!-- language_times_end -->")
            lang_section = content[start:end]
            for line in lang_section.splitlines()[2:]:  # Skip header lines
                parts = line.split()
                if len(parts) >= 2:
                    lang = parts[0]
                    time_str = parts[1]  # "XX hrs YY mins"
                    hours, mins = map(int, time_str.replace('hrs', '').replace('mins', '').split())
                    total_minutes = hours * 60 + mins
                    stored_times[lang] = total_minutes
    except Exception as e:
        print(f"Error reading stored times: {e}")
    
    return stored_times

def format_time(minutes):
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours} hrs {minutes} mins"

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
        # Update the section between language_times_start and language_times_end
        updated_content = content.replace(
            content[content.index("<!-- language_times_start -->"):content.index("<!-- language_times_end -->")],
            f'<!-- language_times_start -->\n{new_content}<!-- language_times_end -->'
        )
        file.seek(0)
        file.write(updated_content)
        file.truncate()

if __name__ == "__main__":
    new_times = {
        'JavaScript': 5700,  # Example: total time in minutes
        'TypeScript': 3450,
        'Java': 840,
        'PHP': 150,
        'Python': 120,
    }  # Populate this dictionary with your actual language times in minutes
    update_readme(new_times)
