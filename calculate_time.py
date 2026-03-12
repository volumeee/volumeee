import base64
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import pytz

# ===== LOGGING CONFIGURATION =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coding_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME', 'volumeee')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
README_FILE = 'README.md'
START_DATE = "01 March 2022"
CACHE_DIR = Path('.cache')
CACHE_EXPIRY_DAYS = 1

# Parallel Processing
MAX_WORKERS = 5
RATE_LIMIT_BUFFER = 100
results_lock = Lock()

# Languages to track
ALLOWED_LANGUAGES = [
    'TypeScript', 'JavaScript', 'HTML', 'CSS', 'PHP', 'Kotlin', 'Java', 'C++', 
    'Vue', 'Python', 'Svelte', 'Shell', 'Dockerfile', 'Go', 'Rust'
]

# Framework detection rules mapping
# Structure: { StackName: { files: [], dependencies: { Label: [pkgs] }, keywords: { Label: [strings] } } }
FRAMEWORK_RULES = {
    "Node.js": {
        "files": ['package.json', 'frontend/package.json', 'client/package.json', 'web/package.json', 'app/package.json'],
        "dependencies": {
            'React': ['react'],
            'React Native': ['react-native', 'expo'],
            'Electron': ['electron'],
            'Capacitor': ['@capacitor/core', '@capacitor/cli'],
            'Ionic': ['@ionic/core', '@ionic/vue', '@ionic/react', '@ionic/angular'],
            'Next.js': ['next'],
            'Nuxt.js': ['nuxt'],
            'Vue.js': ['vue'],
            'Svelte': ['svelte'],
            'Angular': ['@angular/core'],
            'Express.js': ['express'],
            'NestJS': ['@nestjs/core', '@nestjs/common'],
            'Fastify': ['fastify'],
            'Tailwind CSS': ['tailwindcss'],
            'Bootstrap': ['bootstrap'],
            'Vite': ['vite'],
            'Webpack': ['webpack'],
            'Prisma': ['prisma', '@prisma/client'],
            'Supabase': ['supabase', '@supabase/supabase-js'],
            'Firebase': ['firebase'],
            'Jest': ['jest'],
            'Vitest': ['vitest'],
            'Mongoose': ['mongoose'],
            'Sequelize': ['sequelize'],
        }
    },
    "Python": {
        "files": ['requirements.txt', 'backend/requirements.txt', 'api/requirements.txt', 'pyproject.toml', 'Pipfile'],
        "keywords": {
            'Django': ['django'],
            'FastAPI': ['fastapi'],
            'Flask': ['flask'],
            'Pandas': ['pandas'],
            'NumPy': ['numpy'],
            'PyTorch': ['torch', 'pytorch'],
            'TensorFlow': ['tensorflow'],
            'Streamlit': ['streamlit'],
            'Pytest': ['pytest'],
            'SQLAlchemy': ['sqlalchemy'],
            'Scrapy': ['scrapy'],
            'BeautifulSoup': ['beautifulsoup4', 'bs4'],
        }
    },
    "PHP": {
        "files": ['composer.json', 'backend/composer.json'],
        "dependencies": {
            'Laravel': ['laravel/framework'],
            'Symfony': ['symfony/symfony'],
            'CodeIgniter': ['codeigniter4/framework'],
            'Livewire': ['livewire/livewire'],
            'PHPUnit': ['phpunit/phpunit'],
        }
    },
    "Go": {
        "files": ['go.mod'],
        "keywords": {
            'Gin': ['github.com/gin-gonic/gin'],
            'Fiber': ['github.com/gofiber/fiber'],
            'Echo': ['github.com/labstack/echo'],
            'GORM': ['gorm.io/gorm'],
        }
    },
    "Java/Kotlin": {
        "files": ['pom.xml', 'build.gradle', 'app/build.gradle'],
        "keywords": {
            'Spring Boot': ['spring-boot'],
            'Hibernate': ['hibernate'],
            'Android SDK': ['com.android.application', 'com.android.library'],
            'JUnit': ['junit'],
        }
    },
    "Rust": {
        "files": ['Cargo.toml'],
        "keywords": {
            'Tokio': ['tokio'],
            'Actix-Web': ['actix-web'],
            'Rocket': ['rocket'],
            'Axum': ['axum'],
            'Serde': ['serde'],
        }
    }
}

# ===== CACHE SYSTEM =====
def init_cache():
    CACHE_DIR.mkdir(exist_ok=True)

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
                return cached['data']
    return None

