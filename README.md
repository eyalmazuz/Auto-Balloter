# Auto-Balloter
This is a software to ease applying to Japanese events on the website [eplus](https://eplus.jp)

## Disclaimer

THIS SOFTWARE IS PROVIDED “AS IS” WITHOUT WARRANTY OF ANY KIND AND
IS TO BE USED AT YOUR OWN RISK. BY USING THIS SOFTWARE, YOU AGREE THAT
THE AUTHORS OR CONTRIBUTORS ARE NOT LIABLE FOR ANY DAMAGES OR CLAIMS OR ANYTHING AT ALL
ARISING FROM ITS USE. NO GUARANTEE OF SUPPORT OR UPDATES IS PROVIDED.

[Full License Here](./LICENSE)


# Features
- [x] Multiple accounts
- [x] Multiple codes
- [x] Single/renban application
- [x] Conbini payment
- [x] Application with goods (no support for address filling yet)
- [ ] Credit card payment
- [ ] Bank account payment

# Requirements
This code relies on chrome-based browsers to apply
so before you run the code please install [google-chrome](https://www.google.com/chrome/) or [chromium](https://chromium.woolyss.com/download/)

The project uses [uv](https://docs.astral.sh/uv/) for dependency and environment management:

```bash
uv sync
```

# How to run
1. Set the config file as explained below
2. Verify mobile emulation fingerprint (optional dry check):
   ```bash
   uv run main.py --verify-mobile
   ```
3. Run the balloter:
   ```bash
   uv run main.py
   ```
4. Wait and enjoy

## iOS Simulator Sumachike Automation (`ios_balloter.py`)
For smartphone-only Sumachike (`スマチケ`) receptions gated by Akamai Bot Manager, use [ios_balloter.py](./ios_balloter.py), which drives genuine Mobile Safari inside a booted Xcode iOS Simulator via Appium XCUITest (native UI mode, so `navigator.webdriver` stays `false`):

```bash
# 1. Boot an iOS Simulator and start Appium (one-time: `npm install -g appium && appium driver install xcuitest`)
xcrun simctl boot <UDID>
appium --port 4723

# 2. Run all configured ballots (auto-detects the booted iPhone Simulator)
uv run ios_balloter.py

# Or run specific code:session pairs
uv run ios_balloter.py --pairs <SERIAL>:福岡公演

# Agent / non-interactive first-time email OTP (メールアドレス認証) support:
uv run ios_balloter.py --otp-file ~/.cache/auto-balloter/otp.txt
# or fetch automatically via a trusted local command:
uv run ios_balloter.py --otp-cmd "your-gmail-otp-helper"
```

### Credential Safety
Because `config.toml` is tracked in git, either keep placeholder credentials in `config.toml` and pass your real login via environment variables (`EPLUS_USERNAME` / `EPLUS_PASSWORD`), or mark your local copy untracked with:

```bash
git update-index --skip-worktree config.toml
```

### Agent Skill
This repository also includes a workspace Agent Skill at [`.agents/skills/eplus-sumachike-balloter/SKILL.md`](./.agents/skills/eplus-sumachike-balloter/SKILL.md) so AI coding agents (Antigravity, Claude Code, Codex, etc.) can automatically discover and run the iOS Simulator Sumachike workflow, including first-time email OTP verification via `--otp-file`.

# Config file
This scripts uses a [TOML](https://toml.io/en/) config format

When apply for each account, each account is separated by the ``[[Ballots]]`` header (key).

### Basic config  example
Here is an example of single account config option:
```
URL = "https://eplus.jp/aqours-finale-cd"
# The entry page for the event you apply to
# This is currently working only for love live serial events

[[Ballots]]
Credentials = { username = "an@example.com", password = "NonakaCocona" }
# The login info for your eplus account

Codes = ["aaa", "bbb"]
# All the codes you want to apply for this specific account

Sessions = "All"
# You can specify a list or you can just write "All" if you want to apply for all sessions.
# Supported options are: "昼公演", "夜公演", "Day.1", "Day.2", and "All"
# Examples:
# Sessions = ["昼公演"]
# Sessions = ["昼公演", "夜公演"]
# Sessions = "All"

Renban = 1 # or { name = "ふううばる", address = "mail@address.com" }
# if you want to apply allow, add the symbol: # at the beginning of the line
# If your renban list is A, B, C, ..., the value you should pick is:
# A -> 1
# B -> 2
# C -> 3
# ...
# You can also find this as the "No" of the person on
# https://member.eplus.jp/update-dokosha
# You can also specify the renban by his name and address as a mapping as seen above
# copy the "同行者名" without any spaces into the "name" field
# and "メールアドレス" to the address key

ShippingInfo = [] # If you don't want goods, keep it empty aka only the: []
# if you want goods you need to fill your information in a very specific order:
# [Name, Phone, zip, Prefecture, City, Address 1, Address 2]
# 1. Full Name in full-width characters
# 2. Phone number in half-width characters
# 3. zip code in half-width characters
# 4. Prefecture in full-width characters
# 5. City in full-width characters
# 6. Address 1 in full-width characters
# 7. Address 2 in full-width characters
# e.g., GoodsInfo = ["ＦＯＯ　ＢＡＲ", "+815050505050", "123-0123", "ＴＯＫＹＯ", "ＡＫＩＨＡＢＡＲＡ", "ＡＤＤＲＥＳＳ　１"，　"ＡＤＤＲＥＳＳ ２"]
```

### Multiple account example
If you want to apply with multiple accounts then copy the entire block starting from ``[[Ballots]]``
and create another copy below

For example:
```
URL = "http://eplus.jp/event_name"

[[Ballots]]
Credentials = { username = "username@email.com", password = "password" }

Codes = ["aaa", "bbb"]

Sessions = "All"

Renban = 1 # or { name = "ふううばる", address = "mail@address.com" }

ShippingInfo = []

[[Ballots]]
Credentials = { username = "another@account.com", password = "password" }

Codes = ["more", "and", "different", "codes"]

Sessions = "Day.1"

Renban = { name = "田中", address = "onitsuka@tiger.com" }

GoodsInfo = ["ＦＯＯ　ＢＡＲ", "+815050505050", "123-0123", "ＴＯＫＹＯ", "ＡＫＩＨＡＢＡＲＡ", "ＡＤＤＲＥＳＳ　１"，　"ＡＤＤＲＥＳＳ ２"]
```
