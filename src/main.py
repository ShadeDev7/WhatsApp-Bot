import os

from classes import Bot
from constants import VERSION


def main():
    os.system(f"title WhatsApp Bot v{VERSION} by ShadeDev7")

    bot = Bot()


if __name__ == "__main__":
    main()
