import requests
from collections import defaultdict
import os
from datetime import datetime, timezone
import re

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)

def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    repos = response.json()
    return repos

def get_commits(repo_name, since):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    params = {'since': since.isoformat()}
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, params=params)
    commits = response.json()
    return commits

def get_last_update_time():
    with open(README_FILE, 'r') as f:
        content = f.read()
    match = re.search(r'From: .* - To: (.*)', content)
    if match:
        last_update = datetime.strptime(match.group(1), "%d %B %Y").replace(tzinfo=timezone.utc)
        return last_update
    return START_DATE

def get_stored_times():
    with open(README_FILE, 'r') as f:
        content = f.read()
    stored_times = {}
    for line in content.split('\n'):
        match = re.match(r'(\w+)\s+(\d+) hrs (\d+) mins', line)
        if match:
            language, hours, minutes = match.groups()
            stored_times[language] = int(hours) * 60 + int(minutes)
    return stored_times

def calculate_time_spent(since):
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(int)
    for repo in repos:
        repo_name = repo['name']
        language = repo['language'] if repo['language'] else 'Unknown'
        commits = get_commits(repo_name, since)
        language_times[language] += len(commits)
    
    return {lang: count * 30 for lang, count in language_times.items()}

def format_time(minutes):
    h = minutes // 60
    m = minutes % 60
    return f'{h} hrs {m} mins'

def calculate_percentages(language_times, total_time):
    return {lang: (time / total_time) * 100 for lang, time in language_times.items()}

def create_text_graph(percent):
    bar_length = 20
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    return bar

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
    
    with open(README_FILE, 'r') as f:
        readme_content = f.read()
    
    start_marker = '<!-- language_times_start -->'
    end_marker = '<!-- language_times_end -->'
    if start_marker in readme_content and end_marker in readme_content:
        new_readme_content = readme_content.split(start_marker)[0] + start_marker + '\n' + new_content + end_marker + readme_content.split(end_marker)[1]
    else:
        new_readme_content = readme_content + '\n' + start_marker + '\n' + new_content + end_marker
    
    with open(README_FILE, 'w') as f:
        f.write(new_readme_content)

def main():
    last_update = get_last_update_time()
    new_times = calculate_time_spent(last_update)
    update_readme(new_times)

if __name__ == '__main__':
    main()