def save_to_cache(cache_key, data):
    cache_file = CACHE_DIR / f"{cache_key}.json"
    with open(cache_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'data': data
        }, f)

# ===== API HANDLER =====
def api_request_with_retry(url, headers, params=None, max_retries=3):
    cache_key = get_cache_key(url, params)
    cached_data = get_from_cache(cache_key)
    if cached_data is not None:
        return None if isinstance(cached_data, dict) and cached_data.get("_not_found") else cached_data
    
    full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full_url, headers=headers)
    
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req) as response:
                remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
                if remaining < RATE_LIMIT_BUFFER:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    wait_seconds = max(reset_time - time.time(), 0) + 5
                    logger.warning(f"Rate limit low ({remaining}). Sleeping {wait_seconds:.0f}s...")
                    time.sleep(wait_seconds)
                
                data = json.loads(response.read().decode('utf-8'))
                save_to_cache(cache_key, data)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                save_to_cache(cache_key, {"_not_found": True})
                return None
            if e.code == 403 and 'rate limit' in str(e).lower():
                time.sleep((2 ** attempt) * 30)
                continue
            time.sleep((2 ** attempt) * 2)
        except Exception:
            time.sleep((2 ** attempt) * 2)
    return []

# ===== DATA FETCHERS =====
def get_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    repos = []
    page = 1
    while True:
        data = api_request_with_retry(url, headers, {'page': page, 'per_page': 100})
        if not data: break
        repos.extend(data)
        page += 1
    return repos

def get_commits(repo_name, since_date, until_date):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    all_commits, page = [], 1
    while True:
        params = {
            'since': since_date.isoformat(),
            'until': until_date.isoformat(),
            'author': GITHUB_USERNAME,
            'page': page, 'per_page': 100
        }
        commits = api_request_with_retry(url, headers, params)
        if not commits or not isinstance(commits, list): break
        all_commits.extend(commits)
        if len(commits) < 100: break
        page += 1
    return all_commits

def get_repo_languages(repo_name):
    url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    languages = api_request_with_retry(url, headers)
    if not isinstance(languages, dict): return {}
    return {lang: b for lang, b in languages.items() if lang in ALLOWED_LANGUAGES}

# ===== FRAMEWORK DETECTION =====
def get_repo_frameworks(repo_name: str, languages: Optional[Dict[str, Any]] = None) -> List[str]:
    if languages is None: languages = {}
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    frameworks = set()
    
    # Fast inference
    if 'Vue' in languages: frameworks.add('Vue.js')
    if 'Svelte' in languages: frameworks.add('Svelte')

    def fetch_content(path):
        url = f'https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{path}'
        data = api_request_with_retry(url, headers)
        if data and isinstance(data, dict) and 'content' in data:
            return base64.b64decode(data['content']).decode('utf-8', errors='ignore')
        return None

    for stack, rules in FRAMEWORK_RULES.items():
        for file_path in rules.get("files", []):
            content = fetch_content(file_path)
            if not content: continue
            
            if file_path.endswith('.json'):
                try:
                    data = json.loads(content)
                    deps = {}
                    if stack == "Node.js": deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                    elif stack == "PHP": deps = {**data.get('require', {}), **data.get('require-dev', {})}
                    
                    for label, pkgs in rules.get('dependencies', {}).items():
                        if any(p in deps for p in pkgs): frameworks.add(label)
                except: pass
            else:
                lower_content = content.lower()
                for label, strings in rules.get('keywords', {}).items():
                    if any(s.lower() in lower_content for s in strings): frameworks.add(label)
            break # Stop after finding primary config for stack
            
    return sorted(list(frameworks))

# ===== LOGIC & CALCULATIONS =====
def is_valid_commit(commit):
    message = commit['commit']['message'].lower()
    invalids = ['merge', 'bot', 'auto-update', 'readme', 'bump version', 'dependency', 'format', 'lint']
    return not any(p in message for p in invalids)

