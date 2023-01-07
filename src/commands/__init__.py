from classes.Command import Command

from .menu import menu
from .whoami import whoami
from .sticker import sticker
from .say import say
from .send import send
from .resources import resources
from .history import history
from .executions import executions
from .ban import ban

commands_dict: dict[str, list[Command]] = {
    "global": [menu, whoami, sticker, say, send],
    "staff": [resources, history, executions, ban],
}
