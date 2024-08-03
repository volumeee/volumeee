import requests
from collections import defaultdict
import os

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
        language = repo['language']
        commits = get_commits(repo_name)
        # Assuming each commit represents an hour of work (for simplicity)
        language_times[language] += len(commits)
    
    return language_times

def update_readme(language_times):
    with open(README_FILE, 'r') as f:
        readme_content = f.read()
    
    start_marker = '<!-- language_times_start -->'
    end_marker = '<!-- language_times_end -->'

    new_content = '## Time Spent on Projects by Dominant Language\n'
    for language, time in language_times.items():
        new_content += f'- **{language}**: {time} hours\n'

    if start_marker in readme_content and end_marker in readme_content:
        new_readme_content = readme_content.split(start_marker)[0] + start_marker + '\n' + new_content + '\n' + end_marker + readme_content.split(end_marker)[1]
    else:
        new_readme_content = readme_content + '\n' + start_marker + '\n' + new_content + '\n' + end_marker

    with open(README_FILE, 'w') as f:
        f.write(new_readme_content)

def main():
    language_times = calculate_time_spent()
    update_readme(language_times)

if __name__ == '__main__':
    main()
