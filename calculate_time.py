import os
from datetime import datetime, timezone
import re
import logging
from github import Github, Auth
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)

def get_repos():
    auth = Auth.Token(GITHUB_TOKEN)
    g = Github(auth=auth)
    return g.get_user().get_repos()

def calculate_language_times(repos, since):
    language_times = defaultdict(int)
    for repo in repos:
        commits = repo.get_commits(since=since)
        for commit in commits:
            commit_date = commit.commit.author.date.replace(tzinfo=timezone.utc)
            if commit_date > since:
                files_changed = commit.files
                for file in files_changed:
                    language = get_file_language(file.filename)
                    if language:
                        language_times[language] += 30  # 30 minutes per file changed
    return language_times

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

def update_readme(language_times):
    total_time = sum(language_times.values())
    percentages = calculate_percentages(language_times, total_time)
    
    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)
    
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
    repos = get_repos()
    language_times = calculate_language_times(repos, last_update)
    update_readme(language_times)

if __name__ == '__main__':
    main()
