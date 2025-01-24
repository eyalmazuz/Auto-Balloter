import time
import tomllib
from typing import Dict, List, Optional, Union
import logging
logger = logging.getLogger()
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import undetected_chromedriver as uc




class Status(Enum):
    VALID_CODE = 0
    INVALID_CODE = 1
    USED_CODE = 2

def get_session_element(driver: WebDriver, session_name: str) -> WebElement:
    elem = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.LINK_TEXT, "＜{0}＞お申込み".format(session_name))
        )
    )

    return elem


def apply_for_single_session(
    driver: WebDriver, session_name: str, code: str, **ballot_info
) -> Status:
    # TODO: generalize to sessions that aren't "Day.1/Day.2" or "昼公演/夜公演"
    session_button = get_session_element(driver, session_name)
    logging.info(f"<Session> Applying to {session_name}")
    session_button.click()
    WebDriverWait(driver, 10).until(
        EC.all_of(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']")
            ),
            EC.element_to_be_clickable((By.XPATH, "//button[text()='お申込みへ']")),
        )
    )
    serial_code_box = driver.find_element(
        By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']"
    )

    logging.info("<Status> Filling code")
    serial_code_box.send_keys(code)

    apply_button = driver.find_element(By.XPATH, "//button[text()='お申込みへ']")
    apply_button.click()

    # Waiting until the new page loads or an error message pops out
    WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[text()='申込む' and @data-title='★ 必ずお読みください ★']",
                )
            ),
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//div[@name='ninsho_key_whole_error_info']/p[contains(text(),'ません')]"
                )
            )
        )
    )

    # Figure out if there is an error message
    try:
        error_message = driver.find_element(
            By.XPATH,
            "//div[@name='ninsho_key_whole_error_info']/p[contains(text(),'ません')]"
        )
        if error_message:
            error_msg = error_message.text
            if error_msg == "利用回数を超えたためお申込みできません。":
                return Status.USED_CODE
            elif error_msg == "申し込み情報が正しくありません。":
                return Status.INVALID_CODE
    except:
        pass

    # Clicking Apply in first page
    apply_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[text()='申込む' and @data-title='★ 必ずお読みください ★']",
            )
        )
    )
    apply_button.click()

    # Checking 各種注意事項に同意します on pop up
    checkbox = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//label[text()='各種注意事項に同意します']")
        )
    )
    checkbox.click()

    # Clicking Apply on popup
    apply_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[text()='申込みへ' and @type='submit']")
        )
    )
    apply_button.click()

    return Status.VALID_CODE


def login(driver: WebDriver, username: str, password: str) -> None:
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@id='login-bt']/a[text()='ログイン画面へ']")
        )
    )
    login_button.click()

    username_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//input[@id='loginId' and @class='inputType01']",
            )
        )
    )
    username_form.send_keys(username)

    password_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//input[@id='loginPassword' and @class='inputType01 passwordInput']",
            )
        )
    )
    password_form.send_keys(password)

    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[@id='idPwLogin' and @type='submit']",
            )
        )
    )

    login_button.click()


def ballot_with_goods(
    driver: WebDriver, with_goods: bool = False, is_pair: bool = False
) -> None:
    if with_goods:
        box_text = "グッズ付き　-----"
    else:
        box_text = "グッズなし　-----"

    ticket_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, f"//tr/td[3]//select[option[text()='{box_text}']]")
        )
    )
    ticket_select = Select(ticket_option)
    ticket_select.select_by_index(is_pair + 1)


def ballot_without_goods(driver: WebDriver, is_pair: bool = False) -> None:
    ticket_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//tr/td[3]//select"))
    )

    ticket_select = Select(ticket_option)
    ticket_select.select_by_index(is_pair + 1)


def get_number_of_selects(driver: WebDriver) -> int:
    ballot_element = driver.find_element(
        By.XPATH, "//div[@class='select-area']//tr/td[3]"
    )

    select_elements = ballot_element.find_elements(By.TAG_NAME, "select")
    return len(select_elements)


def fill_ballot_info(driver: WebDriver, with_goods: bool, is_pair: bool) -> bool:
    """Fills in the options on the first page after you log in.

    Returns a boolean describing whether you can apply with goods or not."""
    day_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//tr/td[2]//select[option[text()='選択して下さい']]")
        )
    )
    day_select = Select(day_option)
    day_select.select_by_index(1)

    num_selects = get_number_of_selects(driver)
    can_apply_with_goods = num_selects == 2

    if can_apply_with_goods:
        ballot_with_goods(driver, with_goods, is_pair)
    else:
        ballot_without_goods(driver, is_pair)

    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@id='enter-bt-zumi']/a[text()='申込み']")
        )
    )
    submit_button.click()

    return can_apply_with_goods


