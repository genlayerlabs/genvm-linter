# { "Depends": "py-genlayer:test" }

import typing
from dataclasses import dataclass

from genlayer import *


@dataclass
class Campaign:
    id: str
    title: str
    goal: str
    knowledge_base: str
    rules: str
    style: str
    start_datetime_iso: str
    campaign_duration_periods: int
    period_length_days: int
    missions: dict[str, dict[str, typing.Any]]
    token: str
    distribution_contract_chain_id: int
    distribution_contract_address: str
    only_verified_users: bool
    minimum_followers: int
    maximum_followers: int
    whitelisted_submitters: DynArray[str]
    alpha: int
    beta: int
    gate_weights: DynArray[int]
    metric_weights: DynArray[int]
    allow_old_tweets: bool
    max_submissions_per_participant: int


class CampaignFactory(gl.Contract):
    contract_addresses: DynArray[str]
    x_id_contract: str
    campaign_code: str
    id_to_address: TreeMap[str, str]
    bridge_sender: Address
    owner: Address
    tweet_api_url: str

    def __init__(
        self,
        x_id_contract: str,
        bridge_sender: str,
        tweet_api_url: str,
    ):
        self.x_id_contract = x_id_contract
        self.bridge_sender = Address(bridge_sender)
        self.owner = gl.message.sender_address
        self.tweet_api_url = tweet_api_url
        with open("/contract/CampaignIC.py", "rt") as f:
            self.campaign_code = f.read()

    @gl.public.write
    def create_campaign(
        self,
        id: str,
        title: str,
        goal: str,
        knowledge_base: str,
        rules: str,
        style: str,
        start_datetime_iso: str,
        campaign_duration_periods: int,
        period_length_days: int,
        missions: dict[str, dict[str, typing.Any]],
        token: str,
        distribution_contract_chain_id: int,
        distribution_contract_address: str,
        only_verified_users: bool,
        minimum_followers: int,
        maximum_followers: int,
        whitelisted_submitters: list[str],
        alpha: int,
        beta: int,
        gate_weights: list[int],
        metric_weights: list[int],
        allow_old_tweets: bool = True,
        max_submissions_per_participant: int = 0,
    ) -> str:
        if id in self.id_to_address:
            raise Exception(f"Id {id} already exists")

        salt_nonce = len(self.contract_addresses) + 1
        
        campaign_address = gl.deploy_contract(
            code=self.campaign_code.encode("utf-8"),
            args=[
                title,
                goal,
                knowledge_base,
            ],
            salt_nonce=salt_nonce,
            on="accepted",
        )

        self.contract_addresses.append(campaign_address.as_hex)
        self.id_to_address[id] = campaign_address.as_hex
        return campaign_address.as_hex

    @gl.public.view
    def get_contract_addresses(self) -> list[str]:
        return self.contract_addresses
