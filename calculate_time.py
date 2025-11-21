import requests
from collections import defaultdict
import os
from datetime import datetime, timedelta
import pytz
import time
import json
import hashlib
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ===== LOGGING CONFIGURATION =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coding_tracker.log'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

GITHUB_USERNAME = 'volumeee'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "01 March 2022"
ALLOWED_LANGUAGES = ['TypeScript', 'JavaScript', 'HTML', 'CSS', 'PHP', 'Kotlin', 'Java', 'C++']
CACHE_DIR = Path('.cache')
CACHE_EXPIRY_DAYS = 1

# ===== PARALLEL PROCESSING CONFIGURATION =====
MAX_WORKERS = 5  # Optimal for GitHub Actions (2 vCPU)
RATE_LIMIT_BUFFER = 100  # Stop if remaining requests < 100
results_lock = Lock()  # Thread-safe aggregation

# ===== NEW: Cache Management =====
def init_cache():
    CACHE_DIR.mkdir(exist_ok=True)
    logger.info(f"Cache directory initialized: {CACHE_DIR}")

def get_cache_key(url, params=None):
    key = f"{url}_{json.dumps(params, sort_keys=True) if params else ''}"
    return hashlib.md5(key.encode()).hexdigest()

def get_from_cache(cache_key):
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            cached_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cached_time < timedelta(days=CACHE_EXPIRY_DAYS):
                logger.debug(f"Cache hit: {cache_key}")
                return cached['data']
            else:
                logger.debug(f"Cache expired: {cache_key}")
    return None

def save_to_cache(cache_key, data):
    cache_file = CACHE_DIR / f"{cache_key}.json"
    with open(cache_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'data': data
        }, f)
    logger.debug(f"Data cached: {cache_key}")

