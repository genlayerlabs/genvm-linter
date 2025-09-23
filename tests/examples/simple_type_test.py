def get_number() -> int:
    return "string instead of int"  # Type error

def process(x: int) -> str:
    return str(x)

def main():
    result = process("not an int")  # Type error
    return result