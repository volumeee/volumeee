import requests
from collections import defaultdict
import os
from datetime import datetime, timedelta
import pytz

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "01 March 2020"

def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    repos = response.json()
    return repos

def get_repo_languages(repo_name):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    languages = response.json()
    return languages

def get_commits(repo_name, since_date, until_date):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    params = {'since': since_date.isoformat(), 'until': until_date.isoformat()}
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, params=params)
    commits = response.json()
    return commits

def calculate_time_spent(start_date, end_date):
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(float)
    total_bytes = 0
    
    for repo in repos:
        repo_name = repo['name']
        commits = get_commits(repo_name, start_date, end_date)
        
        if len(commits) > 0:  # Only consider repos with commits in the given time range
            languages = get_repo_languages(repo_name)
            repo_total_bytes = sum(languages.values())
            total_bytes += repo_total_bytes
            
            for language, bytes in languages.items():
                language_times[language] += bytes
    
    # Convert bytes to hours (assuming 100 bytes = 1 minute of coding time)
    hours_per_byte = 1 / (100 * 60)
    for language in language_times:
        language_times[language] *= hours_per_byte
    
    return language_times

def format_time(hours):
    h = int(hours)
    m = int((hours - h) * 60)
    return f'{h} hrs {m} mins'

def calculate_percentages(language_times, total_time):
    return {lang: (time / total_time) * 100 if total_time > 0 else 0 for lang, time in language_times.items()}

def create_text_graph(percent):
    bar_length = 20
    filled_length = int(bar_length * percent // 100)
    return '█' * filled_length + '░' * (bar_length - filled_length)

def update_readme(language_times, start_date, end_date):
    total_time = sum(language_times.values())
    percentages = calculate_percentages(language_times, total_time)
    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)
    
    duration = (end_date - start_date).days
    
    new_content = f'```typescript\nFrom: {start_date.strftime("%d %B %Y")} - To: {end_date.strftime("%d %B %Y")}\n\n'
    new_content += f'Total Time: {format_time(total_time)}  ({duration} days)\n\n'
    
    for language, time in sorted_languages:
        formatted_time = format_time(time)
        percent = percentages[language]
        graph = create_text_graph(percent)
        new_content += f'{language:<25} {formatted_time:<15} {graph} {percent:>6.2f} %\n'
    
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
    start_date = datetime.strptime(START_DATE, "%d %B %Y").replace(tzinfo=pytz.UTC)
    end_date = datetime.now(pytz.UTC)
    language_times = calculate_time_spent(start_date, end_date)
    update_readme(language_times, start_date, end_date)

if __name__ == '__main__':
    main()
