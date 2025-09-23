# { "Depends": "py-genlayer:test" }
from genlayer import *
import typing

class TestVMTypes(gl.Contract):
    
    @gl.public.write
    def test_vm_result(self):
        # Test gl.vm.Result type
        def leader_fn() -> str:
            return "test_result"
        
        def validator_fn(result: gl.vm.Result) -> bool:
            # Check if result is Return type
            if isinstance(result, gl.vm.Return):
                return result.calldata == "test_result"
            return False
        
        # Test run_nondet with all parameters
        value = gl.vm.run_nondet(
            leader_fn,
            validator_fn,
            compare_user_errors=lambda a, b: a.message == b.message,
            compare_vm_errors=lambda a, b: a.message == b.message
        )
        
        # Test spawn_sandbox
        result = gl.vm.spawn_sandbox(lambda: 42, allow_write_ops=True)
        
        # Test unpack_result
        unpacked = gl.vm.unpack_result(result)
        
        # Test UserError and VMError
        try:
            raise gl.vm.UserError("Test error")
        except gl.vm.UserError as e:
            print(e.message)
    
    @gl.public.view
    def test_return_type(self) -> int:
        result: gl.vm.Result[int] = gl.vm.spawn_sandbox(lambda: 100)
        if isinstance(result, gl.vm.Return):
            return result.calldata
        return 0
