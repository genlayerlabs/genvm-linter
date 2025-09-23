# { "Depends": "py-genlayer:test" }
 
from genlayer import *
import sys
 
 
class VisualWeb(gl.Contract):
    banner: str
 
    def __init__(self):
        pass
 
    @gl.public.write
    def analyze_banner(self) -> u64:
        # 1) Render page and capture screenshot (use wait_after_loaded if needed)
        def run() -> str:
            img = gl.nondet.web.render(
                'https://test-server.genlayer.com/static/genvm/hello.html',
                mode='screenshot',
                # wait_after_loaded='1000ms',
            )
 
            # 2) Feed screenshot into prompt as image input
            return gl.nondet.exec_prompt(
                'Extract the main visible word. Answer with lowercase letters only.',
                images=[img],
            )
 
        # 3) Use strict_eq since we expect identical string output across validators
        self.banner = gl.eq_principle.strict_eq(run)
 
    @gl.public.view
    def read_banner(self) -> str:
        return self.banner