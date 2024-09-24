import requests
from collections import defaultdict
import os
from datetime import datetime

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'

def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    repos = response.json()
    return repos

def get_commits(repo_name):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
    commits = response.json()
    return commits

def calculate_time_spent():
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(int)

    for repo in repos:
        repo_name = repo['name']
        language = repo['language'] if repo['language'] else 'Unknown'
        commits = get_commits(repo_name)
        # Count the number of commits as hours
        language_times[language] += len(commits)
    
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

def update_readme(language_times):
    total_time = sum(language_times.values())
    percentages = calculate_percentages(language_times, total_time)

    formatted_time = {lang: format_time(time) for lang, time in language_times.items()}
    formatted_percentages = {lang: f'{percent:.2f} %' for lang, percent in percentages.items()}

    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)

    now = datetime.now()
    start_date = "13 March 2022"
    end_date = now.strftime("%d %B %Y")
    duration = (end_date - start_date).days

    new_content = f'```typescript\nFrom: {start_date} - To: {end_date}\n\nTotal Time: {format_time(total_time)}  ({duration} days)\n\n'
    for language, time in sorted_languages:
        percent = (time / total_time) * 100 if total_time > 0 else 0
        graph = create_text_graph(percent)
        new_content += f'{language:<25} {formatted_time[language]} {graph} {formatted_percentages[language]:>8}\n'
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
    language_times = calculate_time_spent()
    update_readme(language_times)

if __name__ == '__main__':
    main()

