import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

console = Console(force_terminal=True, legacy_windows=False)

ACCOUNTS_FILE = "accounts.json"
LINKS_FILE = "links.txt"
STATE_FILE = "state.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class InstapaperAccount:
    def __init__(self, account_id: int, name: str, raw_cookie: str, enabled: bool = True):
        self.account_id = account_id
        self.name = name
        self.raw_cookie = raw_cookie.strip()
        self.enabled = enabled
        self.is_valid = False
        self.email: Optional[str] = None
        self.form_key: Optional[str] = None
        self.initial_unread: int = 0
        self.current_unread: int = 0
        self.session = requests.Session()

        self._configure_session()

    def _configure_session(self):
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instapaper.com/home",
            "Origin": "https://www.instapaper.com",
            "X-Requested-With": "XMLHttpRequest",
        })

        if not self.raw_cookie or "PASTE_" in self.raw_cookie:
            return

        for item in self.raw_cookie.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                self.session.cookies.set(k.strip(), v.strip().strip('"'), domain=".instapaper.com")

    def refresh_session_and_key(self) -> Tuple[bool, str]:
        """Fetch fresh user session info, count, and extract user.form_key."""
        try:
            resp = self.session.get("https://www.instapaper.com/data/user_session", timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                self.email = user.get("email") or f"Account-{self.account_id}"
                self.current_unread = user.get("counts", {}).get("unread", 0)
                if self.initial_unread == 0:
                    self.initial_unread = self.current_unread

                # Extract form_key from user dict
                self.form_key = user.get("form_key")
                if self.form_key:
                    self.session.cookies.set("form_key", self.form_key, domain=".instapaper.com")

                self.is_valid = True
                return True, f"Active ({self.email}) | Articles: {self.current_unread}"
            elif resp.status_code == 401:
                return False, "Session Expired (401 Unauthorized)"
            else:
                return False, f"Unexpected response: HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Network check error: {str(e)[:40]}"

    def add_bookmark(self, url: str) -> Tuple[bool, str, Optional[str]]:
        """Add a single URL and strictly verify the returned bookmark object."""
        if not self.form_key:
            ok, _ = self.refresh_session_and_key()
            if not ok or not self.form_key:
                return False, "Missing CSRF form_key", None

        headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-Form-Key": self.form_key,
        }

        try:
            resp = self.session.post(
                "https://www.instapaper.com/data/bookmarks/create",
                json={"url": url},
                headers=headers,
                timeout=15,
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("success") is True and "bookmark" in data:
                        bm = data["bookmark"]
                        title = bm.get("title") or "Saved Link"
                        self.current_unread += 1
                        return True, "SUCCESS", title
                    else:
                        err = data.get("errorMessage") or data.get("error") or "Unknown API response"
                        return False, err, None
                except Exception as e:
                    return False, f"JSON parse error: {e}", None
            elif resp.status_code == 429:
                return False, "RATE_LIMIT_429", None
            elif resp.status_code == 401:
                return False, "SESSION_EXPIRED_401", None
            elif resp.status_code == 403:
                # Refresh key once and fail if still 403
                self.refresh_session_and_key()
                return False, "CSRF_ERROR_403", None
            else:
                return False, f"HTTP_{resp.status_code}", None
        except Exception as e:
            return False, f"Network error: {str(e)[:40]}", None


class SequentialAutomationEngine:
    def __init__(self):
        self.accounts: List[InstapaperAccount] = []
        self.links: List[str] = []
        self.state: Dict = {"accounts": {}}

    def load_accounts(self) -> bool:
        if not os.path.exists(ACCOUNTS_FILE):
            console.print(f"[bold red]Error:[/] '{ACCOUNTS_FILE}' not found!")
            return False

        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                if item.get("enabled", True):
                    acc = InstapaperAccount(
                        account_id=item.get("id", len(self.accounts) + 1),
                        name=item.get("name", f"Account-{len(self.accounts)+1}"),
                        raw_cookie=item.get("cookie", ""),
                        enabled=item.get("enabled", True),
                    )
                    self.accounts.append(acc)
            return True
        except Exception as e:
            console.print(f"[bold red]Failed to read {ACCOUNTS_FILE}:[/] {e}")
            return False

    def load_links(self) -> bool:
        if not os.path.exists(LINKS_FILE):
            console.print(f"[bold red]Error:[/] '{LINKS_FILE}' not found!")
            return False

        raw_links = []
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if not line.startswith("http://") and not line.startswith("https://"):
                        line = "https://" + line
                    raw_links.append(line)

        # Deduplicate while preserving input order
        seen = set()
        self.links = [x for x in raw_links if not (x in seen or seen.add(x))]
        return True

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                    if "accounts" not in self.state:
                        self.state = {"accounts": {}}
            except Exception:
                self.state = {"accounts": {}}
        else:
            self.state = {"accounts": {}}

    def save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            console.print(f"[red]Failed to save state: {e}[/]")

    def run(self):
        console.print(Panel.fit(
            "[bold white]INSTAPAPER SEQUENTIAL AUTOMATION ENGINE[/]\n"
            "[dim]Every Account Receives 100% of All Links in links.txt[/]",
            border_style="cyan"
        ))

        self.load_state()

        if not self.load_accounts():
            return

        if not self.load_links():
            return

        total_links = len(self.links)
        total_accounts = len(self.accounts)

        if total_links == 0:
            console.print("[yellow]No links found in links.txt![/]")
            return

        total_operations = total_links * total_accounts

        console.print(f"[cyan]Links Detected in links.txt:[/] [bold]{total_links}[/] URLs")
        console.print(f"[cyan]Active Accounts Loaded:[/] [bold]{total_accounts}[/] Accounts")
        console.print(f"[bold yellow]Total Workload (Links × Accounts):[/] {total_links} × {total_accounts} = [bold green]{total_operations}[/] Deployments\n")

        # Outer Loop: Account by Account
        for acc_idx, account in enumerate(self.accounts, start=1):
            console.print("=" * 65)
            console.print(
                f"[bold magenta]>>> [{acc_idx}/{total_accounts}] INITIALIZING ACCOUNT: {account.name} <<<[/]"
            )

            # Pre-flight check for this account
            ok, msg = account.refresh_session_and_key()
            if not ok:
                console.print(f"[bold red][!] Account {account.name} Offline:[/] {msg}. Skipping to next account.\n")
                continue

            console.print(f"[green][OK] Session Verified:[/] {account.email}")
            console.print(f"[dim]Live Articles on Instapaper before run: {account.current_unread}[/]")

            acc_key = account.email or account.name
            if acc_key not in self.state["accounts"]:
                self.state["accounts"][acc_key] = []

            completed_for_this_acc = set(self.state["accounts"][acc_key])
            pending_links = [l for l in self.links if l not in completed_for_this_acc]

            console.print(f"[cyan]Links status for this account:[/] {len(completed_for_this_acc)} already saved, [bold yellow]{len(pending_links)} pending[/].\n")

            if not pending_links:
                console.print(f"[bold green][OK] Account {account.name} has already received all {total_links} links! Moving to next...[/]\n")
                continue

            added_this_session = 0

            # Inner Loop: All Links for this Account
            for link_idx, url in enumerate(pending_links, start=1):
                display_url = url if len(url) <= 55 else url[:52] + "..."
                overall_progress = f"[{link_idx}/{len(pending_links)}]"

                console.print(f" {overall_progress} Adding: [dim]{display_url}[/] ... ", end="")

                # Attempt with retry
                success = False
                title = ""
                attempts = 0

                while attempts < 3 and not success:
                    attempts += 1
                    ok, res_code, res_title = account.add_bookmark(url)
                    if ok:
                        success = True
                        title = res_title or "Bookmark"
                        break
                    elif res_code == "RATE_LIMIT_429":
                        console.print(f"\n   [yellow][!] Rate limit hit on {account.name}. Sleeping 60s...[/] ", end="")
                        time.sleep(60)
                    elif res_code == "SESSION_EXPIRED_401":
                        console.print(f"\n   [red][!] Session expired on {account.name}.[/] ")
                        break
                    else:
                        time.sleep(2)

                if success:
                    console.print(f"[bold green][SUCCESS][/] [dim]({title})[/]")
                    added_this_session += 1
                    self.state["accounts"][acc_key].append(url)
                    self.save_state()
                else:
                    console.print(f"[bold red][FAILED][/] ({res_code})")

                # Natural human jitter delay between links (2.5s - 4.5s)
                if link_idx < len(pending_links):
                    delay = random.uniform(2.5, 4.5)
                    time.sleep(delay)

            # End of this account's batch
            # Verify final live count
            account.refresh_session_and_key()
            console.print(f"\n[bold green][OK] Finished Account {account.name}![/]")
            console.print(f"    - Added this run: [bold]{added_this_session}[/]")
            console.print(f"    - Final Live Articles on Instapaper: [bold cyan]{account.current_unread}[/]")

            # Rest between accounts (7 seconds)
            if acc_idx < total_accounts:
                console.print("\n[dim]Resting 7 seconds before switching to the next account...[/]")
                time.sleep(7)
                console.print()

        console.print("\n" + "=" * 65)
        console.print("[bold green]ALL ACCOUNTS PROCESSED SUCCESSFULLY![/]", justify="center")
        console.print("=" * 65)


if __name__ == "__main__":
    try:
        engine = SequentialAutomationEngine()
        engine.run()
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow][!] Script paused by user (Ctrl+C). Progress is safely saved.[/]")
