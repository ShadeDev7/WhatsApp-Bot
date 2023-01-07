class Roles:
    DEFAULT = USER = "USER"
    MODERATOR = "MODERATOR"
    ADMIN = "ADMIN"
    OWNER = "OWNER"
    STAFF = [MODERATOR, ADMIN, OWNER]
    ALL_ROLES = [USER, MODERATOR, ADMIN, OWNER]
