# { "Depends": "py-genlayer:test" }
from genlayer import *

class CampaignFactory(gl.Contract):
    owner: Address
    
    def __init__(self, bridge_sender: str):
        self.owner = gl.message.sender_address
    
    @gl.public.write
    def create_campaign(self, id: str, title: str) -> str:
        campaign_address = gl.deploy_contract(
            code=b"campaign code",
            args=[title, id],
            salt_nonce=1,
            on="accepted"
        )
        return campaign_address.as_hex
    
    @gl.public.write
    def update_owner(self, new_owner: str) -> None:
        if gl.message.sender_address != self.owner:
            raise Exception("Only owner can update")
        self.owner = Address(new_owner)
