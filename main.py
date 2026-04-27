import asyncio
import sys
import time
import threading
import os
import httpx
from dataclasses import dataclass, field


LANG = {"current": "zh"}


def t(key: str) -> str:
    texts = {
        "zh": {
            "quit": "退出",
            "back": "返回",
            "select_provider": "选择供应商",
            "select_model": "选择模型",
            "commands": "b=返回, q=退出",
            "you": "你: ",
            "goodbye": "再见!",
            "error": "错误",
            "bot": "Bot: ",
            "batch_results": "批量测试结果",
            "invalid": "无效输入",
            "no_models": "没有可用模型",
            "selected": "已选择",
            "test_all": "测试全部模型",
            "test_prompt": "测试提示词",
        },
"en": {
            "quit": "quit",
            "back": "back",
            "select_provider": "Select provider",
            "select_model": "Select model",
            "commands": "b=back, q=quit",
            "you": "You: ",
            "goodbye": "Goodbye!",
            "error": "Error",
            "bot": "Bot: ",
            "batch_results": "Batch Test Results",
            "invalid": "Invalid input",
            "no_models": "No available models",
            "selected": "Selected",
            "test_all": "test all models",
            "test_prompt": "test prompt",
        },
    }
    return texts[LANG["current"]].get(key, key)


if sys.platform == "win32":
    import io
    import msvcrt
    import os
    import subprocess

    os.environ["TERM"] = "xterm-256color"

    try:
        import colorama

        colorama.init()
    except ImportError:
        subprocess.run(["uv", "add", "colorama"], capture_output=True)
        import colorama

        colorama.init()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


CONFIG_FILE = "models.yaml"


