import time
import os
import psutil
import subprocess
import shutil
from urllib import request
from zipfile import ZipFile
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    SessionNotCreatedException,
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from .Logger import Logger
from .CommandHandler import CommandHandler
from utils import get_driver_versions, get_brave_version, show_qr, close_qr
from enums import Locators, Timeouts, Attempts, Cooldowns
from exceptions import (
    AlreadyLoggedInException,
    CouldntLogInException,
    CouldntHandleMessageException,
)
from constants import VERSION, BRAVE_PATH, DRIVER_ARGUMENTS


class Bot:
    # Private values
    __logger: Logger
    __command_handler: CommandHandler
    __driver: Chrome

    # Public values
    error: bool
    logged: bool

    def __init__(self) -> None:
        self.__logger = Logger()
        self.error = False
        self.logged = False

        self.__logger.log(f"Starting WhatsApp Bot v{VERSION}...", "DEBUG")
        time.sleep(3)

        if "chromedriver.exe" not in os.listdir("."):
            self.__logger.log("Driver not found! Downloading it...", "DEBUG")

            downloaded = self.__download_driver()

            if not downloaded:
                self.__logger.log("Couldn't download the driver!", "ERROR")
                self.error = True

                return

            self.__logger.log("Driver downloaded successfully.", "EVENT")

        self.__command_handler = CommandHandler(self.__logger, self.__send_message)
        self.__driver = self.__initialize_driver()
        if self.__driver:
            self.__logger.log("Driver initialized.", "EVENT")

    def __download_driver(self) -> bool:
        driver_versions = get_driver_versions()
        brave_version = get_brave_version()

        if not driver_versions or not brave_version:
            return False

        main_version = brave_version.split(".")[0]
        version = driver_versions[0]

        for driver_version in driver_versions:
            if driver_version.startswith(main_version):
                version = driver_version
                break

        url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_win32.zip"
        temp_file = "temp-" + str(int(time.time())) + ".zip"
        request.urlretrieve(url, temp_file)
        ZipFile(temp_file, "r").extractall()
        os.remove(temp_file)

        return True

    def __initialize_driver(self) -> Chrome | None:
        self.__logger.log("Initializing driver...", "DEBUG")

        options = ChromeOptions()
        options.binary_location = BRAVE_PATH + "\\brave.exe"
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        for argument in DRIVER_ARGUMENTS:
            options.add_argument(argument)

        try:
            return Chrome(
                service=Service(executable_path="./chromedriver.exe"), options=options
            )
        except SessionNotCreatedException:
            os.remove("chromedriver.exe")

            self.__logger.log(
                "Invalid driver version! Downloading the correct one..", "DEBUG"
            )

            if not self.__download_driver():
                self.__logger.log("Couldn't download the driver!", "ERROR")
                self.error = True

                return

            return self.__initialize_driver()

    def __await_element_load(
        self, locator: tuple, timeout: int | None = None
    ) -> WebElement | None:
        while True:
            try:
                return WebDriverWait(self.__driver, timeout if timeout else 5).until(
                    EC.presence_of_element_located(locator)
                )
            except TimeoutException:
                if not timeout:
                    continue

                return

    def __find_pinned_chat(self) -> WebElement | None:
        attempt = 1
        while True:
            pinned_chat = self.__await_element_load(
                Locators.PINNED_CHAT, Timeouts.PINNED_CHAT
            )
            if pinned_chat:
                return pinned_chat

            if attempt < Attempts.PINNED_CHAT:
                self.__driver.get("https://web.whatsapp.com")
                self.__logger.log(
                    f"Couldn't find a pinned chat to focus on! Trying again in {Cooldowns.PINNED_CHAT} seconds... ({attempt}/{Attempts.PINNED_CHAT})",
                    "ERROR",
                )
                time.sleep(Cooldowns.PINNED_CHAT)
                attempt += 1

                continue

            self.__logger.log(
                f"Couldn't find a pinned chat to focus on. ({attempt}/{Attempts.PINNED_CHAT})",
                "ERROR",
            )
            self.error = True

            return

    def __get_chat_data(self) -> list[str] | None:
        try:
            self.__driver.find_element(*Locators.CHAT_HEADER).click()
            chat_info = self.__driver.find_element(*Locators.CHAT_INFO)

            try:
                return [
                    element.get_attribute("innerText")
                    for element in [
                        chat_info.find_element(*Locators.BUSINESS_NAME),
                        chat_info.find_element(*Locators.BUSINESS_NUMBER),
                    ]
                ]
            except NoSuchElementException:
                pass

            return [
                element.get_attribute("innerText").replace("~", "")
                for element in [
                    chat_info.find_element(*Locators.PERSON_NAME),
                    chat_info.find_element(*Locators.PERSON_NUMBER),
                ]
            ]
        except NoSuchElementException:
            return

    def __get_message_data(self) -> dict[str, str] | None:
        message_containers = self.__driver.find_elements(*Locators.MESSAGE_CONTAINER)
        if not message_containers:
            return

        message_container = message_containers[-1]

        try:
            message_with_text = message_container.find_element(
                *Locators.MESSAGE_WITH_TEXT
            )
            emojis = message_with_text.find_elements(*Locators.EMOJIS)
            if not emojis:
                return {"type": "text", "value": message_with_text.text}

            for emoji in emojis:
                emoji_char = emoji.get_attribute("data-plain-text")
                self.__driver.execute_script(
                    f"arguments[0].innerHTML='{emoji_char}'", emoji
                )

            message_with_text = message_container.find_element(
                *Locators.MESSAGE_WITH_TEXT
            )

            return {"type": "text", "value": message_with_text.text}
        except NoSuchElementException:
            try:
                image_with_text = message_container.find_element(
                    *Locators.IMAGE_WITH_TEXT
                )
                image_url = image_with_text.get_attribute("src")
                image_text = image_with_text.get_attribute("alt")

                return {"type": "image", "value": image_url, "text": image_text}
            except NoSuchElementException:
                return {"type": "invalid"}

    def __send_message(self, message: str) -> None:
        input_box = self.__driver.find_element(*Locators.INPUT_BOX)

        lines = message.split("\n")
        lines_length = len(lines)
        for index, line in enumerate(lines, start=1):
            input_box.send_keys(line)

            if index != lines_length:
                ActionChains(self.__driver).key_down(Keys.SHIFT).send_keys(
                    Keys.ENTER
                ).key_up(Keys.SHIFT).perform()

        input_box.send_keys(Keys.ENTER)

    def login(self) -> None:
        self.__logger.log("Trying to log in...", "DEBUG")

        attempt = 1
        while True:
            try:
                self.__driver.get("https://web.whatsapp.com")

                qr = self.__await_element_load(Locators.QR, Timeouts.QR)
                if not qr:
                    try:
                        if self.__driver.find_element(*Locators.HEADER):
                            raise AlreadyLoggedInException
                    except NoSuchElementException:
                        raise CouldntLogInException

                self.__logger.log("Awaiting QR code scan...", "DEBUG")

                show_qr(qr.get_attribute("data-ref"))

                if not self.__await_element_load(Locators.HEADER, Timeouts.HEADER):
                    close_qr()

                    raise CouldntLogInException

                close_qr()

                raise AlreadyLoggedInException
            except AlreadyLoggedInException:
                self.__logger.log("Logged in.", "EVENT")
                self.logged = True

                return
            except CouldntLogInException:
                if attempt < Attempts.LOGIN:
                    self.__logger.log(
                        f"Couldn't log in! Trying again in {Cooldowns.LOGIN} seconds... ({attempt}/{Attempts.LOGIN})",
                        "ERROR",
                    )
                    time.sleep(Cooldowns.LOGIN)
                    attempt += 1

                    continue

                self.__logger.log(
                    f"Couldn't log in. ({attempt}/{Attempts.LOGIN})", "ERROR"
                )
                self.error = True

                return

    def handle_messages(self) -> None:
        self.__logger.log("Handling messages...", "DEBUG")

        while True:
            time.sleep(0.25)

            new_chats = self.__driver.find_elements(*Locators.NEW_CHAT)
            if not new_chats:
                continue

            try:
                chat = new_chats[-1].find_element(*Locators.NEW_CHAT_CONTAINER)
            except (NoSuchElementException, StaleElementReferenceException):
                continue

            pinned_chat = self.__find_pinned_chat()
            if not pinned_chat:
                return

            name, number = None, None

            try:
                chat.click()

                chat_data = self.__get_chat_data()
                if not chat_data:
                    pinned_chat.click()

                    continue

                name, number = chat_data

                message_data = self.__get_message_data()
                if not message_data:
                    raise CouldntHandleMessageException

                match message_data["type"]:
                    case "text":
                        self.__command_handler.execute(
                            name, number, message_data["value"]
                        )

                    case "image":
                        self.__logger.log(
                            f"{name} ({number}) sent an image ({message_data['value']}) with the text: '{message_data['text']}'.",
                            "DEBUG",
                        )
            except CouldntHandleMessageException:
                self.__logger.log("There was an error handling a message!", "ERROR")

            except StaleElementReferenceException:  # If we are here and no one has been spamming, there's something wrong.
                self.__logger.log(
                    f"{name if name else 'An user'}{f' ({number})' if number else ''} is probably spamming messages!",
                    "ALERT",
                )

            finally:
                pinned_chat.click()

    def close(self) -> None:
        self.__logger.log("Closing... Please wait!", "CLOSE")

        # As the driver.quit() method doesn't end brave browser processes,
        # the only way I found to do it was killing them manually.
        for process in psutil.process_iter():
            try:
                if (
                    process.name() == "brave.exe"
                    and "--test-type=webdriver" in process.cmdline()
                ):
                    subprocess.call(
                        f"taskkill /pid {process.pid} /f /t",
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
            except:
                continue

        # After killing the browser, we need to delete all the
        # temporal files created by its instance.
        try:
            temp_folder = os.getenv("TEMP")
            if temp_folder:
                shutil.rmtree(temp_folder, ignore_errors=True)
        except:
            return
