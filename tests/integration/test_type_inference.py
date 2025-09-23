# { "Depends": "py-genlayer:test" }

from genlayer import *

class TypeInferenceTest(gl.Contract):
    
    def __init__(self):
        pass
    
    @gl.public.view
    def test_address_methods(self) -> int:
        # Test Address constructor - should provide .as_hex, .as_bytes, etc.
        address1 = Address("0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        hex_value = address1.  # <-- Should show: as_hex, as_bytes, as_b64, as_int + methods
        
        # Test gl.message properties - should infer Address type
        address2 = gl.message.sender_address
        sender_hex = address2.  # <-- Should show Address properties/methods
        
        # Test gl.message other properties
        contract_addr = gl.message.contract_address  
        origin_addr = gl.message.origin_address
        value = gl.message.value  # Should be u256
        chain = gl.message.chain_id  # Should be u256
        
        # Test property access type inference
        bytes_data = address1.as_bytes  # Should infer bytes type
        hex_string = address2.as_hex   # Should infer str type
        b64_string = address1.as_b64   # Should infer str type
        int_value = address2.as_int    # Should infer u160 type
        
        return 42
    
    @gl.public.write 
    def test_web_response_methods(self) -> int:
        # Test HTTP response - should provide .status, .headers, .body
        response = gl.nondet.web.get("https://example.com").get()
        status_code = response.  # <-- Should show: status, headers, body
        
        # Test property inference
        status = response.status  # Should be int
        headers = response.headers  # Should be dict[str, bytes]
        body = response.body  # Should be bytes | None
        
        return status
    
    @gl.public.write
    def test_lazy_objects(self) -> str:
        # Test Lazy object - should provide .get() method
        lazy_result = gl.eq_principle.strict_eq(lambda: "test")
        value = lazy_result.  # <-- Should show: get()
        
        # Test chained calls
        final_result = lazy_result.get()  # Should resolve to actual type
        
        return final_result
    
    @gl.public.write
    def test_image_objects(self) -> int:
        # Test Image object from web rendering
        image = gl.nondet.web.render("https://example.com", mode="screenshot").get()
        raw_data = image.  # <-- Should show: raw, pil
        
        # Test property access
        image_bytes = image.raw  # Should be bytes
        pil_image = image.pil    # Should be PIL.Image.Image
        
        return len(image_bytes)
        
    @gl.public.view
    def test_method_chaining(self) -> str:
        # Test complex type inference chains
        addr = Address("0x123...")
        
        # This should work: addr.as_hex should return str
        hex_str = addr.as_hex
        
        # Method calls with return types
        upper_hex = hex_str.upper()  # Built-in str method (if we support it)
        
        return hex_str