C = {
    "r": "\033[91m",
    "g": "\033[92m",
    "y": "\033[93m",
    "b": "\033[94m",
    "m": "\033[95m",
    "c": "\033[96m",
    "w": "\033[97m",
    "k": "\033[90m",
    "rst": "\033[0m",
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("Installing pyyaml...")
        os.system("uv add pyyaml")
        import yaml

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    providers = {}
    for p in config.get("providers", []):
        name = p.get("name", "")
        base_url = p.get("base_url", "").strip()
        api_key = p.get("api_key", "").strip()

        if not base_url or not api_key:
            continue

        models = [ModelInfo(id=m, name=m.split("/")[-1]) for m in p.get("models", [])]

        providers[name] = {
            "display": p.get("display", name),
            "base_url": base_url,
            "api_key": api_key,
            "models": models,
            "fetch_models": p.get("fetch_models", False),
            "headers": p.get("headers", {}),
            "auth_header": p.get("auth_header", "Authorization"),
            "auth_prefix": p.get("auth_prefix", "Bearer "),
        }

    return {
        "providers": providers,
        "default_timeout": config.get("default_timeout", 30),
    }


@dataclass
class ModelInfo:
    id: str
    name: str


async def fetch_models(base_url: str, api_key: str) -> list[ModelInfo]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return [
                ModelInfo(id=m["id"], name=m["id"].split("/")[-1])
                for m in data.get("data", [])
            ]
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []


class KeyChecker:
    def __init__(self):
        self.cancel_requested = False

    def start(self):
        self.cancel_requested = False
        if sys.platform == "win32":
            self._thread = threading.Thread(target=self._check_win, daemon=True)
            self._thread.start()

    def _check_win(self):
        while not self.cancel_requested:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch == "\x1b":
                    print("\n[Cancelled by ESC]", flush=True)
                    self.cancel_requested = True
                    break
            time.sleep(0.05)

    def is_cancelled(self) -> bool:
        return self.cancel_requested

    def stop(self):
        self.cancel_requested = True


async def chat_with_provider(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    provider_config: dict,
) -> str:
    auth_header = provider_config.get("auth_header", "Authorization")
    auth_prefix = provider_config.get("auth_prefix", "Bearer ")
    extra_headers = provider_config.get("headers", {})

    headers = {"Content-Type": "application/json", auth_header: f"{auth_prefix}{api_key}", **extra_headers}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def chat_with_cancel_check(coro, timeout_val: float, key_checker: KeyChecker):
    start_time = time.time()

    def draw_spinner(elapsed: float, total: float):
        bar_len = 20
        progress = min(elapsed / total, 1.0)
        filled = min(int(bar_len * progress), bar_len)
        bar = C["g"] + "█" * filled + C["k"] + "░" * (bar_len - filled) + C["rst"]
        pct = int(progress * 100)
        print(f"\r  {C['y']}{pct:3d}%{C['rst']} [{bar}] {elapsed:.1f}s", end="", flush=True)

    result = None
    error = None

    async def run():
        nonlocal result, error
        try:
            result = await coro
        except Exception as e:
            error = str(e)

    task = asyncio.create_task(run())
    elapsed = 0.0

    try:
        while not task.done():
            await asyncio.sleep(0.1)

            if key_checker.is_cancelled():
                task.cancel()
                draw_spinner(timeout_val, timeout_val)
                print()
                return "Request cancelled", True

            elapsed = time.time() - start_time
            draw_spinner(elapsed, timeout_val)

            if elapsed > timeout_val:
                task.cancel()
                draw_spinner(timeout_val, timeout_val)
                print()
                return "Request timed out", True

        await task
        elapsed = time.time() - start_time

    except asyncio.CancelledError:
        draw_spinner(timeout_val, timeout_val)
        print()
        return "Request cancelled", True

    draw_spinner(timeout_val, timeout_val)
    print()
    print(f"{C['g']}✓ Done in {elapsed:.1f}s{C['rst']}", flush=True)

    if error:
        return f"Error: {error}", True

    return result, False


def simplify_error(error: str) -> str:
    if "404" in error:
        return "404 Not Found"
    if "400" in error:
        return "400 Bad Request"
    if "401" in error:
        return "401 Unauthorized"
    if "403" in error:
        return "403 Forbidden"
    if "500" in error:
        return "500 Server Error"
    if "timeout" in error.lower():
        return "Timeout"
    if "cancelled" in error.lower():
        return "Cancelled"
    return error[:80]


async def main():
    print("=" * 50)
    print("Model Testing Tool")
    print("=" * 50)

    print(f"\n[1=中文, 2=English] 选择语言:")
    print("  1. 中文")
    print("  2. English")
    lang = input("(默认 1) >> ").strip()
    if lang == "2":
        LANG["current"] = "en"

    config = load_config()
    providers = config["providers"]
    default_timeout = config["default_timeout"]

    while True:
        print(f"\n{'='*50}")
        print(f"{t('select_provider')}")
        provider_list = list(providers.keys())
        for i, name in enumerate(provider_list, 1):
            p = providers[name]
            print(f"  {i}. {p['display']}")

        choice = input(f"\n(默认 1, q={t('quit')}) >> ").strip()
        if choice.lower() == "q":
            print(t("goodbye"))
            break

        try:
            idx = int(choice) - 1 if choice else 0
            if 0 <= idx < len(provider_list):
                provider = provider_list[idx]
            else:
                continue
        except ValueError:
            continue

        provider_config = providers[provider]

        if provider_config.get("fetch_models"):
            models = await fetch_models(provider_config["base_url"], provider_config["api_key"])
        else:
            models = provider_config["models"]

        if not models:
            print("No models available")
            continue

        print(f"\n{provider_config['display']}")
        print(f"{t('select_model')}")
        for i, m in enumerate(models, 1):
            print(f"  {i}. {m.id}")

        choice = input(f"\n(默认 a=全部, 1-N=选择单个模型, b={t('back')}) >> ").strip()
        if choice.lower() == "b":
            continue

        if choice.lower() == "a" or choice == "":
            timeout_val = default_timeout
            default_prompt = "你好" if LANG["current"] == "zh" else "Hi"
            prompt = input(f"\n{t('test_prompt')} (默认: {default_prompt}): ").strip()
            if not prompt:
                prompt = default_prompt

            print(f"\n{t('test_all')}: {prompt[:50]}...")
            print("-" * 50)

            results = []
            for i, model in enumerate(models):
                print(f"\n[{i+1}/{len(models)}] {model.id}")
                coro = chat_with_provider(
                    provider_config["base_url"], provider_config["api_key"], model.id, prompt, provider_config
                )
                key_checker = KeyChecker()
                key_checker.start()
                result, is_error = await chat_with_cancel_check(coro, timeout_val, key_checker)
                key_checker.stop()
                results.append((model.id, is_error, result if not is_error else None))
                if is_error:
                    print(f"  {C['r']}FAIL{C['rst']}: {simplify_error(result or '')}")
                else:
                    text = result or ""
                    print(f"  {C['g']}OK{C['rst']}: {text[:50]}{'...' if len(text) > 50 else ''}")

            print(f"\n{'='*50}")
            print(f"{t('batch_results')}")
            print("-" * 50)
            success = sum(1 for _, ok, _ in results if not ok)
            print(f"Total: {len(results)}, Success: {success}, Failed: {len(results)-success}")
            ok_results = [(m, r) for m, o, r in results if o == False]
            fail_results = [(m, r) for m, o, r in results if o == True]
            for model_id, res in ok_results:
                print(f"{C['g']}OK{C['rst']} | {model_id}")
            for model_id, res in fail_results:
                err = simplify_error(res or "")
                print(f"{C['r']}FAIL{C['rst']} | {model_id} | {err}")
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                model = models[idx]
            else:
                continue
        except ValueError:
            continue

        print(f"\nSelected: {model.id}")
        print(t("commands"))
        timeout_val = default_timeout
        print(f"[Timeout: {timeout_val}s]")

        key_checker = KeyChecker()

        while True:
            prompt = input(f"\n{t('you')}").strip()
            if not prompt:
                continue

            if prompt.lower() == "b":
                break
            if prompt.lower() == "q":
                print(t("goodbye"))
                return

            coro = chat_with_provider(
                provider_config["base_url"], provider_config["api_key"], model.id, prompt, provider_config
            )

            key_checker.start()
            result, is_error = await chat_with_cancel_check(coro, timeout_val, key_checker)
            key_checker.stop()

            if is_error:
                print(f"\n{C['r']}{t('error')}: {result}{C['rst']}")
            else:
                print(f"\n{C['c']}{t('bot')}{C['rst']}{result}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted")