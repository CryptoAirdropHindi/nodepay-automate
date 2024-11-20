import asyncio
import aiohttp
import time
import uuid
import random
import cloudscraper
from loguru import logger
from collections import defaultdict

def show_warning():
    confirm = input("THIS IS MULTI AND BYPASSED VERSION - BYPASSED BY IM-HANZOU (github/im-hanzou) \n\nBy using this tool means you understand the risks. do it at your own risk! \nMake sure you have:\n1. tokens.txt file with your nodepay tokens (one per line)\n2. proxies.txt file with your proxy list\nNote: Each token will get maximum 10 proxies\n\nPress Enter to continue or Ctrl+C to cancel... ")

    if confirm.strip() == "":
        print("Continuing...")
    else:
        print("Exiting...")
        exit()

# Constants
PING_INTERVAL = 60
RETRIES = 60

DOMAIN_API_ENDPOINTS = {
    "SESSION": [
        "http://api.nodepay.ai/api/auth/session"
    ],
    "PING": [
        "http://13.215.134.222/api/network/ping",
        "http://18.139.20.49/api/network/ping",
        "http://52.74.35.173/api/network/ping",
        "http://52.77.10.116/api/network/ping",
        "http://3.1.154.253/api/network/ping"
    ]
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

class TokenState:
    def __init__(self):
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.browser_id = None
        self.account_info = {}
        self.last_ping_time = {}
        self.active_proxies = set()

token_states = defaultdict(TokenState)

def get_random_endpoint(endpoint_type):
    return random.choice(DOMAIN_API_ENDPOINTS[endpoint_type])

def get_endpoint(endpoint_type):
    if endpoint_type not in DOMAIN_API_ENDPOINTS:
        raise ValueError(f"Unknown endpoint type: {endpoint_type}")
    return get_random_endpoint(endpoint_type)

def uuidv4():
    return str(uuid.uuid4())
    
def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

def load_tokens(token_file):
    try:
        with open(token_file, 'r') as file:
            tokens = [line.strip() for line in file if line.strip()]
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def divide_proxies(proxies, num_tokens):
    if not proxies:
        return []
    
    shuffled_proxies = proxies.copy()
    random.shuffle(shuffled_proxies)
    
    divided_proxies = [[] for _ in range(num_tokens)]
    
    proxy_index = 0
    for token_index in range(num_tokens):
        if proxy_index < len(shuffled_proxies):
            divided_proxies[token_index].append(shuffled_proxies[proxy_index])
            proxy_index += 1
    
    while proxy_index < len(shuffled_proxies):
        for token_index in range(num_tokens):
            if len(divided_proxies[token_index]) >= 10:
                continue
                
            if proxy_index < len(shuffled_proxies):
                divided_proxies[token_index].append(shuffled_proxies[proxy_index])
                proxy_index += 1
            else:
                break
    
    for i, proxy_group in enumerate(divided_proxies):
        logger.info(f"Token {i+1} received {len(proxy_group)} proxies")
        
    divided_proxies = [group for group in divided_proxies if group]
    
    return divided_proxies

async def call_api(url, data, proxy, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
    }

    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.post(url, json=data, headers=headers, proxies={
            "http": proxy, "https": proxy}, timeout=30)
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def ping(proxy, token):
    state = token_states[token]
    current_time = time.time()

    if proxy in state.last_ping_time and (current_time - state.last_ping_time[proxy]) < PING_INTERVAL:
        logger.info(f"Skipping ping for proxy {proxy} (Token: {token[:8]}...), not enough time elapsed")
        return

    state.last_ping_time[proxy] = current_time

    try:
        data = {
            "id": state.account_info.get("uid"),
            "browser_id": state.browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(get_endpoint("PING"), data, proxy, token)
        if response["code"] == 0:
            logger.info(f"Ping successful via proxy {proxy} (Token: {token[:8]}...): {response}")
            state.status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response, token)
    except Exception as e:
        logger.error(f"Ping failed via proxy {proxy} (Token: {token[:8]}...): {e}")
        handle_ping_fail(proxy, None, token)

async def start_ping(proxy, token):
    try:
        while True:
            await ping(proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} (Token: {token[:8]}...) was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy} (Token: {token[:8]}...): {e}")

def handle_ping_fail(proxy, response, token):
    state = token_states[token]
    if response and response.get("code") == 403:
        handle_logout(proxy, token)
    else:
        state.status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy, token):
    state = token_states[token]
    state.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    state.account_info = {}
    logger.info(f"Logged out and cleared session info for proxy {proxy} (Token: {token[:8]}...)")

async def render_profile_info(proxy, token):
    state = token_states[token]

    try:
        state.browser_id = uuidv4()
        response = await call_api(get_endpoint("SESSION"), {}, proxy, token)
        valid_resp(response)
        state.account_info = response["data"]
        
        if state.account_info.get("uid"):
            await start_ping(proxy, token)
        else:
            handle_logout(proxy, token)
            
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy} (Token: {token[:8]}...): {e}")
        error_message = str(e)
        if "500 Internal Server Error"  or "401" in error_message or "keepalive ping timeout" in error_message:
            logger.info(f"Removing error proxy from token {token[:8]}... proxy list: {proxy}")
            state.active_proxies.discard(proxy)
            return None
        return proxy

async def handle_token(token, proxy_group):
    state = token_states[token]
    state.active_proxies = set(proxy_group)
    
    logger.info(f"Token {token[:8]}... starting with {len(state.active_proxies)} active proxies")
    
    while True:
        tasks = []
        for proxy in list(state.active_proxies):
            task = asyncio.create_task(render_profile_info(proxy, token))
            tasks.append(task)
            
        if tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    result = task.result()
                    if result is None:
                        logger.info(f"Task failed for token {token[:8]}...")
                except Exception as e:
                    logger.error(f"Task error for token {token[:8]}...: {e}")
                    
        await asyncio.sleep(3)

async def main():
    tokens = load_tokens('tokens.txt')
    if not tokens:
        logger.error("No tokens found in tokens.txt")
        return
    
    all_proxies = load_proxies('proxies.txt')
    if not all_proxies:
        logger.error("No proxies found in proxies.txt")
        return
    
    proxy_groups = divide_proxies(all_proxies, len(tokens))
    
    for i, (token, proxy_group) in enumerate(zip(tokens, proxy_groups)):
        logger.info(f"Token {token[:8]}... got {len(proxy_group)} proxies")
    
    token_tasks = []
    for token, proxy_group in zip(tokens, proxy_groups):
        if proxy_group:
            logger.info(f"Starting bot for token {token[:8]}... with {len(proxy_group)} proxies")
            task = asyncio.create_task(handle_token(token, proxy_group))
            token_tasks.append(task)

    await asyncio.gather(*token_tasks)

if __name__ == '__main__':
    show_warning()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
