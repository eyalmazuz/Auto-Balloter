---
name: eplus-sumachike-balloter
description: >-
  Automate Japanese E+ (イープラス / eplus.jp) smartphone-only Sumachike (スマチケ)
  ticket lottery applications using an Xcode iOS Simulator and Appium XCUITest
  driving genuine Mobile Safari. Use this skill when the user asks to apply for
  E+ Sumachike / smartphone-only serial-code ballots, set up mobile E+ balloting
  on macOS, or handle E+ first-time email OTP verification during automation.
---

# E+ Sumachike iOS Simulator Balloter

Automates E+ (`eplus.jp`) smartphone-only **Sumachike (`スマチケ`)** serial-code lottery applications on macOS by driving genuine Mobile Safari inside an Xcode iOS Simulator through **Appium XCUITest** in native UI mode (`bundleId: com.apple.mobilesafari`).

## Why iOS Simulator + Native XCUITest

- **Desktop Chrome + CDP mobile emulation** unlocks E+'s front-end `sp.atom.eplus.jp` layout, **but** Akamai Bot Manager (`edgesuite.net` / `member.eplus.jp/akam`) blocks the login POST (`Access Denied` / `Error Code 99`) due to TLS/WebGL-vs-User-Agent mismatches and CDP markers.
- **Apple `safaridriver`** sets `navigator.webdriver = true` in Mobile Safari, which Akamai also blocks on `sp.atom.eplus.jp/sys/main.jsp`.
- **Appium XCUITest (`bundleId: com.apple.mobilesafari`)** interacts with clean Mobile Safari strictly via iOS accessibility taps/keystrokes (`navigator.webdriver` stays `false`, real iOS WebKit + Apple TLS stack), passing both E+'s Sumachike mobile check and Akamai.
- **Note on App-Only Receptions (`アプリ限定先行`) & Ticket Download:** Web-based Sumachike ballots can be submitted in the iOS Simulator and downloaded later in the official E+ app on a physical smartphone. Receptions strictly requiring the native E+ app (`アプリ限定`) or venue entry still require a real phone tied to SMS verification.

## Prerequisites (macOS)

1. Install Python dependencies with `uv`:
   ```bash
   uv sync
   ```
2. Install Appium and the XCUITest driver (one-time):
   ```bash
   npm install -g appium
   appium driver install xcuitest
   ```
3. Boot an iPhone Simulator and open the Simulator GUI onscreen (Xcode 27 uses `DeviceHub.app`; older Xcode uses `Simulator.app`):
   ```bash
   xcrun simctl list devices available | grep iPhone
   xcrun simctl boot <IPHONE_UDID>
   open -a Simulator 2>/dev/null || open "$(xcode-select -p)/../Applications/DeviceHub.app"
   ```
4. Start the Appium server daemon:
   ```bash
   appium --port 4723
   ```

## Configuring `config.toml`

Update `config.toml` (never commit real credentials or serial codes to git; prefer passing `EPLUS_USERNAME` and `EPLUS_PASSWORD` as environment variables or running `git update-index --skip-worktree config.toml` locally):

- `URL`: The E+ serial reception URL (e.g., `https://eplus.jp/serial/<event_slug>/`).
- `Codes`: List of serial codes to submit.
- `Sessions`: List of tour stops or sessions matching the text on the E+ page (e.g., `["福岡公演", "愛知公演"]`).
- `SeatKeyword` / `GoodsKeyword`: Substrings matching the seat tier dropdown (`"一般指定席"`) and goods toggle (`"特製グッズ無し"` or `"特製グッズ付き"`).
- `Quantity` & `Renban`:
  - **For Sumachike (`スマチケ`):** Set `Quantity = 2` (or `1`) and **`Renban = 0`**. Sumachike does **not** select companions (`同行者`) at application time—you apply for multiple tickets under your own account and distribute (`分配`) them later in the E+ app after winning.

## Running Ballots & Handling First-Time Email OTP (`メールアドレス認証`)

The first time you sign into `member.eplus.jp` on a newly booted iOS Simulator, E+ sends a 6-digit email verification code (`メールアドレス認証`) and iOS may show a `"Save Password?"` sheet and/or `"同一端末での複数アカウント利用..."` (`追加認証が必要です`) modal.

[ios_balloter.py](../../../ios_balloter.py) handles all of these automatically (`Save Password?` dismissal, `次へ` modal dismissal, numeric keyboard `Done` dismissal, `登録` click, and blank-redirect recovery) using one of three OTP modes:

1. **Agentic / Non-Interactive Mode (`--otp-file`) — Recommended for AI Agents:**
   Launch `ios_balloter.py` in the background with a private per-user path (avoid world-writable `/tmp`):
   ```bash
   uv run ios_balloter.py --otp-file ~/.cache/auto-balloter/otp.txt --screenshot-prefix ~/.cache/auto-balloter/done
   ```
   - Watch stdout for `>>> [OTP REQUIRED] ... Write the 6-digit code to ~/.cache/auto-balloter/otp.txt`.
   - Retrieve the 6-digit code (ask the user or check their email if authorized) and write it with restrictive permissions:
     ```bash
     (umask 077 && printf '123456' > ~/.cache/auto-balloter/otp.txt)
     ```
   - `ios_balloter.py` immediately detects the file, deletes it, enters the code, completes verification, and finishes all remaining ballots automatically (subsequent ballots reuse the verified Mobile Safari session without needing another OTP).

2. **Automated Email Fetch Hook (`--otp-cmd`):**
   If you have a trusted local CLI or script that fetches the latest E+ 6-digit code from your inbox, pass:
   ```bash
   uv run ios_balloter.py --otp-cmd "your-otp-fetcher-command"
   ```

3. **Interactive Terminal Mode:**
   Run directly in a terminal and type the 6-digit code when prompted:
   ```bash
   uv run ios_balloter.py --screenshot-prefix ~/.cache/auto-balloter/done
   ```

4. **Submitting Specific Code/Stop Pairs Only:**
   ```bash
   uv run ios_balloter.py --pairs <SERIAL_1>:福岡公演 <SERIAL_2>:愛知公演
   ```

## Validation Steps

After running `ios_balloter.py`:
1. Confirm stdout prints `[SUCCESS] <code> -> <stop>` for every pair.
2. Inspect the saved completion screenshots (`--screenshot-prefix`) to verify **`申込完了`**, event stop, seat tier, ticket count, and total yen amount.
3. Check `apply.log` for full per-application audit logs.
4. Remind the user to confirm all filings in E+'s **申込み履歴** (`https://eplus.jp/jyoukyou/`) and never commit real credentials in `config.toml`.