# ===== IMPROVED: Rate Limit Handler with Better Protection =====
def api_request_with_retry(url, headers, params=None, max_retries=3):
    cache_key = get_cache_key(url, params)
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Enhanced rate limit protection for GitHub Actions
            remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
            
            if remaining < RATE_LIMIT_BUFFER:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_seconds = max(reset_time - time.time(), 0) + 10
                logger.warning(f"⚠️  Rate limit buffer reached ({remaining} left). Sleeping {wait_seconds:.0f}s...")
                print(f"⚠️  Rate limit buffer reached ({remaining} left). Sleeping {wait_seconds:.0f}s...")
                time.sleep(wait_seconds)
            
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                wait_time = (2 ** attempt) * 60  # Exponential backoff
                logger.warning(f"🚫 Rate limited! Waiting {wait_time}s (attempt {attempt+1}/{max_retries})")
                print(f"🚫 Rate limited! Waiting {wait_time}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            data = response.json()
            save_to_cache(cache_key, data)
            return data
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Failed after {max_retries} attempts: {e}")
                print(f"❌ Failed after {max_retries} attempts: {e}")
                return []
            wait_time = (2 ** attempt) * 5
            logger.warning(f"⚠️  Error: {e}. Retrying in {wait_time}s...")
            print(f"⚠️  Error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    return []

# ===== IMPROVED: Get Repos with Cache =====
def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    repos = []
    page = 1
    
    print(f"📦 Fetching repositories for {username}...")
    logger.info(f"Fetching repositories for {username}")
    while True:
        data = api_request_with_retry(url, headers, {'page': page, 'per_page': 100})
        if not data:
            break
        repos.extend(data)
        page += 1
    
    logger.info(f"Found {len(repos)} repositories")
    print(f"✓ Found {len(repos)} repositories")
    return repos

# ===== IMPROVED: Get Commits with Better Filtering =====
def get_commits(repo_name, since_date, until_date):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    all_commits = []
    page = 1
    
    while True:
        params = {
            'since': since_date.isoformat(),
            'until': until_date.isoformat(),
            'author': GITHUB_USERNAME,
            'page': page,
            'per_page': 100
        }
        
        commits = api_request_with_retry(url, headers, params)
        if not commits or not isinstance(commits, list):
            break
        
        all_commits.extend(commits)
        if len(commits) < 100:
            break
        page += 1
    
    return all_commits

# ===== IMPROVED: Smarter Commit Validation =====
def is_valid_commit(commit):
    message = commit['commit']['message'].lower()
    
    # Filter out automated commits
    invalid_patterns = [
        'merge', 'automated', 'bot', 'auto-update',
        'update readme', 'update package', 'bump version',
        'dependency update', 'prettier', 'eslint', 'format'
    ]
    
    if any(pattern in message for pattern in invalid_patterns):
        return False
    
    # Filter commits with only formatting changes (high changes but likely automated)
    stats = commit.get('stats', {})
    if stats:
        total_changes = stats.get('additions', 0) + stats.get('deletions', 0)
        # If only formatting files changed
        if total_changes > 500 and 'format' in message:
            return False
    
    return True

# ===== IMPROVED: Working Hours Detection =====
def is_working_hours(commit_time):
    """Filter out commits made at unrealistic hours (likely automated)"""
    hour = commit_time.hour
    # Assume working hours: 6 AM - 2 AM (allowing night coding)
    return 6 <= hour or hour <= 2

# ===== IMPROVED: Accurate Time Calculation =====
def get_commit_time_difference(commits):
    if len(commits) < 2:
        return 0
    
    commit_times = []
    for commit in commits:
        commit_date = datetime.strptime(
            commit['commit']['author']['date'], 
            '%Y-%m-%dT%H:%M:%SZ'
        ).replace(tzinfo=pytz.UTC)
        
        # Filter by working hours
        if is_working_hours(commit_date):
            commit_times.append(commit_date)
    
    if len(commit_times) < 2:
        return 0
    
    commit_times.sort()
    
    total_time = 0
    session_gap = timedelta(hours=2)  # Changed to 2 hours for better accuracy
    
    for i in range(len(commit_times)-1):
        diff = commit_times[i+1] - commit_times[i]
        
        # Only count if within same coding session
        if diff < session_gap:
            total_time += diff.total_seconds()
        else:
            # Add base time for the last commit in session (30 min)
            total_time += 1800
    
    # Add time for last commit
    total_time += 1800
    
    return total_time / 3600  # Convert to hours

# ===== IMPROVED: Better Weight Calculation =====
def calculate_commit_weight(stats, commit_message):
    additions = stats.get('additions', 0)
    deletions = stats.get('deletions', 0)
    total_changes = additions + deletions
    
    # Adjust weight based on commit message
    message_lower = commit_message.lower()
    multiplier = 1.0
    
    if any(word in message_lower for word in ['fix', 'bug', 'debug']):
        multiplier = 1.3  # Debugging takes longer
    elif any(word in message_lower for word in ['refactor', 'optimize']):
        multiplier = 1.2
    elif any(word in message_lower for word in ['docs', 'comment', 'typo']):
        multiplier = 0.5  # Documentation is faster
    
    # Base weight calculation
    if total_changes < 5:
        return 0.15 * multiplier  # 9 minutes
    elif total_changes < 20:
        return 0.25 * multiplier  # 15 minutes
    elif total_changes < 50:
        return 0.5 * multiplier   # 30 minutes
    elif total_changes < 150:
        return 1.0 * multiplier   # 1 hour
    elif total_changes < 300:
        return 1.5 * multiplier   # 1.5 hours
    else:
        # Large changes shouldn't scale linearly
        return min(2.5, (total_changes / 200) * multiplier)

def get_commit_stats(commit_url, headers):
    data = api_request_with_retry(commit_url, headers)
    if data and 'stats' in data:
        return data['stats'], data.get('files', [])
    return {'additions': 0, 'deletions': 0}, []

def get_repo_languages(repo_name):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    languages = api_request_with_retry(url, headers)
    return {lang: bytes for lang, bytes in languages.items() if lang in ALLOWED_LANGUAGES}

# ===== NEW: Process Single Repository (Worker Function) =====
def process_repository(repo, current_date, chunk_end, repo_idx, total_repos):
    """
    Worker function to process a single repository in parallel
    Thread-safe and optimized for GitHub Actions
    """
    repo_name = repo['name']
    result = {
        'repo_name': repo_name,
        'language_times': defaultdict(float),
        'commit_count': 0,
        'total_time': 0,
        'status': 'success'
    }
    
    try:
        logger.info(f"[{repo_idx}/{total_repos}] Processing {repo_name}...")
        
        # Fetch commits for this repository
        commits = get_commits(repo_name, current_date, chunk_end)
        
        if not commits:
            result['status'] = 'no_commits'
            logger.debug(f"{repo_name}: No commits found")
            return result
        
        # Get repository languages
        languages = get_repo_languages(repo_name)
        if not languages:
            result['status'] = 'no_tracked_languages'
            logger.debug(f"{repo_name}: No tracked languages")
            return result
        
        # Filter valid commits
        valid_commits = [c for c in commits if is_valid_commit(c)]
        if not valid_commits:
            result['status'] = 'no_valid_commits'
            logger.debug(f"{repo_name}: No valid commits after filtering")
            return result
        
        result['commit_count'] = len(valid_commits)
        
        # Calculate time using hybrid method
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        timestamp_based_time = get_commit_time_difference(valid_commits)
        
        weight_based_time = 0
        for commit in valid_commits:
            stats, files = get_commit_stats(commit['url'], headers)
            message = commit['commit']['message']
            weight_based_time += calculate_commit_weight(stats, message)
        
        # Weighted average: 60% timestamp, 40% weight-based
        total_time = (timestamp_based_time * 0.6) + (weight_based_time * 0.4)
        result['total_time'] = total_time
        
        if total_time > 0:
            # Distribute time across languages by code proportion
            total_bytes = sum(languages.values())
            for language, bytes_count in languages.items():
                result['language_times'][language] = total_time * (bytes_count / total_bytes)
            
            logger.info(f"✅ {repo_name}: {len(valid_commits)} commits → {total_time:.1f}h")
        
    except Exception as e:
        logger.error(f"❌ Error processing {repo_name}: {e}")
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result

# ===== NEW: Parallel Time Calculation =====
def calculate_time_spent(start_date, end_date):
    """
    Main calculation with parallel processing
    Uses ThreadPoolExecutor for concurrent repository processing
    """
    init_cache()
    current_date = start_date
    chunk_size = timedelta(days=30)
    language_times = defaultdict(float)
    
    repos = get_repos(GITHUB_USERNAME)
    total_chunks = ((end_date - start_date).days // chunk_size.days) + 1
    chunk_count = 0
    
    logger.info(f"🚀 Starting parallel processing with {MAX_WORKERS} workers")
    logger.info(f"📊 Total repositories: {len(repos)}")
    
    while current_date < end_date:
        chunk_count += 1
        chunk_end = min(current_date + chunk_size, end_date)
        
        print(f"\n{'='*60}")
        print(f"📅 Processing chunk {chunk_count}/{total_chunks}")
        print(f"📆 Period: {current_date.date()} to {chunk_end.date()}")
        print(f"{'='*60}")
        logger.info(f"Processing chunk {chunk_count}/{total_chunks}: {current_date.date()} to {chunk_end.date()}")
        
        # ===== PARALLEL EXECUTION =====
        chunk_language_times = defaultdict(float)
        completed = 0
        total_repos = len(repos)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all repository processing tasks
            future_to_repo = {
                executor.submit(
                    process_repository,
                    repo,
                    current_date,
                    chunk_end,
                    idx,
                    total_repos
                ): repo
                for idx, repo in enumerate(repos, 1)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_repo):
                completed += 1
                repo = future_to_repo[future]
                
                try:
                    result = future.result()
                    
                    # Thread-safe aggregation
                    with results_lock:
                        for language, time in result['language_times'].items():
                            chunk_language_times[language] += time
                    
                    # Progress indicator
                    if completed % 5 == 0 or completed == total_repos:
                        progress_pct = (completed / total_repos) * 100
                        print(f"📊 Progress: {completed}/{total_repos} repos ({progress_pct:.1f}%)")
                        logger.info(f"Progress: {completed}/{total_repos} repos processed")
                
                except Exception as e:
                    logger.error(f"❌ Failed to process {repo['name']}: {e}")
        
        # Aggregate chunk results to total
        for language, time in chunk_language_times.items():
            language_times[language] += time
        
        chunk_total = sum(chunk_language_times.values())
        print(f"✅ Chunk {chunk_count} completed: {chunk_total:.1f} hours")
        logger.info(f"Chunk {chunk_count} total time: {chunk_total:.1f} hours")
        
        current_date = chunk_end
    
    total_hours = sum(language_times.values())
    logger.info(f"\n{'='*60}")
    logger.info(f"📈 FINAL RESULTS:")
    logger.info(f"Total coding time: {total_hours:.2f} hours")
    logger.info(f"Languages tracked: {len(language_times)}")
    logger.info(f"{'='*60}")
    
    return language_times

# ===== Keep existing functions: format_time, calculate_percentages, create_text_graph, update_readme =====
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
    new_content =  f'```typescript\nCoding Time Tracker🙆‍♂️\n\n'
    new_content += f'From: {start_date.strftime("%d %B %Y")} - To: {end_date.strftime("%d %B %Y")}\n'
    new_content += f'Total Time: {format_time(total_time)}  ({duration} days)\n\n'
    
    for language, time in sorted_languages:
        formatted_time = format_time(time)
        percent = percentages[language]
        graph = create_text_graph(percent)
        new_content += f'{language:<25} {formatted_time:<15} {graph} {percent:>6.2f} %\n'
    
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
    print("=" * 60)
    print("🚀 Coding Time Tracker - Parallel Processing Version")
    print("=" * 60)
    logger.info("="*60)
    logger.info("🚀 Coding Time Tracker Started (Parallel Mode)")
    logger.info("="*60)
    
    start_date = datetime.strptime(START_DATE, "%d %B %Y").replace(tzinfo=pytz.UTC)
    end_date = datetime.now(pytz.UTC)
    
    print(f"\n📊 Configuration:")
    print(f"   User: {GITHUB_USERNAME}")
    print(f"   Period: {START_DATE} to {end_date.strftime('%d %B %Y')}")
    print(f"   Languages: {', '.join(ALLOWED_LANGUAGES)}")
    print(f"   Workers: {MAX_WORKERS} parallel threads")
    print(f"   Rate limit buffer: {RATE_LIMIT_BUFFER} requests\n")
    
    logger.info(f"User: {GITHUB_USERNAME}")
    logger.info(f"Period: {START_DATE} to {end_date.strftime('%d %B %Y')}")
    logger.info(f"Parallel workers: {MAX_WORKERS}")
    logger.info(f"Rate limit buffer: {RATE_LIMIT_BUFFER}")
    
    # Start time tracking
    start_time = time.time()
    
    # Main processing
    language_times = calculate_time_spent(start_date, end_date)
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    total_hours = sum(language_times.values())
    logger.info(f"\n📈 Results Summary:")
    logger.info(f"Total coding time: {total_hours:.2f} hours")
    logger.info(f"Languages tracked: {len(language_times)}")
    logger.info(f"Execution time: {execution_time:.1f} seconds")
    
    print("\n" + "=" * 60)
    print("📝 Updating README.md...")
    update_readme(language_times, start_date, end_date)
    logger.info("README.md updated successfully")
    
    print("=" * 60)
    print(f"✅ Completed in {execution_time:.1f} seconds")
    print(f"📊 Total coding time: {format_time(total_hours)}")
    print("=" * 60 + "\n")
    
    logger.info("="*60)
    logger.info("✅ Coding Time Tracker Completed Successfully")
    logger.info("="*60)

if __name__ == '__main__':
    main()