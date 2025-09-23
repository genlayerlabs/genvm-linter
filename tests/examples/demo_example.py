# { "Depends": "py-genlayer:test" }

from genlayer import *
from dataclasses import dataclass

@allow_storage
@dataclass
class Token:
    symbol: str
    decimals: u8
    total_supply: u256

class TokenManager(gl.Contract):
    tokens: TreeMap[str, Token]
    owner: Address
    paused: bool

    def __init__(self, owner_address: str):
        self.owner = Address(owner_address)
        self.paused = False

    @gl.public.write
    def create_token(self, symbol: str, decimals: int, supply: int):
        if self.paused:
            raise gl.Rollback("Contract is paused")
        
        token = Token(symbol=symbol, decimals=decimals, total_supply=supply)
        self.tokens[symbol] = token
        # The linter detects this modifies state correctly now

    @gl.public.view
    def get_token(self, symbol: str) -> dict:
        token = self.tokens.get(symbol)
        if token:
            return {
                "symbol": token.symbol,
                "decimals": token.decimals,
                "total_supply": token.total_supply
            }
        return {}

    @gl.public.write
    def pause(self):
        if gl.message.sender_address != self.owner:
            raise gl.Rollback("Only owner can pause")
        self.paused = True

    @gl.public.view
    def is_paused(self) -> bool:
        return self.paused

    def _validate_owner(self) -> bool:
        return gl.message.sender_address == self.owner