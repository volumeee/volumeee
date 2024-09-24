import os
from datetime import datetime, timezone
from github import Github
import pytz

# Constants
START_DATE = datetime(2023, 1, 1, tzinfo=pytz.UTC)  # Adjust to your desired start date
GITHUB_TOKEN = os.environ.get("GH_TOKEN")  # Changed from GITHUB_TOKEN to GH_TOKEN
REPO_NAME = os.environ["GITHUB_REPOSITORY"]

def get_language_stats(repo, start_date):
    languages = {}
    commits = repo.get_commits(since=start_date)
    
    for commit in commits:
        if commit.commit.author.date >= start_date:
            files = commit.files
            for file in files:
                # Get the file extension
                ext = file.filename.split('.')[-1].lower()
                if ext:  # Only consider files with extensions
                    languages[ext] = languages.get(ext, 0) + file.changes
    
    return languages

def format_time(minutes):
    hours, mins = divmod(minutes, 60)
    return f"{hours:02d}h {mins:02d}m"

def create_text_graph(percent, width=20):
    filled = int(width * percent / 100)
    return '█' * filled + '░' * (width - filled)

def calculate_percentages(times, total):
    return {lang: (changes / total) * 100 for lang, changes in times.items()}

def update_readme(language_stats):
    total_changes = sum(language_stats.values())
    percentages = calculate_percentages(language_stats, total_changes)
    
    sorted_languages = sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
    
    now = datetime.now(timezone.utc)
    start_date = START_DATE.strftime("%d %B %Y")
    end_date = now.strftime("%d %B %Y")
    
    new_content = f'```typescript\nFrom: {start_date} - To: {end_date}\n\nTotal Changes: {total_changes}\n\n'
    
    for language, changes in sorted_languages:
        time_str = format_time(changes)  # Assuming 1 change = 1 minute for simplicity
        percent = percentages[language]
        graph = create_text_graph(percent)
        new_content += f'{language:<18} {time_str:>14}  {graph} {percent:>7.2f}%\n'
    
    new_content += '```\n'
    return new_content

def main():
    if not GITHUB_TOKEN:
        raise ValueError("GH_TOKEN environment variable is not set")
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    language_stats = get_language_stats(repo, START_DATE)
    
    new_readme_content = update_readme(language_stats)
    
    # Update README.md
    try:
        readme = repo.get_contents("README.md")
        current_content = readme.decoded_content.decode()
        start_marker = "<!-- START_SECTION:language_stats -->"
        end_marker = "<!-- END_SECTION:language_stats -->"
        
        start_index = current_content.find(start_marker)
        end_index = current_content.find(end_marker)
        
        if start_index != -1 and end_index != -1:
            updated_content = (
                current_content[:start_index + len(start_marker)] +
                "\n" + new_readme_content + "\n" +
                current_content[end_index:]
            )
            
            repo.update_file(
                path="README.md",
                message="Update language stats",
                content=updated_content,
                sha=readme.sha
            )
            print("README.md updated successfully.")
        else:
            print("Markers not found in README.md. Please add the markers to your README.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
