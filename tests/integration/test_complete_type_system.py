# { "Depends": "py-genlayer:test" }
from genlayer import *
from dataclasses import dataclass

@dataclass
@allow_storage
class Campaign:
    id: str
    duration: u256
    participants: DynArray[str]

class CompleteContract(gl.Contract):
    # Storage with sized types
    owner: Address
    campaign_duration: u256
    max_participants: u64
    campaigns: DynArray[Campaign]
    balances: TreeMap[str, u256]
    
    def __init__(self, initial_duration: int):
        # int parameter to sized type field - should work
        self.campaign_duration = initial_duration
        self.max_participants = 100  # literal int to u64
        self.owner = gl.message.sender_address
        self.campaigns = DynArray()
        self.balances = TreeMap()
    
    @gl.public.write
    def create_campaign(
        self,
        id: str,
        duration: int,  # Must be int, not u256
        participant_list: list[str]  # Must be list, not DynArray
    ) -> str:
        # Create campaign with int -> u256 conversion
        campaign = Campaign(
            id=id,
            duration=duration,  # int -> u256 in dataclass
            participants=participant_list  # list -> DynArray
        )
        self.campaigns.append(campaign)
        
        # Assign int to sized type storage
        self.campaign_duration = duration
        
        # Use gl.vm types
        result = gl.vm.spawn_sandbox(lambda: "created")
        if isinstance(result, gl.vm.Return):
            return result.calldata
        return "failed"
    
    @gl.public.view
    def get_campaign_duration(self) -> int:  # Return int, not u256
        return int(self.campaign_duration)
    
    @gl.public.view
    def get_campaigns(self) -> list[Campaign]:  # Return list, not DynArray
        return self.campaigns
