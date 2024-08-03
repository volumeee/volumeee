import requests
from collections import defaultdict
import os
from datetime import datetime
import matplotlib.pyplot as plt

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = '13 March 2023'
END_DATE = '02 August 2024'
TOTAL_TIME_STR = '1,204 hrs 2 mins'
TOTAL_TIME_HOURS = 1204 + 2/60  # Total time in hours

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
        # Assuming each commit represents an hour of work (for simplicity)
        language_times[language] += len(commits)
    
    return language_times

def format_time(hours):
    h = int(hours)
    m = int((hours - h) * 60)
    return f'{h} hrs {m} mins'

def calculate_percentages(language_times, total_time):
    percentages = {}
    for language, time in language_times.items():
        percentages[language] = (time / total_time) * 100
    return percentages

def create_bar_chart(language_times, total_time):
    sorted_languages = sorted(language_times.items(), key=lambda x: x[1], reverse=True)
    languages = [lang for lang, _ in sorted_languages]
    times = [time for _, time in sorted_languages]
    percentages = [time / total_time * 100 for time in times]

    plt.figure(figsize=(10, 6))
    bars = plt.barh(languages, times, color='skyblue')
    plt.xlabel('Time Spent (hours)')
    plt.ylabel('Programming Languages')
    plt.title(f'Time Spent on Programming Languages\nFrom: {START_DATE} - To: {END_DATE}\nTotal Time: {TOTAL_TIME_STR}')
    
    # Add percentage labels
    for bar, percent in zip(bars, percentages):
        plt.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f'{percent:.2f}%', ha='left', va='center')
    
    plt.gca().invert_yaxis()  # Invert y-axis to have the highest value on top
    plt.show()

def main():
    language_times = calculate_time_spent()
    create_bar_chart(language_times, TOTAL_TIME_HOURS)

if __name__ == '__main__':
    main()
