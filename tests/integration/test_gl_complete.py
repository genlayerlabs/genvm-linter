# { "Depends": "py-genlayer:test" }
from genlayer import *

class TestContract(gl.Contract):
    owner: Address
    data: TreeMap[str, int]
    
    def __init__(self):
        # Test gl.message attributes
        self.owner = gl.message.sender_address
        sender = gl.message.sender  # Alias
        contract = gl.message.contract_address
        value = gl.message.value
        chain = gl.message.chain_id
        
        # Test gl.deploy_contract
        new_contract = gl.deploy_contract(
            code=b"contract code",
            args=["arg1", "arg2"],
            salt_nonce=1,
            on="accepted"
        )
        
        # Test gl.get_contract_at
        contract_ref = gl.get_contract_at(new_contract)
        
        # Test balance property
        my_balance = self.balance
    
    @gl.public.write
    def test_submodules(self):
        # Test gl.advanced
        gl.advanced.user_error_immediate("Error message")
        
        # Test gl.vm
        try:
            raise gl.vm.UserError("User error")
        except gl.vm.VMError:
            pass
        
        result = gl.vm.run_nondet(lambda: "test")
        sandbox = gl.vm.spawn_sandbox()
        
        # Test gl.storage
        root = gl.storage.Root()
        gl.storage.copy_to_memory(b"data")
        gl.storage.inmem_allocate(100)
    
    @gl.public.write.payable
    def receive_payment(self):
        return True
    
    @gl.public.view
    def get_owner(self) -> Address:
        return self.owner

@gl.evm.contract_interface
class EthContract:
    pass

@gl.contract_interface
class AnotherInterface:
    pass
