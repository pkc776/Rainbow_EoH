import ast
import hashlib

class DocstringRemover(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if ast.get_docstring(node) and len(node.body) > 1:
            node.body = node.body[1:]
        elif ast.get_docstring(node):
            node.body = [ast.Pass()]
        return node
    
    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        if ast.get_docstring(node) and len(node.body) > 1:
            node.body = node.body[1:]
        elif ast.get_docstring(node):
            node.body = [ast.Pass()]
        return node
    
    def visit_ClassDef(self, node):
        self.generic_visit(node)
        if ast.get_docstring(node) and len(node.body) > 1:
            node.body = node.body[1:]
        elif ast.get_docstring(node):
            node.body = [ast.Pass()]
        return node
    
    def visit_Module(self, node):
        self.generic_visit(node)
        if ast.get_docstring(node) and len(node.body) > 1:
            node.body = node.body[1:]
        return node

def get_ast_hash(code_str: str) -> str:
    try:
        parsed = ast.parse(code_str)
        cleaned = DocstringRemover().visit(parsed)
        ast.fix_missing_locations(cleaned)
        standardized_code = ast.unparse(cleaned)
        return hashlib.sha256(standardized_code.encode('utf-8')).hexdigest()
    except SyntaxError:
        # Fallback if invalid python code
        return hashlib.sha256(code_str.encode('utf-8')).hexdigest()

def has_random_call(code_str: str) -> bool:
    try:
        parsed = ast.parse(code_str)
        for node in ast.walk(parsed):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if any(kw in node.func.id for kw in ["random", "choice", "sample"]):
                        return True
                elif isinstance(node.func, ast.Attribute):
                    if any(kw in node.func.attr for kw in ["random", "choice", "sample"]):
                        return True
                    if isinstance(node.func.value, ast.Name):
                        if any(kw in node.func.value.id for kw in ["random", "choice", "sample"]):
                            return True
        return False
    except SyntaxError:
        return False