def get_commit_time_difference(commits):
    if len(commits) < 2: return 0
    times = sorted([datetime.strptime(c['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC) for c in commits])
    times = [t for t in times if (6 <= t.hour or t.hour <= 2)] # Working hrs
    if len(times) < 2: return 0
    
    total, gap = 0, timedelta(hours=2)
    for i in range(len(times)-1):
        diff = times[i+1] - times[i]
        total += diff.total_seconds() if diff < gap else 1800 # Either gap or 30m base
    return (total + 1800) / 3600

def calculate_commit_weight(stats, message):
    changes = stats.get('additions', 0) + stats.get('deletions', 0)
    m = 1.0
    if any(w in message.lower() for w in ['fix', 'bug']): m = 1.3
    elif any(w in message.lower() for w in ['docs', 'typo']): m = 0.5
    
    if changes < 20: return 0.25 * m
    if changes < 150: return 1.0 * m
    return min(2.5, (changes / 200) * m)

# ===== MAIN WORKER =====
def process_repository(repo, current_date, chunk_end, idx, total):
    name = repo['name']
    res = {'language_times': defaultdict(float), 'framework_times': defaultdict(float), 'total_time': 0}
    try:
        commits = get_commits(name, current_date, chunk_end)
        if not commits: return res
        
        langs = get_repo_languages(name)
        if not langs: return res
        
        fws = get_repo_frameworks(name, languages=langs)
        valid = [c for c in commits if is_valid_commit(c)]
        if not valid: return res
        
        ts_time = get_commit_time_difference(valid)
        wt_time = sum(calculate_commit_weight(api_request_with_retry(c['url'], {'Authorization': f'token {GITHUB_TOKEN}'}).get('stats', {}), c['commit']['message']) for c in valid)
        
        total_time = (ts_time * 0.6) + (wt_time * 0.4)
        res['total_time'] = total_time
        
        if total_time > 0:
            total_b = sum(langs.values())
            for l, b in langs.items(): res['language_times'][l] = total_time * (b / total_b)
            for f in fws: res['framework_times'][f] = total_time
            logger.info(f"[{idx}/{total}] ✅ {name}: {total_time:.1f}h")
    except Exception as e:
        logger.error(f"Error {name}: {e}")
    return res

def calculate_time_spent(start_date, end_date):
    init_cache()
    lang_total, fw_total = defaultdict(float), defaultdict(float)
    repos = get_repos(GITHUB_USERNAME)
    
    current = start_date
    while current < end_date:
        chunk_end = min(current + timedelta(days=30), end_date)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_repository, r, current, chunk_end, i+1, len(repos)) for i, r in enumerate(repos)]
            for f in as_completed(futures):
                r = f.result()
                with results_lock:
                    for l, t in r['language_times'].items(): lang_total[l] += t
                    for fw, t in r['framework_times'].items(): fw_total[fw] += t
        current = chunk_end
    return lang_total, fw_total

# ===== UI & EXPORT =====
def format_time(hours):
    return f'{int(hours)} hrs {int((hours % 1) * 60)} mins'

def create_text_graph(percent):
    return '█' * int(20 * percent / 100) + '░' * (20 - int(20 * percent / 100))

def update_readme(lang_times, fw_times, start, end):
    total = sum(lang_times.values())
    sorted_langs = sorted(lang_times.items(), key=lambda x: x[1], reverse=True)
    sorted_fws = sorted(fw_times.items(), key=lambda x: x[1], reverse=True)
    
    content = '```typescript\nCoding Time Tracker🙆‍♂️\n\n'
    content += f'Period: {start.strftime("%d %b %Y")} - {end.strftime("%d %b %Y")}\n'
    content += f'Total Time: {format_time(total)}\n\n💻 Languages:\n'
    for l, t in sorted_langs:
        p = (t / total * 100) if total > 0 else 0
        content += f'{l:<15} {format_time(t):<15} {create_text_graph(p)} {p:>6.2f} %\n'
    
    if sorted_fws:
        content += '\n⚡ Frameworks:\n'
        for f, t in sorted_fws:
            p = (t / total * 100) if total > 0 else 0
            content += f'{f:<15} {format_time(t):<15} {create_text_graph(p)} {p:>6.2f} %\n'
    content += '```\n'

    marker_s, marker_e = '<!-- language_times_start -->', '<!-- language_times_end -->'
    if os.path.exists(README_FILE):
        with open(README_FILE, 'r') as f: text = f.read()
        if marker_s in text:
            text = text.split(marker_s)[0] + marker_s + '\n' + content + marker_e + text.split(marker_e)[1]
        else:
            text += f'\n{marker_s}\n{content}{marker_e}'
        with open(README_FILE, 'w') as f: f.write(text)

def main():
    start_date = datetime.strptime(START_DATE, "%d %B %Y").replace(tzinfo=pytz.UTC)
    end_date = datetime.now(pytz.UTC)
    
    print(f"🚀 Tracking {GITHUB_USERNAME} from {START_DATE}...")
    l_times, f_times = calculate_time_spent(start_date, end_date)
    update_readme(l_times, f_times, start_date, end_date)
    print(f"✅ README updated. Total: {format_time(sum(l_times.values()))}")

if __name__ == '__main__':
    main()
