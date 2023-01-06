import time
from typing import Callable, Optional

from classes.Database import Database
from classes.Command import Command
from utils import is_valid_phone_number, normalize_phone_number


def send_executor(
    user_name: str,
    phone_number: str,
    command_params: list[str],
    db: Database,
    go_to_chat: Callable[[str], bool],
    send_message: Callable[[str, Optional[bool]], None],
) -> None:
    if not command_params or len(command_params) < 2:
        return send_message("```You need to provide a phone number and a message!```")

    to_phone_number, message = command_params[:2]
    normalized_to_phone_number = normalize_phone_number(phone_number)

    if db.is_number_banned(normalized_to_phone_number):
        return send_message("```This phone number is banned.```")

    if not is_valid_phone_number(to_phone_number):
        return send_message(
            "```Invalid phone number!```\n\nCopy the phone number from the contact's WhatsApp profile."
        )

    send_message("```Sending message...```")
    time.sleep(1)

    inside_chat = go_to_chat(normalized_to_phone_number)
    if inside_chat:
        send_message(
            f"{message}\n\nSent by: *{user_name}* ({phone_number}).", sent_by_user=True
        )


send = Command(
    name="send",
    parameters=["phone number", "message"],
    description="Sends a message to a specified phone number, clarifying that it is your message.",
    executor=send_executor,
    args=[
        "user_name",
        "phone_number",
        "command_params",
        "_db",
        "_go_to_chat",
        "_send_message",
    ],
)
