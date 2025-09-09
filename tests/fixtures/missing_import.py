# { "Depends": "py-genlayer:test" }

# Missing: from genlayer import *

class MissingImportContract(gl.Contract):
    value: u256

    def __init__(self, initial_value: int):
        self.value = initial_value

    @gl.public.view
    def get_value(self) -> int:
        return self.value