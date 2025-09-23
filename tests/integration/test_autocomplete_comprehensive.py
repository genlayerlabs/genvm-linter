# { "Depends": "py-genlayer:test" }

from genlayer import *

class ComprehensiveTest(gl.Contract):
    my_map: TreeMap[str, u64]
    my_array: DynArray[Address]
    
    def __init__(self):
        pass
    
    @gl.public.view
    def test_all_autocomplete_scenarios(self) -> int:
        # Test 1: gl. should immediately show completions
        gl.  # ← Should show: trace, message, eq_principle, nondet, storage, vm, advanced, etc.
        
        # Test 2: gl.message should show properties  
        sender = gl.message.  # ← Should show: sender_address, contract_address, origin_address, value, chain_id
        
        # Test 3: Address constructor should be suggested
        Addr  # ← Should show: Address(...)
        
        # Test 4: Address methods after assignment
        address1 = Address("0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        hex_val = address1.  # ← Should show: as_hex, as_bytes, as_b64, as_int
        
        # Test 5: Property type inference
        contract_addr = gl.message.contract_address  # Address type
        hex_string = contract_addr.  # ← Should show Address methods
        
        # Test 6: Storage collections
        my_storage_map = TreeMap[str, u64]()
        my_storage_map.  # ← Should show: get, keys, values, items, clear, pop, etc.
        
        my_storage_array = DynArray[u64]()
        my_storage_array.  # ← Should show: append, insert, remove, pop, clear, etc.
        
        # Test 7: Web responses
        response = gl.nondet.web.get("https://example.com").get()
        status = response.  # ← Should show: status, headers, body
        
        # Test 8: Images
        image = gl.nondet.web.render("https://example.com", mode="screenshot").get()
        raw_bytes = image.  # ← Should show: raw, pil
        
        # Test 9: Lazy objects
        lazy_result = gl.eq_principle.strict_eq(lambda: "test")
        value = lazy_result.  # ← Should show: get()
        
        # Test 10: Contract properties
        balance = self.  # ← Should show: balance, address (plus user-defined methods)
        
        # Test 11: All gl modules
        gl.eq_principle.  # ← Should show: strict_eq, prompt_comparative, prompt_non_comparative
        gl.nondet.  # ← Should show: exec_prompt, web
        gl.nondet.web.  # ← Should show: render, request, get, post, delete, head, patch
        gl.storage.  # ← Should show: inmem_allocate
        gl.advanced.  # ← Should show: emit_raw_event, user_error_immediate
        gl.vm.  # ← Should show: spawn_sandbox, run_nondet, run_nondet_unsafe, unpack_result
        
        # Test 12: Type constructors with snippets
        addr2 = Address("0x123...")  # Should provide constructor snippet
        val1 = u64(100)  # Should provide constructor snippet  
        val2 = i32(-50)  # Should provide constructor snippet
        
        return 42