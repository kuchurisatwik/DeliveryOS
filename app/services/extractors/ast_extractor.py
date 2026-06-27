import os
import ast

from app.services.extractors.base import IntelligenceExtractor
from app.schemas.knowledge import (
    RepositoryKnowledge,
    ClassSignature,
    MethodSignature,
    RouteSignature,
    FixtureSignature
)

class AstPythonExtractor(IntelligenceExtractor):
    """
    Parses Python source code using AST to extract signatures, routes, fixtures, and imports.
    """
    
    def extract(self, workspace_path: str, knowledge: RepositoryKnowledge) -> None:
        current_files = set()
        
        for root, dirs, files in os.walk(workspace_path):
            if "venv" in root or ".venv" in root or "__pycache__" in root or ".git" in root or ".ai_cache" in root:
                continue
                
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, workspace_path).replace("\\", "/")
                    current_files.add(rel_path)
                    
                    try:
                        mtime = os.path.getmtime(filepath)
                        
                        # Differential Cache Check
                        if rel_path in knowledge.mtimes and knowledge.mtimes[rel_path] == mtime:
                            continue # File unchanged, skip parsing
                            
                        # File changed or is new, remove old references
                        self._clear_file_knowledge(rel_path, knowledge)
                        knowledge.mtimes[rel_path] = mtime
                        
                        with open(filepath, "r", encoding="utf-8") as f:
                            tree = ast.parse(f.read(), filename=filepath)
                            
                        self._parse_tree(tree, rel_path, knowledge)
                        
                    except SyntaxError:
                        pass # Ignore files with syntax errors during static extraction
                    except Exception:
                        pass
                        
        # Cleanup deleted files
        deleted_files = set(knowledge.mtimes.keys()) - current_files
        for rel_path in deleted_files:
            self._clear_file_knowledge(rel_path, knowledge)
            del knowledge.mtimes[rel_path]

    def _clear_file_knowledge(self, rel_path: str, knowledge: RepositoryKnowledge) -> None:
        """Removes all indexed knowledge for a specific file to allow fresh re-extraction."""
        knowledge.class_index.pop(rel_path, None)
        knowledge.method_index.pop(rel_path, None)
        knowledge.route_index.pop(rel_path, None)
        knowledge.fixture_index.pop(rel_path, None)
        knowledge.exception_index.pop(rel_path, None)
        knowledge.model_index.pop(rel_path, None)
        knowledge.imports_index.pop(rel_path, None)

    def _parse_tree(self, tree: ast.AST, rel_path: str, knowledge: RepositoryKnowledge) -> None:
        classes = []
        methods = []
        routes = []
        fixtures = []
        imports = []
        exceptions = []
        models = []

        for node in ast.iter_child_nodes(tree):
            # Extract Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

            # Extract Classes
            elif isinstance(node, ast.ClassDef):
                class_methods = []
                bases = []
                
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(base.attr)
                        
                for body_node in node.body:
                    if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sig = self._extract_method(body_node)
                        class_methods.append(method_sig)
                
                class_sig = ClassSignature(
                    name=node.name,
                    methods=class_methods,
                    bases=bases,
                    docstring=ast.get_docstring(node)
                )
                
                if "Exception" in bases or any("Error" in b for b in bases):
                    exceptions.append(class_sig)
                elif "BaseModel" in bases or "Model" in bases:
                    models.append(class_sig)
                else:
                    classes.append(class_sig)

            # Extract free Functions (and checking for routes/fixtures)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_sig = self._extract_method(node)
                is_route = False
                is_fixture = False
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        # E.g. @app.get("/path")
                        if decorator.func.attr in ("get", "post", "put", "delete", "patch"):
                            path = ""
                            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                path = decorator.args[0].value
                            routes.append(RouteSignature(
                                method=decorator.func.attr.upper(),
                                path=path,
                                handler=node.name
                            ))
                            is_route = True
                            
                        # E.g. @pytest.fixture(scope="session")
                        if decorator.func.attr == "fixture":
                            scope = "function"
                            for kw in decorator.keywords:
                                if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
                                    scope = kw.value.value
                            fixtures.append(FixtureSignature(name=node.name, scope=scope))
                            is_fixture = True
                            
                    elif isinstance(decorator, ast.Attribute):
                        # E.g. @pytest.fixture (no parens)
                        if decorator.attr == "fixture":
                            fixtures.append(FixtureSignature(name=node.name))
                            is_fixture = True

                if not is_route and not is_fixture:
                    methods.append(method_sig)

        if classes:
            knowledge.class_index[rel_path] = classes
        if methods:
            knowledge.method_index[rel_path] = methods
        if routes:
            knowledge.route_index[rel_path] = routes
        if fixtures:
            knowledge.fixture_index[rel_path] = fixtures
        if exceptions:
            knowledge.exception_index[rel_path] = exceptions
        if models:
            knowledge.model_index[rel_path] = models
        if imports:
            knowledge.imports_index[rel_path] = imports

    def _extract_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodSignature:
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        for arg in node.args.kwonlyargs:
            args.append(arg.arg)
            
        returns = None
        if node.returns:
            if isinstance(node.returns, ast.Name):
                returns = node.returns.id
            elif isinstance(node.returns, ast.Subscript):
                returns = "Generic" # simplify
                
        return MethodSignature(
            name=node.name,
            args=args,
            returns=returns,
            is_async=isinstance(node, ast.AsyncFunctionDef)
        )
