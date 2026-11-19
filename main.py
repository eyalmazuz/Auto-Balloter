import argparse
import os
import time
import tomllib
from typing import Any, Dict, List, Optional, Union
import logging
logger = logging.getLogger()
from enum import Enum
import unicodedata

import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


def xpath_literal(value: str) -> str:
    """Safely quote an arbitrary string for use as an XPath 1.0 string literal."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


MOBILE_DEVICE_PRESETS: Dict[str, Dict[str, Any]] = {
    "iPhone 15 Pro": {
        "width": 393,
        "height": 852,
        "pixelRatio": 3.0,
        "userAgent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
        ),
        "platform": "iPhone",
        "vendor": "Apple Computer, Inc.",
        "maxTouchPoints": 5,
        "userAgentMetadata": {
            "mobile": True,
            "platform": "iOS",
            "platformVersion": "17.5.0",
            "architecture": "",
            "model": "iPhone",
        },
    },
    "Pixel 8": {
        "width": 412,
        "height": 915,
        "pixelRatio": 2.625,
        "userAgent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
        ),
        "platform": "Linux armv8l",
        "vendor": "Google Inc.",
        "maxTouchPoints": 5,
        "userAgentMetadata": {
            "brands": [
                {"brand": "Not/A)Brand", "version": "8"},
                {"brand": "Chromium", "version": "126"},
                {"brand": "Google Chrome", "version": "126"},
            ],
            "fullVersionList": [
                {"brand": "Not/A)Brand", "version": "8.0.0.0"},
                {"brand": "Chromium", "version": "126.0.6478.122"},
                {"brand": "Google Chrome", "version": "126.0.6478.122"},
            ],
            "mobile": True,
            "platform": "Android",
            "platformVersion": "14.0.0",
            "architecture": "",
            "model": "Pixel 8",
        },
    },
}


def create_driver(
    mobile_emulation: bool = True,
    device_name: str = "Pixel 8",
) -> WebDriver:
    """Create an undetected_chromedriver instance with optional full mobile device emulation."""
    preset = MOBILE_DEVICE_PRESETS.get(device_name, MOBILE_DEVICE_PRESETS["Pixel 8"])
    options = uc.ChromeOptions()

    if mobile_emulation:
        options.add_argument(f"--user-agent={preset['userAgent']}")
    options.add_argument("--start-maximized")

    # Ensure ChromiumService passes --disable-build-check so minor Chrome/ChromeDriver version skew works
    orig_service_init = webdriver.chromium.service.ChromiumService.__init__

    def _patched_service_init(self, *args, **kwargs):
        service_args = list(kwargs.get("service_args") or [])
        if "--disable-build-check" not in service_args:
            service_args.append("--disable-build-check")
        kwargs["service_args"] = service_args
        orig_service_init(self, *args, **kwargs)

    webdriver.chromium.service.ChromiumService.__init__ = _patched_service_init
    try:
        default_uc_binary = os.path.expanduser(
            "~/Library/Application Support/undetected_chromedriver/undetected_chromedriver"
        )
        driver_exe = default_uc_binary if os.path.exists(default_uc_binary) else None
        driver = uc.Chrome(options=options, driver_executable_path=driver_exe)
    finally:
        webdriver.chromium.service.ChromiumService.__init__ = orig_service_init

    try:
        driver.maximize_window()
    except Exception:
        pass

    if mobile_emulation:
        apply_mobile_emulation_cdp(driver, preset)
        logging.info(f"<Mobile Emulation> Enabled preset: {device_name}")

    return driver


def apply_mobile_emulation_cdp(driver: WebDriver, preset: Dict[str, Any]) -> None:
    """Apply CDP overrides for User-Agent, Client Hints, viewport metrics, and touch capability."""
    ua_override: Dict[str, Any] = {
        "userAgent": preset["userAgent"],
        "acceptLanguage": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "platform": preset["platform"],
    }
    if "userAgentMetadata" in preset:
        ua_override["userAgentMetadata"] = preset["userAgentMetadata"]

    driver.execute_cdp_cmd("Network.setUserAgentOverride", ua_override)
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": preset["width"],
            "height": preset["height"],
            "deviceScaleFactor": preset["pixelRatio"],
            "mobile": True,
            "screenWidth": preset["width"],
            "screenHeight": preset["height"],
        },
    )


# Thanks ChatGPT
def half_width_to_full_width(text):
    """
    Convert half-width characters to full-width characters.
    
    Parameters:
        text (str): The input string containing half-width characters.
        
    Returns:
        str: A string with full-width characters.
    """
    full_width_text = ''
    for char in text:
        # Check if the character is half-width and convert to full-width
        if unicodedata.east_asian_width(char) == 'Na':  # Narrow (half-width) characters
            code_point = ord(char)
            if 0x21 <= code_point <= 0x7E:  # ASCII printable range
                char = chr(code_point + 0xFEE0)  # Convert to full-width
        full_width_text += char
    return full_width_text


class Status(Enum):
    VALID_CODE = 0
    INVALID_CODE = 1
    USED_CODE = 2


def safe_click(driver: WebDriver, element: WebElement) -> None:
    """Reliably click an element under CDP mobile emulation."""
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'}); arguments[0].click();",
        element,
    )


def safe_fill_input(driver: WebDriver, element: WebElement, text: str) -> None:
    """Reliably fill an input element under CDP mobile emulation."""
    driver.execute_script(
        """
        arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});
        arguments[0].focus();
        arguments[0].value = '';
        """,
        element,
    )
    element.send_keys(text)
    if element.get_attribute("value") != text:
        driver.execute_script(
            """
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """,
            element,
            text,
        )

def get_session_element(driver: WebDriver, session_name: str) -> WebElement:
    elem = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.LINK_TEXT, "＜{0}＞お申込み".format(session_name))
        )
    )

    return elem


def apply_for_single_session(
    driver: WebDriver, session_name: str, code: str, has_session_selection: bool, **ballot_info
) -> Status:
    if has_session_selection:
        session_button = get_session_element(driver, session_name)
        logging.info(f"<Session> Applying to {session_name}")
        session_button.click()
        WebDriverWait(driver, 10).until(
            EC.all_of(
                EC.presence_of_element_located(
                    (By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']")
                ),
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'お申込みへ')]")),
            )
        )
    serial_code_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']")
        )
    )

    logging.info("<Status> Filling code")
    safe_fill_input(driver, serial_code_box, code)

    apply_button = driver.find_element(By.XPATH, "//button[contains(text(),'お申込みへ')]")
    safe_click(driver, apply_button)

    # Waiting until the new page loads or an error message pops out
    WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='次へ' and @data-title]")),
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//div[@name='ninsho_key_whole_error_info']/p[contains(text(),'ません')]",
                )
            ),
        )
    )

    # Figure out if there is an error message
    try:
        error_message = driver.find_element(
            By.XPATH,
            "//div[@name='ninsho_key_whole_error_info']/p[contains(text(),'ません')]",
        )
        if error_message:
            error_msg = error_message.text
            if "利用回数を超えた" in error_msg:
                return Status.USED_CODE
            elif "正しくありません" in error_msg:
                return Status.INVALID_CODE
    except Exception:
        pass

    # If multiple tour stops appear after serial entry (e.g. 東京公演 / 愛知公演 / 福岡公演), pick the matching stop's 次へ button
    matching_next_buttons = []
    if session_name and session_name != "All":
        session_lit = xpath_literal(session_name)
        matching_next_buttons = driver.find_elements(
            By.XPATH,
            f"(//*[contains(text(),{session_lit})]/following::button[text()='次へ' and @data-title])[1]",
        )
    if matching_next_buttons:
        apply_button = matching_next_buttons[0]
        logging.info(f"<Session> Selecting post-serial tour stop: {session_name}")
    else:
        apply_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='次へ' and @data-title]"))
        )

    time.sleep(1.5)
    safe_click(driver, apply_button)

    # Some events open a terms agreement modal (各種注意事項に同意します); others navigate directly to sp.atom.eplus.jp
    WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.url_contains("atom.eplus.jp"),
            EC.element_to_be_clickable(
                (By.XPATH, "//label[contains(text(),'各種注意事項に同意します')]")
            ),
        )
    )

    if "atom.eplus.jp" not in driver.current_url:
        checkbox = driver.find_element(
            By.XPATH, "//label[contains(text(),'各種注意事項に同意します')]"
        )
        safe_click(driver, checkbox)

        modal_submit = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='次へ' and @type='submit']")
            )
        )
        safe_click(driver, modal_submit)

    WebDriverWait(driver, 15).until(EC.url_contains("atom.eplus.jp"))
    time.sleep(1.5)
    return Status.VALID_CODE


def login(
    driver: WebDriver,
    username: str,
    password: str,
    interactive: bool = False,
) -> None:
    WebDriverWait(driver, 15).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//a[contains(text(),'ログイン画面へ')]")),
            EC.presence_of_element_located((By.ID, "loginId")),
            EC.presence_of_element_located((By.XPATH, "//select[option[contains(text(),'選択して')]]")),
        )
    )
    if driver.find_elements(By.XPATH, "//select[option[contains(text(),'選択して')]]"):
        logging.info("<Login> Already logged in on sp.atom.eplus.jp.")
        return

    if interactive:
        logging.info(f"<Login> Interactive mode waiting for user at URL={driver.current_url}")
        print(
            "\n>>> [ACTION REQUIRED] In the opened Chrome window, please click 'ログイン画面へ' and sign in with your E+ email & password (waiting up to 180s)... <<<",
            flush=True,
        )
        saw_auth = {"flag": False}

        def _is_post_login_ready(drv: WebDriver) -> bool:
            try:
                url = drv.current_url or ""
                if "member.eplus.jp" in url:
                    saw_auth["flag"] = True
                    return False
                if "atom.eplus.jp" in url:
                    has_login_link = (
                        len(drv.find_elements(By.XPATH, "//a[contains(text(),'ログイン画面へ')]")) > 0
                    )
                    if saw_auth["flag"] and not has_login_link:
                        return True
                    if len(drv.find_elements(By.TAG_NAME, "select")) > 0:
                        return True
                return False
            except Exception:
                return False

        WebDriverWait(driver, 180).until(_is_post_login_ready)
        logging.info(f"<Login> Interactive login completed; returned to URL={driver.current_url}")
        return

    login_links = driver.find_elements(By.XPATH, "//a[contains(text(),'ログイン画面へ')]")
    if login_links:
        WebDriverWait(driver, 15).until(
            lambda drv: drv.execute_script("return document.readyState === 'complete';")
        )
        safe_click(driver, login_links[0])

    username_form = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "loginId"))
    )
    safe_fill_input(driver, username_form, username)

    password_form = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "loginPassword"))
    )
    safe_fill_input(driver, password_form, password)

    login_button = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "idPwLogin"))
    )
    safe_click(driver, login_button)


def get_ticket_select_elements(driver: WebDriver) -> List[WebElement]:
    """Return the ticket-quantity <select> elements for both desktop table and mobile stacked DOMs."""
    desktop_selects = driver.find_elements(
        By.XPATH, "//div[contains(@class,'select-area')]//tr/td[3]//select"
    )
    if desktop_selects:
        return desktop_selects

    # Fallback for mobile layout where selects are not inside td[3]
    return driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'select-area')]//select[not(option[contains(text(),'選択して')])]",
    )


def safe_select_by_index(driver: WebDriver, select_el: WebElement, index: int) -> None:
    """Select an <option> by index reliably under CDP mobile emulation."""
    try:
        Select(select_el).select_by_index(index)
    except Exception:
        pass
    selected_idx = driver.execute_script("return arguments[0].selectedIndex;", select_el)
    if selected_idx != index:
        driver.execute_script(
            """
            arguments[0].selectedIndex = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """,
            select_el,
            index,
        )


def ballot_with_goods(
    driver: WebDriver,
    with_goods: bool = False,
    is_pair: bool = False,
    seat_type: Optional[str] = None,
    goods_keyword: Optional[str] = None,
) -> None:
    keyword = goods_keyword or seat_type
    if keyword:
        kw_lit = xpath_literal(keyword)
        xpath = (
            f"//div[contains(@class,'select-area')]//select[option[contains(text(),{kw_lit})]]"
            f" | //tr/td[3]//select[option[contains(text(),{kw_lit})]]"
            f" | //select[option[contains(text(),{kw_lit})]]"
        )
    elif with_goods:
        xpath = (
            "//div[contains(@class,'select-area')]//select[option[contains(text(),'グッズ付き')]]"
            " | //tr/td[3]//select[option[contains(text(),'グッズ付き')]]"
            " | //select[option[contains(text(),'グッズ付き')]]"
        )
    else:
        xpath = (
            "//div[contains(@class,'select-area')]//select[option[contains(text(),'グッズなし') or contains(text(),'グッズ無し')]]"
            " | //tr/td[3]//select[option[contains(text(),'グッズなし') or contains(text(),'グッズ無し')]]"
            " | //select[option[contains(text(),'グッズなし') or contains(text(),'グッズ無し')]]"
        )

    ticket_option = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    safe_select_by_index(driver, ticket_option, int(is_pair) + 1)


def ballot_without_goods(driver: WebDriver, is_pair: bool = False) -> None:
    ticket_selects = get_ticket_select_elements(driver)
    if ticket_selects:
        ticket_option = ticket_selects[0]
    else:
        ticket_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//tr/td[3]//select"))
        )

    safe_select_by_index(driver, ticket_option, int(is_pair) + 1)


def get_number_of_selects(driver: WebDriver) -> int:
    return len(get_ticket_select_elements(driver))


def fill_ballot_info(
    driver: WebDriver,
    with_goods: bool,
    is_pair: bool,
    seat_type: Optional[str] = None,
    goods_keyword: Optional[str] = None,
) -> bool:
    """Fills in the options on the first page after you log in.

    Returns a boolean describing whether you can apply with goods or not."""
    select_count = len(driver.find_elements(By.TAG_NAME, "select"))
    logging.info(f"<Ballot Page> URL={driver.current_url} selects_count={select_count}")

    day_option = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//tr/td[2]//select[option[contains(text(),'選択して')]]"
                " | //div[contains(@class,'select-area')]//select[option[contains(text(),'選択して')]]"
                " | //select[option[contains(text(),'選択して')]]",
            )
        )
    )
    safe_select_by_index(driver, day_option, 1)

    num_selects = get_number_of_selects(driver)
    can_apply_with_goods = num_selects >= 2 or bool(seat_type) or bool(goods_keyword)

    if can_apply_with_goods:
        ballot_with_goods(
            driver, with_goods, is_pair, seat_type=seat_type, goods_keyword=goods_keyword
        )
    else:
        ballot_without_goods(driver, is_pair)

    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//span[@id='enter-bt-zumi']/a[contains(text(),'申込み')]"
                " | //a[text()='申込み']"
                " | //button[contains(text(),'申込み')]",
            )
        )
    )
    safe_click(driver, submit_button)

    return can_apply_with_goods


def select_delivery_method(driver: WebDriver, delivery_method: str = "sumachike") -> None:
    """Selects Sumachike (スマチケ) delivery option if multiple delivery radio buttons are present."""
    if delivery_method.lower() != "sumachike":
        return

    sumachike_radios = driver.find_elements(
        By.XPATH,
        "//label[contains(.,'スマチケ')]//input[@type='radio']"
        " | //tr[contains(.,'スマチケ')]//input[@type='radio']"
        " | //li[contains(.,'スマチケ')]//input[@type='radio']"
        " | //div[contains(@class,'uketori') or contains(@class,'receive') or contains(@class,'sumachike')]//input[@type='radio']",
    )
    if sumachike_radios:
        radio = sumachike_radios[0]
        if not radio.is_selected():
            safe_click(driver, radio)
        logging.info("<Delivery> Selected スマチケ (Sumachike) radio option.")
    else:
        logging.info("<Delivery> No explicit スマチケ radio toggle found (likely pre-selected/fixed).")


def fill_payment_info(driver: WebDriver, delivery_method: str = "sumachike") -> None:
    conbini_option = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//div[@class='con']//input[@type='radio']"
                " | //label[contains(.,'コンビニ')]//input[@type='radio']"
                " | //tr[contains(.,'コンビニ')]//input[@type='radio']",
            )
        )
    )

    safe_click(driver, conbini_option)
    select_delivery_method(driver, delivery_method)

    submit_button = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//span[contains(@class,'enter-bt')]//a[contains(text(),'次へ')]"
                " | //a[text()='次へ']"
                " | //button[contains(text(),'次へ')]",
            )
        )
    )
    safe_click(driver, submit_button)


def has_goods_ballot(driver: WebDriver) -> bool:
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//div[@class='enq-info']"))
        )
        return True
    except Exception:
        return False


def fill_goods_info(
    driver: WebDriver,
    shipping_info: Optional[List[str]] = None,
) -> None:
    body = driver.find_element(
        By.XPATH, "//div[@class='enq-info']//div[@class='cont-block']"
    )
    forms = body.find_elements(By.XPATH, ".//fieldset")
    with_goods = bool(shipping_info)
    for idx, form in enumerate(forms):
        if idx == 0:
            # If with_goods is true we need to click the 0th button ("I verified")
            form.find_elements(By.TAG_NAME, "input")[int(not with_goods)].click()
        elif idx == 1:
            # If with_goods is true we need to click the 1st button ("I didn't verify")
            form.find_elements(By.TAG_NAME, "input")[int(with_goods)].click()
        elif idx == 3 or idx == 4:
            # Half-width fields (phone number and postal code)
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("0")
            else:
                inp.send_keys(shipping_info[idx - 2])
        else:
            # Full-width fields
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("０")
            else:
                full_width_info = half_width_to_full_width(shipping_info[idx - 2])
                inp.send_keys(full_width_info)


def fill_renban_info(driver: WebDriver, renban: Union[Dict[str, str], int]) -> None:
    renban_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//tr/td[2]//select[option[contains(text(),'同行者1を選択してください')]]"
                " | //select[option[contains(text(),'同行者1を選択してください')]]",
            )
        )
    )

    select_renban = Select(renban_form)
    if isinstance(renban, int):
        select_renban.select_by_index(renban)
    elif isinstance(renban, dict) and len(renban) == 2:
        renban_name = f"{renban['name']}（{renban['address']}）"
        for option in select_renban.options:
            if option.text == renban_name:
                option.click()
    else:
        raise ValueError(
            "Renban value is invalid, please either specify a number or a dictionary of two elements with name and address"
        )


def start_single_ballot_process(
    driver: WebDriver,
    entry_url: str,
    delivery_method: str = "sumachike",
    interactive_login: bool = False,
    **ballot_info,
) -> None:
    available_codes = list(ballot_info["Codes"])
    sessions_to_apply_to = ballot_info["Sessions"]

    if isinstance(sessions_to_apply_to, list):
        sessions_to_apply_to = set(sessions_to_apply_to)
    elif isinstance(sessions_to_apply_to, str) and sessions_to_apply_to != "All":
        sessions_to_apply_to = set([sessions_to_apply_to])

    renban_val = ballot_info.get("Renban")
    has_renban = renban_val is not None and renban_val not in [0, -1]
    quantity = int(ballot_info.get("Quantity", 2 if has_renban else 1))
    pair = quantity >= 2 or has_renban
    shipping_info = ballot_info.get("ShippingInfo") or ballot_info.get("GoodsInfo")
    want_goods = bool(shipping_info)
    seat_type = ballot_info.get("SeatKeyword") or ballot_info.get("SeatType")
    goods_keyword = ballot_info.get("GoodsKeyword")

    driver.get(entry_url)
    sessions = driver.find_elements(By.XPATH, "//div[@class='page-content']//a")
    sessions_name = [session.text[1:-5] for session in sessions if session.text.startswith("＜")]
    # Slicing extracts 'xxx' from options in the form of ＜xxx＞お申込み
    has_session_selection = bool(sessions_name)

    if not has_session_selection:
        # No pre-serial session selection page found — use configured sessions as post-serial identifiers
        if isinstance(ballot_info["Sessions"], list):
            sessions_name = list(ballot_info["Sessions"])
        else:
            sessions_name = [ballot_info["Sessions"]]

    attempted_code_status: dict[str, list[str]] = {}
    first_iteration = True

    for code in available_codes:

        logging.info(f"<Application Started> Code: {code}")

        attempted_code_status[code] = []

        for session_name in sessions_name:
            if sessions_to_apply_to == "All" or session_name in sessions_to_apply_to:
                if not first_iteration:
                    driver.delete_all_cookies()
                    driver.get(entry_url)
                    if not driver.find_elements(By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']"):
                        driver.delete_all_cookies()
                        driver.get(entry_url)
                first_iteration = False
                ballot_status = apply_for_single_session(driver, session_name, code, has_session_selection, **ballot_info)

                match ballot_status:
                    case Status.INVALID_CODE:
                        attempted_code_status[code].append(f"Invalid {session_name}")
                        logger.info(f"<Error> Code {code} is invalid.")
                        continue
                    case Status.USED_CODE:
                        attempted_code_status[code].append(f"Used {session_name}")
                        logger.info(f"<Error> Code {code} has been used for {session_name} before.")
                        continue

                username = os.environ.get("EPLUS_USERNAME") or ballot_info["Credentials"]["username"]
                password = os.environ.get("EPLUS_PASSWORD") or ballot_info["Credentials"]["password"]
                login(
                    driver,
                    username,
                    password,
                    interactive=interactive_login,
                )

                can_apply_with_goods = fill_ballot_info(
                    driver,
                    want_goods,
                    pair,
                    seat_type=seat_type,
                    goods_keyword=goods_keyword,
                )
                fill_payment_info(driver, delivery_method=delivery_method)
                if has_renban:
                    fill_renban_info(driver, ballot_info["Renban"])
                if can_apply_with_goods and has_goods_ballot(driver):
                    fill_goods_info(driver, shipping_info)

                confirm_checkbox = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//td[@class='checkbox-area']//label[text()='内容を確認しました']/preceding-sibling::input[@type='checkbox']"
                            " | //label[contains(text(),'内容を確認しました')]/preceding-sibling::input[@type='checkbox']"
                            " | //label[contains(text(),'内容を確認しました')]",
                        )
                    )
                )
                safe_click(driver, confirm_checkbox)

                submit_button = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//span[@id='apply-button-area']//a[contains(text(),'同意して申込み')]"
                            " | //a[contains(text(),'同意して申込み')]"
                            " | //button[contains(text(),'同意して申込み')]",
                        )
                    )
                )
                safe_click(driver, submit_button)
                attempted_code_status[code].append(f"Successful {session_name}")
                logging.info(f"<Application Successful> Code {code}: {session_name}")
                print(f"[SUCCESS] Completed ballot application for Code={code}, Session={session_name}", flush=True)

    # Start Final Report
    logging.info("---Process Complete---")
    for code, status in attempted_code_status.items():
        logging.info(f"{code}: {status}")
    logging.info("---End of Report---")


def verify_mobile_fingerprint(driver: WebDriver, url: Optional[str] = None) -> None:
    """Verify the active mobile emulation properties inside the browser."""
    target_url = url or "https://eplus.jp/"
    driver.get(target_url)
    fingerprint = driver.execute_script(
        """
        return {
            url: window.location.href,
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            vendor: navigator.vendor,
            maxTouchPoints: navigator.maxTouchPoints,
            hasOntouchstart: 'ontouchstart' in window,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            devicePixelRatio: window.devicePixelRatio,
            userAgentDataMobile: navigator.userAgentData ? navigator.userAgentData.mobile : null
        };
        """
    )
    print("Mobile Emulation Fingerprint:", fingerprint)
    logging.info(f"<Mobile Verification> {fingerprint}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E+ Auto-Balloter with mobile emulation")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Disable mobile emulation and force desktop browser mode",
    )
    parser.add_argument(
        "--device",
        default=None,
        choices=list(MOBILE_DEVICE_PRESETS.keys()),
        help="Override mobile device preset",
    )
    parser.add_argument(
        "--verify-mobile",
        action="store_true",
        help="Launch browser, print mobile fingerprint on the configured URL, and exit",
    )
    parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Pause at member.eplus.jp/auth so you can complete login manually in the browser window",
    )
    args = parser.parse_args()

    with open(args.config, "rb") as fd:
        config = tomllib.load(fd)

    logging.basicConfig(
        filename="apply.log",
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        filemode="a"
    )

    mobile_emulation = False if args.desktop else config.get("MobileEmulation", True)
    device_name = args.device or config.get("MobileDevice", "Pixel 8")
    delivery_method = config.get("DeliveryMethod", "sumachike")

    driver = create_driver(mobile_emulation=mobile_emulation, device_name=device_name)

    try:
        if args.verify_mobile:
            verify_mobile_fingerprint(driver, config.get("URL"))
            return

        for ballot_info in config["Ballots"]:
            start_single_ballot_process(
                driver,
                config["URL"],
                delivery_method=delivery_method,
                interactive_login=args.interactive_login,
                **ballot_info,
            )
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