def fill_payment_info(driver: WebDriver) -> None:
    conbini_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[@class='con']//input[@type='radio']")
        )
    )

    conbini_option.click()

    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@class='enter-bt']//*/a[text()='次へ']")
        )
    )
    submit_button.click()


def has_goods_ballot(driver: WebDriver) -> bool:
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//div[@class='enq-info']"))
        )
        return True
    except:
        return False


def fill_goods_info(
    driver: WebDriver,
    with_goods: bool = False,
    shipping_info: Optional[List[str]] = None,
) -> None:
    body = driver.find_element(
        By.XPATH, "//div[@class='enq-info']//div[@class='cont-block']"
    )
    forms = body.find_elements(By.XPATH, "//fieldset")

    for idx, form in enumerate(forms):
        if idx == 0:
            # If with_goods is true we need to click the 0th button
            # which is the "I verifed"
            form.find_elements(By.TAG_NAME, "input")[not with_goods].click()
        if idx == 1:
            # If with_goods is true we need to click the 1st button
            # which is the "I didn't verify"
            form.find_elements(By.TAG_NAME, "input")[with_goods].click()

        if idx == 3 or idx == 4:
            # We are at the half width form
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("0")
            else:
                inp.send_keys(shipping_info[idx - 2])

        else:
            # We are at any other form which needs to be filled with full-width 0
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("０")
            else:
                inp.send_keys(shipping_info[idx - 2])


def fill_renban_info(driver: WebDriver, renban: Union[Dict[str, str], int]) -> None:
    renban_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//tr/td[2]//select[option[text()='同行者1を選択してください']]")
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
    driver: WebDriver, entry_url: str, **ballot_info
) -> None:
    available_codes = ballot_info["Codes"]
    sessions_to_apply_to = ballot_info["Sessions"]
    if isinstance(sessions_to_apply_to, list):
        sessions_to_apply_to = set(ballot_info["Sessions"])
    elif isinstance(sessions_to_apply_to, str) and sessions_to_apply_to != "All":
        sessions_to_apply_to = set([sessions_to_apply_to])

    pair = "Renban" in ballot_info
    want_goods = ballot_info.get("WantGoods", False)
    shipping_info = ballot_info.get("Shipping Info", None)

    driver.get(entry_url)
    sessions = driver.find_elements(By.XPATH, "//div[@class='page-content']//a")
    sessions_name = {session.text[1:-5] for session in sessions}
    # Slicing is a bit of bandaid solution since right now
    # All options are in the form of ＜xxx＞お申込み so the slice returns 'xxx'

    attempted_code_status = {}

    while available_codes:

        code = available_codes.pop()

        logging.info(f"<Application Started> Code: {code}")

        attempted_code_status[code] = []

        for session_name in sessions_name:
            if sessions_to_apply_to == "All" or session_name in sessions_to_apply_to:
                driver.get(entry_url)

                ballot_status = apply_for_single_session(driver, session_name, code, **ballot_info)

                match ballot_status:
                    case Status.INVALID_CODE:
                        attempted_code_status[code].append(f"Invalid {session_name}")
                        logger.info(f"<Error> Code {code} is invalid.")
                        continue
                    case Status.USED_CODE:
                        attempted_code_status[code].append(f"Used {session_name}")
                        logger.info(f"<Error> Code {code} has been used for {session_name} before.")
                        continue

                login(
                    driver,
                    ballot_info["Credentials"]["username"],
                    ballot_info["Credentials"]["password"],
                )

                can_apply_with_goods = fill_ballot_info(driver, want_goods, pair)
                fill_payment_info(driver)
                if pair:
                    fill_renban_info(driver, ballot_info["Renban"])
                if can_apply_with_goods and has_goods_ballot(driver):
                    fill_goods_info(driver, want_goods, shipping_info)

                confirm_checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//td[@class='checkbox-area']//label[text()='内容を確認しました']/preceding-sibling::input[@type='checkbox']",
                        )
                    )
                )
                confirm_checkbox.click()

                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//span[@id='apply-button-area']//a[text()='同意して申込み']",
                        )
                    )
                )
                submit_button.click()
                attempted_code_status[code].append(f"Successful {session_name}")
                logging.info(f"<Application Successful> Code {code}: {session_name}")

    # Start Final Report
    logging.info("---Process Complete---")
    for code, status in attempted_code_status.items():
        logging.info(f"{code}: {status}")
    logging.info("---End of Report---")

def main() -> None:
    with open("config.toml", "rb") as fd:
        config = tomllib.load(fd)

    logging.basicConfig(
        filename="apply.log",
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        filemode="a"
    )

    driver = uc.Chrome()

    for ballot_info in config["Ballots"]:
        start_single_ballot_process(driver, config["URL"], **ballot_info)

    driver.close()


if __name__ == "__main__":
    main()
