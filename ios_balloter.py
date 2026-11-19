"""iOS Simulator XCUITest Auto-Balloter for E+ Sumachike (スマチケ) lotteries.

Drives genuine Mobile Safari inside a booted Xcode iOS Simulator via Appium XCUITest
(native UI mode, so navigator.webdriver stays false and Akamai Bot Manager does not block).

Prerequisites:
  1. Boot an iOS Simulator (e.g., `xcrun simctl boot <UDID>`).
  2. Start Appium server: `appium --port 4723` (with `xcuitest` driver installed).
  3. Run: `uv run ios_balloter.py`
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


APPIUM_URL = "http://127.0.0.1:4723"


def xpath_literal(value: str) -> str:
    """Safely quote an arbitrary string for use as an XPath 1.0 string literal."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


def detect_booted_iphone_udid() -> str:
    """Return the UDID of a currently booted iPhone simulator, or raise a helpful error."""
    out = subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "booted", "-j"], text=True
    )
    data = json.loads(out)
    for runtime, devices in data.get("devices", {}).items():
        if "iOS" not in runtime:
            continue
        for dev in devices:
            if dev.get("state") == "Booted" and "iPhone" in dev.get("name", ""):
                return dev["udid"]
    raise RuntimeError(
        "No booted iPhone Simulator found. Boot one first with:\n"
        "  xcrun simctl list devices available\n"
        "  xcrun simctl boot <IPHONE_UDID>"
    )


def ensure_appium_running(appium_url: str = APPIUM_URL) -> None:
    """Verify the local Appium server is reachable before creating a session."""
    try:
        r = requests.get(f"{appium_url.rstrip('/')}/status", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"Appium server is not reachable at {appium_url}. Start it first with:\n"
            "  appium --port 4723\n"
            "(Install via: npm install -g appium && appium driver install xcuitest)"
        ) from exc


