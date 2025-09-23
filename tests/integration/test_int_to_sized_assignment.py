# { "Depends": "py-genlayer:test" }
from genlayer import *

class TestContract(gl.Contract):
    # Storage fields with sized types
    campaign_duration_periods: u256
    user_count: u64
    balance: u128
    small_value: u8
    signed_value: i64
    big_number: bigint
    
    def __init__(self):
        self.campaign_duration_periods = u256(0)
        self.user_count = u64(0)
        self.balance = u128(0)
        self.small_value = u8(0)
        self.signed_value = i64(0)
        self.big_number = bigint(0)
    
    @gl.public.write
    def set_values(
        self,
        campaign_duration_periods: int,  # Must be int in method signature
        user_count: int,
        balance: int,
        small_value: int,
        signed_value: int,
        big_number: int
    ):
        # These assignments should all work - int to sized type storage
        self.campaign_duration_periods = campaign_duration_periods
        self.user_count = user_count
        self.balance = balance
        self.small_value = small_value
        self.signed_value = signed_value
        self.big_number = big_number
        
        # Also test direct int literals
        self.campaign_duration_periods = 1000
        self.user_count = 50
        
    @gl.public.view
    def get_duration(self) -> int:  # Must return int, not u256
        return int(self.campaign_duration_periods)
