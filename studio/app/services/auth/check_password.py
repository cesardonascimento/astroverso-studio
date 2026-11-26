import hmac
import time


class CheckPassword:
    def __init__(self, expected: str):
        self.expected = expected

    def execute(self, given: str) -> bool:
        valid = bool(self.expected) and hmac.compare_digest(given.encode(), self.expected.encode())
        if not valid:
            time.sleep(1)
        return valid
