import requests
from collections import defaultdict
import os
from datetime import datetime, timezone
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)

def get_repos(username):
    url = f'https://api.github.com/user/repos'
    params = {'type': 'all', 'per_page': 100}
    repos = []
    while url:
        try:
            response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, params=params)
            response.raise_for_status()
            repos.extend(response.json())
            url = response.links.get('next', {}).get('url')
        except requests.RequestException as e:
            logger.error(f"Error fetching repos: {e}")
            return []
    return repos

def get_commits(repo_name, since):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    params = {'since': since.isoformat()}
    try:
        response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'}, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching commits for {repo_name}: {e}")
        return []

def get_commit_details(repo_name, commit_sha):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits/{commit_sha}'
    try:
        response = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching commit details for {repo_name}/{commit_sha}: {e}")
        return None

def get_file_language(filename):
    extension = os.path.splitext(filename)[1].lower()
    language_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.html': 'HTML',
        '.css': 'CSS',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.go': 'Go',
        '.rs': 'Rust',
        '.ts': 'TypeScript',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.scala': 'Scala',
        '.m': 'Objective-C',
        '.sh': 'Shell',
        '.pl': 'Perl',
        '.r': 'R',
        '.lua': 'Lua'
    }
    return language_map.get(extension, 'Other')

def get_last_update_time():
    try:
        with open(README_FILE, 'r') as f:
            content = f.read()
        match = re.search(r'From: .* - To: (.*)', content)
        if match:
            last_update = datetime.strptime(match.group(1), "%d %B %Y").replace(tzinfo=timezone.utc)
            return last_update
    except Exception as e:
        logger.error(f"Error getting last update time: {e}")
    return START_DATE

def get_stored_times():
    try:
        with open(README_FILE, 'r') as f:
            content = f.read()
        stored_times = {}
        for line in content.split('\n'):
            match = re.match(r'(\w+)\s+(\d+) hrs (\d+) mins', line)
            if match:
                language, hours, minutes = match.groups()
                stored_times[language] = int(hours) * 60 + int(minutes)
        return stored_times
    except Exception as e:
        logger.error(f"Error getting stored times: {e}")
        return {}

def calculate_time_spent(since):
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(int)
    for repo in repos:
        repo_name = repo['name']
        commits = get_commits(repo_name, since)
        for commit in commits:
            commit_date = datetime.strptime(commit['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if commit_date > since:
                commit_details = get_commit_details(repo_name, commit['sha'])
                if commit_details:
                    for file in commit_details.get('files', []):
                        language = get_file_language(file['filename'])
                        changes = file.get('changes', 0)
                        language_times[language] += changes * 0.5  # 0.5 minutes per change

    return language_times

def format_time(minutes):
    h = int(minutes // 60)
    m = int(minutes % 60)
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
    
    new_content = f'typescript\nFrom: {start_date} - To: {end_date}\n\n'
    new_content += f'Total Time: {format_time(total_time)}\n'
    
    for language, minutes in sorted_languages:
        time_str = format_time(minutes)
        percent = percentages[language]
        graph = create_text_graph(percent)
        new_content += f'{language:<18} {time_str:>14}  {graph} {percent:>7.2f}%\n'
    
    try:
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
        logger.info("README updated successfully")
    except Exception as e:
        logger.error(f"Error updating README: {e}")


def main():
    last_update = get_last_update_time()
    new_times = calculate_time_spent(last_update)
    update_readme(new_times)

if __name__ == '__main__':
    main()
