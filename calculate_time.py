import os
from datetime import datetime, timezone
from github import Github

# Constants
START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)  # Adjust this to your actual start date

def get_stored_times():
    stored_times = {}
    with open('README.md', 'r') as file:
        content = file.read()
        if '<!-- language_times_start -->' in content:
            start_index = content.index('<!-- language_times_start -->') + len('<!-- language_times_start -->')
            end_index = content.index('<!-- language_times_end -->')
            times_section = content[start_index:end_index].strip()
            for line in times_section.splitlines():
                parts = line.split()
                if len(parts) >= 2:  # Changed to allow at least language and time
                    lang = parts[0]
                    time_str = parts[1]
                    try:
                        hours, minutes = map(int, time_str.split('hrs'))
                        total_minutes = hours * 60 + minutes
                        stored_times[lang] = stored_times.get(lang, 0) + total_minutes
                    except ValueError:
                        print(f"Skipping line due to format error: {line}")
    return stored_times

def fetch_language_times(token):
    g = Github(token)
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
    total_times = {}
    for commit in repo.get_commits():
        languages = commit.get_stats().get('additions', {})
        for lang, count in languages.items():
            total_times[lang] = total_times.get(lang, 0) + count  # Aggregate usage
    return total_times

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
    
    with open('README.md', 'r+') as file:
        content = file.read()
        new_file_content = content.replace(content[content.index('<!-- language_times_start -->'):content.index('<!-- language_times_end -->')], new_content)
        file.seek(0)
        file.write(new_file_content)
        file.truncate()

if __name__ == "__main__":
    token = os.getenv('GH_TOKEN')
    new_times = fetch_language_times(token)
    update_readme(new_times)