class IOSSafariAutomator:
    def __init__(
        self,
        udid: str,
        appium_url: str = APPIUM_URL,
        session_id: Optional[str] = None,
        otp_file: Optional[str] = None,
        otp_cmd: Optional[str] = None,
        otp_timeout: int = 300,
    ):
        self.udid = udid
        self.appium_url = appium_url.rstrip("/")
        self.otp_file = otp_file
        self.otp_cmd = otp_cmd
        self.otp_timeout = otp_timeout
        ensure_appium_running(self.appium_url)
        self._owns_session = session_id is None
        self.session_id = session_id or self._create_session()
        self.base = f"{self.appium_url}/session/{self.session_id}"
        r = requests.post(
            f"{self.base}/appium/settings",
            json={"settings": {"waitForIdleTimeout": 0}},
            timeout=15,
        )
        r.raise_for_status()

    def __enter__(self) -> "IOSSafariAutomator":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Delete the Appium session if this instance created it."""
        if not self._owns_session:
            return
        try:
            requests.delete(self.base, timeout=15)
        except Exception as exc:
            logging.warning(f"<Appium> Failed to close session {self.session_id}: {exc}")
        finally:
            self._owns_session = False

    def logout(self) -> None:
        """Log out of member.eplus.jp before switching to a different E+ account."""
        logging.info("<Auth> Logging out of current E+ session before account switch")
        self.open_url("https://member.eplus.jp/logout")
        time.sleep(2.0)

    def _safe_json(self, response: requests.Response) -> Dict:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {}
        except ValueError:
            logging.warning(
                f"<Appium> Non-JSON response (HTTP {response.status_code}) from {response.url}"
            )
            return {}

    def _create_session(self) -> str:
        payload = {
            "capabilities": {
                "alwaysMatch": {
                    "platformName": "iOS",
                    "appium:automationName": "XCUITest",
                    "appium:udid": self.udid,
                    "appium:bundleId": "com.apple.mobilesafari",
                    "appium:noReset": True,
                    "appium:shouldTerminateApp": False,
                    "appium:skipLogCapture": True,
                    "appium:newCommandTimeout": 600,
                    "appium:wdaLaunchTimeout": 180000,
                }
            }
        }
        r = requests.post(f"{self.appium_url}/session", json=payload, timeout=200)
        r.raise_for_status()
        data = r.json()
        sid = data["value"]["sessionId"]
        logging.info(f"<Appium> Attached XCUITest session {sid}")
        return sid

    def open_url(self, url: str) -> None:
        subprocess.run(["xcrun", "simctl", "openurl", self.udid, url], check=True)
        time.sleep(3.5)

    def source(self) -> str:
        r = requests.get(f"{self.base}/source", timeout=30)
        if not r.ok:
            logging.warning(f"<Appium> GET /source returned HTTP {r.status_code}")
            return ""
        val = self._safe_json(r).get("value", "")
        return val if isinstance(val, str) else ""

    def find(self, using: str, value: str, timeout: float = 15.0) -> Optional[str]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.post(
                f"{self.base}/element",
                json={"using": using, "value": value},
                timeout=20,
            )
            data = self._safe_json(r)
            v = data.get("value", {})
            if r.ok and isinstance(v, dict) and v and "error" not in v:
                return list(v.values())[0]
            time.sleep(0.5)
        return None

    def find_all(self, using: str, value: str) -> List[str]:
        r = requests.post(
            f"{self.base}/elements",
            json={"using": using, "value": value},
            timeout=20,
        )
        if not r.ok:
            return []
        vals = self._safe_json(r).get("value", [])
        if not isinstance(vals, list):
            return []
        return [list(e.values())[0] for e in vals if isinstance(e, dict) and e]

    def click(self, eid: str) -> int:
        r = requests.post(f"{self.base}/element/{eid}/click", json={}, timeout=20)
        if not r.ok:
            logging.warning(f"<Appium> click({eid}) returned HTTP {r.status_code}")
        return r.status_code

    def tap_xy(self, x: int, y: int) -> int:
        r = requests.post(
            f"{self.base}/execute/sync",
            json={"script": "mobile: tap", "args": [{"x": x, "y": y}]},
            timeout=15,
        )
        if not r.ok:
            logging.warning(f"<Appium> tap_xy({x}, {y}) returned HTTP {r.status_code}")
        return r.status_code

    def type_text(self, eid: str, text: str) -> None:
        self.click(eid)
        time.sleep(0.3)
        r = requests.post(f"{self.base}/element/{eid}/value", json={"text": text}, timeout=20)
        if not r.ok:
            logging.warning(f"<Appium> type_text({eid}) returned HTTP {r.status_code}")
        time.sleep(0.4)

    def swipe(self, direction: str = "up") -> None:
        r = requests.post(
            f"{self.base}/execute/sync",
            json={"script": "mobile: swipe", "args": [{"direction": direction}]},
            timeout=15,
        )
        if not r.ok:
            logging.warning(f"<Appium> swipe({direction}) returned HTTP {r.status_code}")
        time.sleep(0.6)

    def dismiss_keyboard(self) -> None:
        done = self.find(
            "xpath", "//XCUIElementTypeButton[@name='Done' or @name='完了']", timeout=2.0
        )
        if done:
            self.click(done)
            time.sleep(0.5)

    def dismiss_save_password_sheet(self) -> None:
        """Dismiss the iOS 'Save Password?' sheet if it appears after first-time login."""
        src = self.source()
        if "Save Password?" in src or "パスワードを保存" in src:
            not_now = self.find(
                "xpath",
                "//XCUIElementTypeButton[@name='Not Now' or @name='今はしない']",
                timeout=2.0,
            )
            if not_now:
                self.click(not_now)
            else:
                # Fallback tap on the bottom button of the iOS Save Password modal
                self.tap_xy(201, 692)
            time.sleep(0.8)

    def attr(self, eid: str, name: str) -> str:
        r = requests.get(f"{self.base}/element/{eid}/attribute/{name}", timeout=10)
        if not r.ok:
            return ""
        return str(self._safe_json(r).get("value") or "")

    def rect(self, eid: str) -> Dict[str, int]:
        r = requests.get(f"{self.base}/element/{eid}/rect", timeout=10)
        if not r.ok:
            return {}
        val = self._safe_json(r).get("value", {})
        return val if isinstance(val, dict) else {}

    def screenshot(self, path: str) -> None:
        subprocess.run(["xcrun", "simctl", "io", self.udid, "screenshot", path], check=False)

    def _obtain_email_otp(self) -> str:
        """Obtain the 6-digit E+ email verification code via --otp-cmd, --otp-file, or stdin."""
        # 1. Command hook (e.g., Gmail CLI / agent script returning the 6-digit code)
        if self.otp_cmd:
            print("  Running --otp-cmd to retrieve 6-digit E+ verification code...", flush=True)
            out = subprocess.check_output(
                self.otp_cmd,
                shell=True,
                text=True,
                timeout=self.otp_timeout,
            ).strip()
            match = re.search(r"\b(\d{6})\b", out)
            if not match:
                raise RuntimeError(
                    f"--otp-cmd exited 0 but output ({len(out)} chars) did not contain a 6-digit code"
                )
            return match.group(1)

        # 2. File polling hook (for AI agents that pause, ask the user / read email, and write the code)
        if self.otp_file:
            otp_path = Path(self.otp_file).expanduser()
            if otp_path.is_symlink():
                raise RuntimeError(f"Refusing to use symlink for --otp-file: {otp_path}")
            otp_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if otp_path.parent.resolve() != Path("/tmp").resolve():
                    os.chmod(otp_path.parent, 0o700)
            except OSError:
                pass
            if otp_path.exists():
                otp_path.unlink()
            print(
                f"\n>>> [OTP REQUIRED] E+ sent a 6-digit verification code to your email.\n"
                f">>> Write the 6-digit code to {otp_path} (waiting up to {self.otp_timeout}s)... <<<",
                flush=True,
            )
            deadline = time.time() + self.otp_timeout
            while time.time() < deadline:
                if otp_path.is_symlink():
                    raise RuntimeError(f"Refusing to read symlink at --otp-file: {otp_path}")
                if otp_path.exists():
                    content = otp_path.read_text(encoding="utf-8").strip()
                    match = re.search(r"\b(\d{6})\b", content)
                    if match:
                        otp_path.unlink(missing_ok=True)
                        return match.group(1)
                time.sleep(1.0)
            raise TimeoutError(f"Timed out waiting for 6-digit OTP in {otp_path}")

        # 3. Interactive terminal prompt
        if sys.stdin.isatty():
            print(
                "\n>>> [OTP REQUIRED] E+ sent a 6-digit verification code (メールアドレス認証) to your email. <<<",
                flush=True,
            )
            while True:
                code = input("Enter 6-digit E+ verification code: ").strip()
                if re.fullmatch(r"\d{6}", code):
                    return code
                print("Please enter exactly 6 digits.")

        raise RuntimeError(
            "E+ requires first-time email verification (メールアドレス認証), "
            "but stdin is not interactive and neither --otp-file nor --otp-cmd was provided."
        )

    def _complete_email_verification(self) -> bool:
        """Handle E+'s first-time メールアドレス認証 screen (including extra-auth modal & keyboard)."""
        self.dismiss_save_password_sheet()
        src = self.source()

        # Dismiss the '同一端末での複数アカウント利用を確認しました...追加認証が必要です' popup if shown
        if "追加認証が必要です" in src or "複数アカウント利用" in src:
            popup_next = self.find("xpath", "//XCUIElementTypeButton[@name='次へ']", timeout=3.0)
            if popup_next:
                self.click(popup_next)
                time.sleep(1.5)
                src = self.source()

        if "メールアドレス認証" not in src and "認証コード" not in src:
            return True

        otp_code = self._obtain_email_otp()
        logging.info("<Auth> Submitting 6-digit email verification code...")

        tf = self.find("xpath", "//XCUIElementTypeTextField[@name='認証コード']", timeout=10.0)
        if not tf:
            # Fallback: first text field that is not Safari's address bar
            for candidate in self.find_all("class name", "XCUIElementTypeTextField"):
                if self.attr(candidate, "name") != "TabBarItemTitle":
                    tf = candidate
                    break
        if not tf:
            raise RuntimeError("Could not find 認証コード text field on メールアドレス認証 page")

        self.type_text(tf, otp_code)
        self.dismiss_keyboard()
        time.sleep(0.6)

        reg_btn = self.find("xpath", "//XCUIElementTypeButton[@name='登録']", timeout=10.0)
        if not reg_btn:
            raise RuntimeError("Could not find 登録 submit button on メールアドレス認証 page")
        self.click(reg_btn)
        time.sleep(5.0)
        self.dismiss_save_password_sheet()

        # Check whether E+ redirected straight to sp.atom.eplus.jp or stalled on member.eplus.jp
        post_src = self.source()
        if "希望席種" in post_src or "選択して下さい" in post_src or "sp.atom.eplus.jp" in post_src:
            return True
        if "メールアドレス認証" in post_src:
            raise RuntimeError("Email verification code was rejected or expired; still on メールアドレス認証")

        # Device is now verified on member.eplus.jp, but redirect stalled on a blank transition page
        return False

    def _find_stop_next_button(self, session_name: str) -> Optional[str]:
        """Match the 次へ button belonging to session_name dynamically using XML y-coordinates."""
        for attempt in range(2):
            next_btns = self.find_all("accessibility id", "次へ")
            if not next_btns:
                if attempt == 0:
                    self.swipe("up")
                    continue
                return None
            if len(next_btns) == 1 and (not session_name or session_name == "All"):
                return next_btns[0]
            if not session_name or session_name == "All":
                return next_btns[0]

            src = self.source()
            stop_y: Optional[int] = None
            try:
                root = ET.fromstring(src)
                for el in root.iter():
                    if el.tag == "XCUIElementTypeStaticText":
                        text = el.attrib.get("value", "") or el.attrib.get("name", "")
                        if session_name in text and "最速先行抽選" not in text:
                            stop_y = int(el.attrib.get("y", "-1"))
                            break
            except Exception:
                pass

            if stop_y is not None:
                best_btn = None
                best_dy = 10**9
                for btn in next_btns:
                    r = self.rect(btn)
                    by = r.get("y", -1)
                    if by > stop_y and (by - stop_y) < best_dy:
                        best_dy = by - stop_y
                        best_btn = btn
                if best_btn:
                    return best_btn

            if attempt == 0:
                self.swipe("up")

        # Do NOT silently fall back to next_btns[0] for a named session (prevents wrong-stop ballots)
        return None

    def extract_receipt_number(self, src: str) -> str:
        try:
            root = ET.fromstring(src)
            texts = [
                el.attrib.get("value", "")
                for el in root.iter()
                if el.tag == "XCUIElementTypeStaticText"
            ]
            for i, txt in enumerate(texts):
                if "受付番号" in txt:
                    return " ".join(texts[i : i + 3]).strip()
        except Exception:
            pass
        return "(check completion email / 申込み履歴)"

    def _open_and_enter_serial_and_stop(
        self, entry_url: str, code: str, session_name: str
    ) -> Tuple[bool, str]:
        self.open_url(entry_url)

        tf = self.find("xpath", "//XCUIElementTypeTextField[@value='シリアルナンバー']", timeout=8.0)
        if tf:
            self.swipe("up")
            tf = (
                self.find(
                    "xpath", "//XCUIElementTypeTextField[@value='シリアルナンバー']", timeout=5.0
                )
                or tf
            )
            self.type_text(tf, code)
            self.dismiss_keyboard()
            apply_btn = self.find("xpath", "//XCUIElementTypeButton[@name='お申込みへ']", timeout=10.0)
            if not apply_btn:
                return False, "Could not find お申込みへ button"
            self.click(apply_btn)
            time.sleep(4.0)
        else:
            logging.warning(
                "<Serial> Serial input field not found on entry page; checking if stop list is already shown"
            )

        src = self.source()
        if "利用回数を超えた" in src:
            return False, "USED_CODE"
        if "申し込み情報が正しくありません" in src:
            return False, "INVALID_CODE"

        stop_btn = self._find_stop_next_button(session_name)
        if not stop_btn:
            return False, f"No 次へ button found for stop '{session_name}'"
        print(f"  Clicking 次へ for {session_name}", flush=True)
        self.click(stop_btn)
        time.sleep(4.0)
        return True, "OK"

    def _select_dropdown_button(self, dropdown_xpath: str, option_predicate) -> bool:
        """Tap an HTML <select> dropdown and pick the matching native iOS menu button with retries."""
        for _ in range(3):
            dd = self.find("xpath", dropdown_xpath, timeout=10.0)
            if not dd:
                return False
            self.click(dd)
            time.sleep(1.0)
            for b in self.find_all("class name", "XCUIElementTypeButton"):
                bname = self.attr(b, "name")
                if option_predicate(bname):
                    self.click(b)
                    time.sleep(1.2)
                    return True
            time.sleep(0.8)
        return False

    def apply_single(
        self,
        entry_url: str,
        code: str,
        session_name: str,
        seat_keyword: str = "一般指定席",
        goods_keyword: str = "特製グッズ無し",
        quantity: int = 2,
        username: Optional[str] = None,
        password: Optional[str] = None,
        screenshot_prefix: Optional[str] = None,
    ) -> Tuple[bool, str]:
        print(
            f"\n=== Starting application: Code={code}, Stop={session_name}, Qty={quantity} ===",
            flush=True,
        )
        ok, status = self._open_and_enter_serial_and_stop(entry_url, code, session_name)
        if not ok:
            return False, status

        # 3. Handle login + first-time email verification (メールアドレス認証) if needed
        src = self.source()
        if "ログイン画面へ" in src:
            login_link = self.find("accessibility id", "ログイン画面へ", timeout=10.0)
            if login_link:
                self.click(login_link)
                time.sleep(4.0)
            id_tf = self.find("xpath", "//XCUIElementTypeTextField[@name='ID']", timeout=6.0)
            if id_tf and username and password:
                self.type_text(id_tf, username)
                pw_tf = self.find(
                    "xpath", "//XCUIElementTypeSecureTextField[@name='パスワード']", timeout=10.0
                )
                if pw_tf:
                    self.type_text(pw_tf, password)
                login_btn = self.find(
                    "xpath", "//XCUIElementTypeButton[@name='ログイン']", timeout=10.0
                )
                if login_btn:
                    self.click(login_btn)
                time.sleep(5.0)
                self.dismiss_save_password_sheet()

                post_login_src = self.source()
                if "メールアドレス認証" in post_login_src or "追加認証が必要です" in post_login_src:
                    landed_on_ballot = self._complete_email_verification()
                    if not landed_on_ballot:
                        # Device is now verified; re-enter serial & stop cleanly
                        ok, status = self._open_and_enter_serial_and_stop(
                            entry_url, code, session_name
                        )
                        if not ok:
                            return False, status
                        if "ログイン画面へ" in self.source():
                            login_link = self.find("accessibility id", "ログイン画面へ", timeout=8.0)
                            if login_link:
                                self.click(login_link)
                                time.sleep(4.0)

        # 4. Select 希望席種 -> seat_keyword (e.g. 一般指定席)
        if not self._select_dropdown_button(
            "(//XCUIElementTypeOther[@value='選択して下さい'])[1]",
            lambda name: seat_keyword in name,
        ):
            return False, f"Could not select seat option containing '{seat_keyword}'"

        # 5. Select goods/no-goods quantity dropdown -> e.g. （特製グッズ無し） 2枚
        goods_xpath = (
            f"//XCUIElementTypeOther[contains(@value, {xpath_literal(goods_keyword)}) "
            "and contains(@value, '-----')]"
        )
        if not self._select_dropdown_button(
            goods_xpath,
            lambda name: f"{quantity}枚" in name,
        ):
            return False, f"Could not select '{goods_keyword}' {quantity}枚"

        # 6. Click 申込み
        apply_link = self.find("xpath", "//XCUIElementTypeLink[@name='申込み']", timeout=10.0)
        if not apply_link:
            return False, "Could not find 申込み link"
        self.click(apply_link)
        time.sleep(4.0)

        # 7. Payment & Delivery: select スマチケ + コンビニ／ＡＴＭ -> 次へ
        suma = self.find(
            "xpath", "//XCUIElementTypeStaticText[contains(@name, 'スマチケ')]", timeout=10.0
        )
        if suma:
            self.click(suma)
            time.sleep(0.5)

        conbini = self.find(
            "xpath", "//XCUIElementTypeStaticText[@name='コンビニ／ＡＴＭ']", timeout=10.0
        )
        if not conbini:
            return False, "Could not find コンビニ／ＡＴＭ payment option"
        self.click(conbini)
        time.sleep(0.5)

        pay_next = self.find("xpath", "//XCUIElementTypeLink[@name='次へ']", timeout=10.0)
        if not pay_next:
            return False, "Could not find 次へ link on payment screen"
        self.click(pay_next)
        time.sleep(4.0)

        # 8. Final confirmation: check all unchecked switches -> 同意して申込み
        switches = self.find_all("class name", "XCUIElementTypeSwitch")
        for sw in switches:
            if self.attr(sw, "value") == "0":
                self.click(sw)
                time.sleep(0.4)

        submit = self.find("xpath", "//XCUIElementTypeLink[@name='同意して申込み']", timeout=10.0)
        if not submit:
            return False, "Could not find 同意して申込み button"
        self.click(submit)
        time.sleep(5.0)

        done_src = self.source()
        if screenshot_prefix:
            self.screenshot(f"{screenshot_prefix}_{code}_{session_name}.png")

        is_completed = (
            ("申込みが完了しました" in done_src or "申込完了" in done_src or "受付番号" in done_src)
            and "同意して申込み" not in done_src
        )
        if is_completed:
            receipt = self.extract_receipt_number(done_src)
            print(f"  [SUCCESS] {code} -> {session_name} ({receipt})", flush=True)
            return True, receipt
        return False, "Did not see 申込完了 confirmation on final page"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="E+ Sumachike iOS Simulator Auto-Balloter (Appium XCUITest)"
    )
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument(
        "--udid",
        default=None,
        help="Booted iOS Simulator UDID (auto-detected if omitted)",
    )
    parser.add_argument("--session-id", default=None, help="Reuse an existing Appium session ID")
    parser.add_argument(
        "--pairs",
        nargs="*",
        default=None,
        help="Optional explicit code:session pairs (e.g. abc12345:福岡公演)",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        default=0,
        help="0-based [[Ballots]] index to use when --pairs is supplied (default: 0)",
    )
    parser.add_argument(
        "--otp-file",
        default=None,
        help="Path to a private file where an agent or user writes the 6-digit E+ email OTP code",
    )
    parser.add_argument(
        "--otp-cmd",
        default=None,
        help="Trusted local shell command that prints the 6-digit E+ email OTP code",
    )
    parser.add_argument(
        "--otp-timeout",
        type=int,
        default=300,
        help="Seconds to wait for --otp-file / --otp-cmd before timing out (default: 300)",
    )
    parser.add_argument(
        "--screenshot-prefix",
        default=None,
        help="Optional path prefix to save completion screenshots",
    )
    args = parser.parse_args()

    logging.basicConfig(
        filename="apply.log",
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        filemode="a",
    )

    with open(args.config, "rb") as fd:
        config = tomllib.load(fd)

    udid = args.udid or detect_booted_iphone_udid()
    entry_url = config["URL"]

    ballots = config["Ballots"]
    if args.pairs:
        if not (0 <= args.account_index < len(ballots)):
            raise ValueError(
                f"--account-index {args.account_index} out of range for {len(ballots)} [[Ballots]] entries"
            )
        ballots = [ballots[args.account_index]]

    env_username = os.environ.get("EPLUS_USERNAME")
    env_password = os.environ.get("EPLUS_PASSWORD")

    results: List[Tuple[str, str, bool, str]] = []
    previous_username: Optional[str] = None

    with IOSSafariAutomator(
        udid=udid,
        session_id=args.session_id,
        otp_file=args.otp_file,
        otp_cmd=args.otp_cmd,
        otp_timeout=args.otp_timeout,
    ) as auto:
        for ballot in ballots:
            creds = ballot["Credentials"]
            username = env_username or creds["username"]
            password = env_password or creds["password"]

            if previous_username is not None and username != previous_username:
                auto.logout()
            previous_username = username

            quantity = int(ballot.get("Quantity", 2))
            seat_keyword = ballot.get("SeatKeyword") or ballot.get("SeatType") or "一般指定席"
            goods_keyword = ballot.get("GoodsKeyword", "特製グッズ無し")

            jobs: List[Tuple[str, str]] = []
            if args.pairs:
                for item in args.pairs:
                    if ":" not in item:
                        raise ValueError(f"Invalid --pairs entry (expected CODE:SESSION): {item!r}")
                    c, s = item.split(":", 1)
                    jobs.append((c, s))
            else:
                sessions = ballot["Sessions"]
                if isinstance(sessions, str):
                    sessions = [sessions]
                for c in ballot["Codes"]:
                    for s in sessions:
                        jobs.append((c, s))

            for code, stop in jobs:
                ok, info = auto.apply_single(
                    entry_url=entry_url,
                    code=code,
                    session_name=stop,
                    seat_keyword=seat_keyword,
                    goods_keyword=goods_keyword,
                    quantity=quantity,
                    username=username,
                    password=password,
                    screenshot_prefix=args.screenshot_prefix,
                )
                results.append((code, stop, ok, info))
                logging.info(f"<iOS Ballot> Code={code} Stop={stop} OK={ok} Info={info}")

    print("\n=== Summary ===", flush=True)
    for code, stop, ok, info in results:
        print(f"  {code} -> {stop}: {'OK' if ok else 'FAILED'} | {info}", flush=True)


if __name__ == "__main__":
    main()
