import requests
from collections import defaultdict
import os
from datetime import datetime, timedelta
import pytz

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "01 March 2022"
ALLOWED_LANGUAGES = ['TypeScript', 'JavaScript', 'HTML', 'CSS', 'PHP', 'Python', 'Kotlin', 'Java', 'C++']

def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    repos = []
    page = 1
    
    while True:
        response = requests.get(url, headers=headers, params={'page': page, 'per_page': 100})
        if not response.json():
            break
        repos.extend(response.json())
        page += 1
    
    return repos

def get_commits(repo_name, since_date, until_date):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    params = {
        'since': since_date.isoformat(),
        'until': until_date.isoformat(),
        'author': GITHUB_USERNAME
    }
    
    all_commits = []
    page = 1
    
    while True:
        params['page'] = page
        params['per_page'] = 100
        response = requests.get(url, headers=headers, params=params)
        commits = response.json()
        if not commits or not isinstance(commits, list):
            break
        all_commits.extend(commits)
        page += 1
        
    return all_commits

def get_commit_stats(commit_url, headers):
    response = requests.get(commit_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'stats' in data:
            return data['stats']
    return {'additions': 0, 'deletions': 0}

def get_repo_languages(repo_name):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    languages = response.json()
    return {lang: bytes for lang, bytes in languages.items() if lang in ALLOWED_LANGUAGES}

def get_commit_time_difference(commits):
    if len(commits) < 2:
        return 0
    
    commit_times = []
    for commit in commits:
        commit_date = datetime.strptime(commit['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ')
        commit_times.append(commit_date)
    
    commit_times.sort()
    
    total_time = 0
    for i in range(len(commit_times)-1):
        diff = commit_times[i+1] - commit_times[i]
        if diff.total_seconds() < 14400:  # 4 hours in seconds
            total_time += diff.total_seconds()
    
    return total_time / 3600  # Convert to hours

def calculate_commit_weight(stats):
    additions = stats.get('additions', 0)
    deletions = stats.get('deletions', 0)
    total_changes = additions + deletions
    
    if total_changes < 10:
        return 0.25  # 15 minutes
    elif total_changes < 50:
        return 0.5   # 30 minutes
    elif total_changes < 200:
        return 1     # 1 hour
    else:
        return 1.5   # 1.5 hours

def is_valid_commit(commit):
    message = commit['commit']['message'].lower()
    return not any(x in message for x in ['merge', 'automated', 'bot'])

def calculate_time_spent(start_date, end_date):
    repos = get_repos(GITHUB_USERNAME)
    language_times = defaultdict(float)
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    
    for repo in repos:
        repo_name = repo['name']
        all_commits = get_commits(repo_name, start_date, end_date)
        
        # Filter out invalid commits
        commits = [commit for commit in all_commits if is_valid_commit(commit)]
        
        if commits:
            languages = get_repo_languages(repo_name)
            if not languages:
                continue
                
            # Calculate time based on commit timestamps
            timestamp_based_time = get_commit_time_difference(commits)
            
            # Calculate time based on commit weights
            weight_based_time = 0
            for commit in commits:
                stats = get_commit_stats(commit['url'], headers)
                weight_based_time += calculate_commit_weight(stats)
            
            # Use the larger of the two time calculations
            total_time = max(timestamp_based_time, weight_based_time)
            
            if total_time > 0:
                # Distribute time across languages based on their proportion
                for language, bytes in languages.items():
                    language_proportion = bytes / sum(languages.values())
                    language_times[language] += total_time * language_proportion
    
    return language_times

def format_time(hours):
    h = int(hours)
    m = int((hours - h) * 60)
    return f'{h} hrs {m} mins'

def calculate_percentages(language_times, total_time):
    return {lang: (time / total_time) * 100 if total_time > 0 else 0 
            for lang, time in language_times.items()}

def create_text_graph(percent):
    bar_length = 20
    filled_length = int(bar_length * percent // 100)
    return '█' * filled_length + '░' * (bar_length - filled_length)

def update_readme(language_times, start_date, end_date):
    language_times = {lang: time for lang, time in language_times.items() 
                     if lang in ALLOWED_LANGUAGES}
    
    total_time = sum(language_times.values())
    percentages = calculate_percentages(language_times, total_time)
    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)
    
    new_content = f"text\n💻 Coding Time Tracker\n\n"
    new_content += f"From: {start_date.strftime('%d %B %Y')}\n"
    new_content += f"Total Time: {format_time(total_time)}\n\n"
    
    for language, time in sorted_languages:
        percent = percentages[language]
        if percent >= 1:  # Only show languages with >= 1%
            new_content += f"{language:<12} {format_time(time):<15} {create_text_graph(percent)} {percent:.1f}%\n"
    
    new_content += "```\n"
    
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
