import os
import subprocess
import json
import time
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
import shutil
import argparse
import random
from pathlib import Path
from phrase import WORD_LIST
from logging.handlers import RotatingFileHandler
import threading
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv('cluster.env')

# Global Constants
LOG_FILE = 'bot_manager.log'
SUPERVISORD_CONF_DIR = "/etc/supervisor/conf.d"
APP_DIR = Path("/app")

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot_lock = threading.Lock()

def generate_prefix():
    """Generate a random prefix for bot naming."""
    word1 = random.choice(WORD_LIST)
    word2 = random.choice(WORD_LIST)
    prefix = f"{word1} {word2}"
    logging.info(f'Generated prefix: {prefix}')
    return prefix

def validate_config(clusters):
    """Ensure config is valid before starting bots."""
    required_keys = ['bot_number', 'git_url', 'branch', 'run_command']
    seen_bot_suffixes = set()
    bot_suffix_pattern = re.compile(r'bot\d+$')

    for cluster in clusters:
        if not all(key in cluster for key in required_keys):
            logging.error(f"Missing required fields in: {cluster.get('name', 'Unknown')}")
            return False

        if not cluster['git_url'].startswith('http'):
            logging.error(f"Invalid git_url for {cluster['name']}.")
            return False

        match = bot_suffix_pattern.search(cluster['bot_number'])
        if not match:
            logging.error(f"Invalid bot_number format for {cluster['name']}: {cluster['bot_number']}")
            return False
        
        bot_suffix = match.group()

        if bot_suffix in seen_bot_suffixes:
            logging.error(f"Duplicate bot suffix found: {bot_suffix} in {cluster['bot_number']}")
            return False
        
        seen_bot_suffixes.add(bot_suffix)

    logging.info("Configuration validation successful.")
    return True

def load_config(file_path):
    """Load bot configurations from a JSON file."""
    logging.info(f'Loading configuration from {file_path}')
    
    try:
        with open(file_path, "r") as jsonfile:
            config = json.load(jsonfile)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading JSON file: {e}")
        return []

    clusters = []
    for cluster in config.get('clusters', []):
        details_str = os.getenv(cluster['name'], '{}')

        try:
            details = json.loads(details_str)
            if not isinstance(details, list) or len(details) < 4:
                logging.warning(f"Skipping cluster {cluster['name']} due to missing details.")
                continue

            prefix = generate_prefix()
            cluster_name = f"{prefix} {cluster['name']}"

            clusters.append({
                "name": cluster_name,
                "bot_number": f"{prefix} {details[0]}",
                "git_url": details[1],
                "branch": details[2],
                "run_command": details[3],
                "env": details[4] if len(details) > 4 and isinstance(details[4], dict) else {}
            })

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for {cluster['name']}, skipping.")
            continue

    if not validate_config(clusters):
        raise ValueError("Invalid configuration file.")

    return clusters
    
clusters = load_config("config.json")

def write_supervisord_config(cluster, command):
    """Write supervisord config and ensure it uses the correct virtual environment."""
    bot_name = cluster['bot_number'].replace(" ", "_")
    bot_dir = APP_DIR / bot_name
    venv_path = bot_dir / "venv"
    python_exec = venv_path / "bin" / "python"

    config_path = Path(SUPERVISORD_CONF_DIR) / f"{bot_name}.conf"

    logging.info(f"Writing supervisord config for {cluster['bot_number']} at {config_path}")

    env_vars = ','.join([f'{key}="{value}"' for key, value in cluster['env'].items()]) if cluster['env'] else ""

    config_content = f"""
[program:{bot_name}]
command={python_exec} {command}
directory={bot_dir}
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/{bot_name}_err.log
stdout_logfile=/var/log/supervisor/{bot_name}_out.log
environment={env_vars},VIRTUAL_ENV="{venv_path}",PATH="{venv_path}/bin:$PATH"
"""

    config_path.write_text(config_content.strip())
    logging.info(f"Supervisord config for {cluster['bot_number']} written successfully.")

def start_bot(cluster):
    """Clone, set up, and start a bot with a virtual environment."""
    with bot_lock:
        logging.info(f'Starting bot: {cluster["bot_number"]}')
        bot_env = os.environ.copy()
        bot_env.update(cluster.get('env', {}))

        bot_dir = APP_DIR / cluster['bot_number'].replace(" ", "_")
        venv_path = bot_dir / "venv"
        requirements_file = bot_dir / 'requirements.txt'
        bot_file = bot_dir / cluster['run_command']
        branch = cluster.get('branch', 'main')

        try:
            if bot_dir.exists():
                logging.info(f'Removing existing directory: {bot_dir}')
                shutil.rmtree(bot_dir)

            logging.info(f'Cloning {cluster["bot_number"]} from {cluster["git_url"]} (branch: {branch})')
            subprocess.run(['git', 'clone', '-b', branch, '--single-branch', cluster['git_url'], str(bot_dir)], check=True)

            logging.info(f'Creating virtual environment for {cluster["bot_number"]}')
            subprocess.run(['python3', '-m', 'venv', str(venv_path)], check=True)

            if requirements_file.exists():
                logging.info(f'Installing dependencies for {cluster["bot_number"]}')
                subprocess.run([str(venv_path / 'bin' / 'pip'), 'install', '--no-cache-dir', '-r', str(requirements_file)], check=True)

            command = f"bash {bot_file}" if bot_file.suffix == ".sh" else f"python3 {bot_file}"
            write_supervisord_config(cluster, command)
            reload_supervisord()
            logging.info(f"{cluster['bot_number']} started successfully via supervisord.")

        except subprocess.CalledProcessError as e:
            logging.error(f"Error while processing {cluster['bot_number']}: {e}")

def reload_supervisord():
    """Reload and update supervisord after modifying configurations."""
    logging.info("Reloading supervisord...")
    try:
        subprocess.run(["supervisorctl", "reread"], check=True)
        subprocess.run(["supervisorctl", "update"], check=True)
        logging.info("Supervisord updated successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reloading supervisord: {e}")

def restart_all_bots():
    """Restart all bots managed by the system."""
    logging.info('Restarting all bots...')
    for cluster in clusters:
        stop_bot(cluster['bot_number'])
    reload_supervisord()

def main():
    parser = argparse.ArgumentParser(description='Bot Manager')
    parser.add_argument('--restart', action='store_true', help='Restart all bots')
    args = parser.parse_args()

    if args.restart:
        restart_all_bots()
    else:
        logging.info('Starting bot manager...')
        with ThreadPoolExecutor(max_workers=len(clusters)) as executor:
            for cluster in clusters:
                executor.submit(start_bot, cluster)

if __name__ == "__main__":
    main()
