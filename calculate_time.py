import requests
from collections import defaultdict
import os
from datetime import datetime, timedelta
import pytz

# Configuration
GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "01 March 2022"
ALLOWED_LANGUAGES = ['TypeScript', 'JavaScript', 'HTML', 'CSS', 'PHP', 'Python', 'Kotlin', 'Java', 'C++']

def get_user_repos(username, token):
    repos = []
    page = 1
    while True:
        url = f'https://api.github.com/users/{username}/repos'
        params = {'page': page, 'per_page': 100, 'type': 'all'}
        headers = {'Authorization': f'token {token}'}
        response = requests.get(url, params=params, headers=headers)
        if not response.json():
            break
        repos.extend(response.json())
        page += 1
    return repos

def get_org_repos(token):
    repos = []
    # First get list of organizations
    url = 'https://api.github.com/user/orgs'
    headers = {'Authorization': f'token {token}'}
    orgs_response = requests.get(url, headers=headers)
    orgs = orgs_response.json()

    for org in orgs:
        page = 1
        while True:
            url = f"https://api.github.com/orgs/{org['login']}/repos"
            params = {'page': page, 'per_page': 100}
            response = requests.get(url, headers=headers, params=params)
            if not response.json():
                break
            repos.extend(response.json())
            page += 1
    return repos

def get_repo_languages(repo_full_name, token):
    url = f'https://api.github.com/repos/{repo_full_name}/languages'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)
    languages = response.json()
    return {lang: bytes for lang, bytes in languages.items() if lang in ALLOWED_LANGUAGES}

def get_commits(repo_full_name, since_date, until_date, token):
    commits = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{repo_full_name}/commits'
        params = {
            'since': since_date.isoformat(),
            'until': until_date.isoformat(),
            'page': page,
            'per_page': 100,
            'author': GITHUB_USERNAME
        }
        headers = {'Authorization': f'token {token}'}
        response = requests.get(url, headers=headers, params=params)
        if not response.json():
            break
        commits.extend(response.json())
        page += 1
    return commits

def calculate_time_spent(start_date, end_date):
    language_times = defaultdict(float)
    total_bytes = 0
    
    # Get both personal and organization repositories
    personal_repos = get_user_repos(GITHUB_USERNAME, GITHUB_TOKEN)
    org_repos = get_org_repos(GITHUB_TOKEN)
    all_repos = personal_repos + org_repos
    
    for repo in all_repos:
        repo_full_name = repo['full_name']
        commits = get_commits(repo_full_name, start_date, end_date, GITHUB_TOKEN)
        
        if commits:
            languages = get_repo_languages(repo_full_name, GITHUB_TOKEN)
            repo_total_bytes = sum(languages.values())
            total_bytes += repo_total_bytes
            
            # Calculate time based on commit frequency and code volume
            commit_count = len(commits)
            if commit_count > 0:
                for language, bytes in languages.items():
                    # Assuming average of 30 minutes per commit
                    language_proportion = bytes / repo_total_bytes if repo_total_bytes > 0 else 0
                    language_times[language] += (commit_count * 0.5) * language_proportion

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
    
    # Update README.md
    try:
        with open(README_FILE, 'r') as f:
            readme_content = f.read()
    except FileNotFoundError:
        readme_content = ''
    
    start_marker = '<!-- language_times_start -->'
    end_marker = '<!-- language_times_end -->'
    
    if start_marker in readme_content and end_marker in readme_content:
        new_readme_content = (
            readme_content.split(start_marker)[0] + 
            start_marker + '\n' + 
            new_content + 
            end_marker + 
            readme_content.split(end_marker)[1]
        )
    else:
        new_readme_n' + start_marker + '\n' + new_content + end_marker
    
    with open(README_FILE, 'w') as f:
        f.write(new_readme_content)

def main():
    """Main function to run the script"""
    start_date = datetime.strptime(START_DATE, "%d %B %Y").replace(tzinfo=pytz.UTC)
    end_date = datetime.now(pytz.UTC)
    
    try:
        language_times = calculate_time_spent(start_date, end_date)
        update_readme(language_times, start_date, end_date)
        print("Successfully updated README.md with coding statistics")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    main()
