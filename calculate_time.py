import requests
from collections import defaultdict
import os

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

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

def main():
    language_times = calculate_time_spent()
    with open('language_times.md', 'w') as f:
        f.write('## Time Spent on Projects by Dominant Language\n')
        for language, time in language_times.items():
            f.write(f'- **{language}**: {time} hours\n')

if __name__ == '__main__':
    main()
