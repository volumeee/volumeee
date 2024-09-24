import requests
from collections import defaultdict
import os
from datetime import datetime, timedelta
import pytz

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "13 March 2022"  # Customizable start date

def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    repos = response.json()
    return repos

def get_commits(repo_name, since_date):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    params = {'since': since_date.isoformat()}
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, params=params)
    commits = response.json()
    return commits

def calculate_time_spent(since_date):
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(int)
    for repo in repos:
        repo_name = repo['name']
        language = repo['language'] if repo['language'] else 'Unknown'
        commits = get_commits(repo_name, since_date)
        # Estimate time spent: 30 minutes per commit
        language_times[language] += len(commits) * 0.5
    
    return language_times

def format_time(hours):
    h = int(hours)
    m = int((hours - h) * 60)
    return f'{h} hrs {m} mins'

def calculate_percentages(language_times, total_time):
    percentages = {}
    for language, time in language_times.items():
        percentages[language] = (time / total_time) * 100 if total_time > 0 else 0
    return percentages

def create_text_graph(percent):
    bar_length = 20
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    return bar

def update_readme(language_times, start_date, end_date):
    total_time = sum(language_times.values())
    percentages = calculate_percentages(language_times, total_time)
    formatted_time = {lang: format_time(time) for lang, time in language_times.items()}
    formatted_percentages = {lang: f'{percent:.2f} %' for lang, percent in percentages.items()}
    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)
    
    duration = (end_date - start_date).days
    new_content = f'```typescript\nFrom: {start_date.strftime("%d %B %Y")} - To: {end_date.strftime("%d %B %Y")}\n\nTotal Time: {format_time(total_time)}  ({duration} days)\n\n'
    for language, time in sorted_languages:
        percent = (time / total_time) * 100 if total_time > 0 else 0
        graph = create_text_graph(percent)
        new_content += f'{language:<25} {formatted_time[language]:<10} {graph:>20} {formatted_percentages[language]:>8}\n'
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
    wib = pytz.timezone('Asia/Jakarta')
    start_date = datetime.strptime(START_DATE, "%d %B %Y").replace(tzinfo=wib)
    end_date = datetime.now(wib)
    
    language_times = calculate_time_spent(start_date)
    update_readme(language_times, start_date, end_date)

if __name__ == '__main__':
    main()
