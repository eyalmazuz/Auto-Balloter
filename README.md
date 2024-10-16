# Auto-Balloter
This is a software to ease applying to Japanese events on the website [eplus](https://eplus.jp)


# Features
- [x] Multiple accounts
- [x] Multiple codes
- [x] Single/renban application
- [x] Conbini payment
- [ ] Credit card payment
- [ ] Bank account payment
- [ ] Application with goods (no support for address filling yet)

# Requirements
This code relies on chrome-based browsers to apply
so before you run the code please install [google-chrome](https://www.google.com/chrome/) or [chromium](https://chromium.woolyss.com/download/)

The code also relied heavily on Selenium and undetected-chromedriver
Please run:
```
pip install -r requirements.txt
```


# How to run
1. Set the config file as explain below
2. Open powershell/termina/shell
3. Run ``python3 main.py``
4. Wait and enjoy

# Config file
This scripts uses a [TOML](https://toml.io/en/) config format

When apply for each account, each account is separated by the ``[[Ballots]]`` header (key).

### Basic config  example
Here is an example of single account config option:
```
URL = "http://eplus.jp/event_name"
# The entry page for the event you apply to
# This is currently working only for love live serial events

[[Ballots]]
Credentials = { username = "username@email.com", password = "password" }
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

WantGoods = false
# If there are goods, do you want to apply for them?
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

WantGoods = false

[[Ballots]]
Credentials = { username = "another@account.com", password = "password" }

Codes = ["more", "and", "different", "codes"]

Sessions = "Day.1"

Renban = { name = "田中", address = "tanaka@tiger.com" }

WantGoods = false
```


