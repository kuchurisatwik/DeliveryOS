import os
import ast
from typing import List, Optional, Tuple
from app.services.repository.db import RepositoryDB
from app.utils.logger import logger

class RepositoryIndexer:
    """Parses AST of Python files and stores structural metadata in SQLite.

    Beyond a flat symbol list, the indexer now builds two traversable graphs:
      * a call graph (caller symbol -> callee name edges) in the ``calls`` table
      * a dependency graph (imports with resolved ``import_path``) in ``dependencies``
    Nested functions and class methods are captured (not just top-level symbols),
    and files that cannot be parsed into an AST are recorded as ``unparseable``
    rather than silently skipped.
    """
    
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.db = RepositoryDB(workspace_path)
        
    def index_repository(self):
        """Indexes the entire repository from scratch."""
        logger.info("Starting Repository Indexer (SQLite & AST)...")
        self.db.clear()
        
        for root, dirs, files in os.walk(self.workspace_path):
            if ".git" in root or "venv" in root or "__pycache__" in root or ".deliveryos" in root:
                continue
                
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.workspace_path).replace("\\", "/")
                    self._index_file(full_path, rel_path)
                    
        logger.info("Repository Indexing complete.")
                    
    def _index_file(self, full_path: str, rel_path: str):
        is_test = rel_path.startswith("tests/") or rel_path.startswith("test/") or "conftest.py" in rel_path
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {rel_path}: {e}")
            return

        # Attempt to parse. A parse failure must NOT abort indexing of the rest of
        # the repository: record the file as unparseable and continue (Requirement 2.6).
        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            logger.warning(f"SyntaxError while parsing {rel_path}. Recording as unparseable.")
            try:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO files (path, is_test, unparseable) VALUES (?, ?, 1)",
                        (rel_path, is_test),
                    )
            except Exception as e:
                logger.error(f"Failed to record unparseable file {rel_path}: {e}")
            return
        except Exception as e:
            logger.error(f"Failed to index {rel_path}: {e}")
            return

        try:
            content_lines = content.split("\n")
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO files (path, is_test, unparseable) VALUES (?, ?, 0)",
                    (rel_path, is_test),
                )
                file_id = cursor.lastrowid

                # Resolve imports into (target_symbol_name, import_path) pairs.
                import_entries = self._extract_imports(tree)

                if is_test:
                    # For test files we only record the dependency mapping.
                    for target_name, _import_path in import_entries:
                        conn.execute(
                            "INSERT INTO tests_mapping (test_file_id, target_symbol_name) VALUES (?, ?)",
                            (file_id, target_name),
                        )
                else:
                    # Recursively index classes, functions, methods and nested defs,
                    # and record caller -> callee edges for the call graph.
                    top_level_symbol_ids: List[int] = []
                    self._index_scope(
                        conn,
                        file_id,
                        content_lines,
                        tree.body,
                        prefix="",
                        parent_symbol_id=None,
                        parent_is_class=False,
                        top_level_symbol_ids=top_level_symbol_ids,
                    )

                    # Record module-level calls (calls not enclosed by any symbol).
                    for callee_name, lineno in self._collect_scope_calls(tree):
                        conn.execute(
                            "INSERT INTO calls (file_id, caller_symbol_id, callee_name, lineno) VALUES (?, ?, ?, ?)",
                            (file_id, None, callee_name, lineno),
                        )

                    # Preserve existing behaviour: attach module imports to each
                    # top-level symbol as dependency-graph edges, now with a resolved
                    # import_path where determinable.
                    for symbol_id in top_level_symbol_ids:
                        for target_name, import_path in import_entries:
                            conn.execute(
                                "INSERT INTO dependencies (source_symbol_id, target_symbol_name, import_path) VALUES (?, ?, ?)",
                                (symbol_id, target_name, import_path),
                            )
        except Exception as e:
            logger.error(f"Failed to index {rel_path}: {e}")

    def _index_scope(
        self,
        conn,
        file_id: int,
        content_lines: List[str],
        body_nodes,
        prefix: str,
        parent_symbol_id: Optional[int],
        parent_is_class: bool,
        top_level_symbol_ids: List[int],
    ):
        """Recursively indexes a scope's direct child definitions.

        Captures classes, functions, methods and nested defs (each with a dotted
        qualified name) and records the function-call edges lexically contained in
        each function/method body.
        """
        for node in body_nodes:
            if isinstance(node, ast.ClassDef):
                qualified_name = f"{prefix}.{node.name}" if prefix else node.name
                symbol_id = self._insert_symbol(
                    conn, file_id, node, "class", qualified_name, parent_symbol_id, content_lines
                )
                if prefix == "":
                    top_level_symbol_ids.append(symbol_id)
                # Recurse into the class body (methods / nested classes).
                self._index_scope(
                    conn, file_id, content_lines, node.body,
                    prefix=qualified_name,
                    parent_symbol_id=symbol_id,
                    parent_is_class=True,
                    top_level_symbol_ids=top_level_symbol_ids,
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = f"{prefix}.{node.name}" if prefix else node.name
                symbol_type = "method" if parent_is_class else "function"
                symbol_id = self._insert_symbol(
                    conn, file_id, node, symbol_type, qualified_name, parent_symbol_id, content_lines
                )
                if prefix == "":
                    top_level_symbol_ids.append(symbol_id)

                # Record call edges for calls directly within this function body.
                for callee_name, lineno in self._collect_scope_calls(node):
                    conn.execute(
                        "INSERT INTO calls (file_id, caller_symbol_id, callee_name, lineno) VALUES (?, ?, ?, ?)",
                        (file_id, symbol_id, callee_name, lineno),
                    )

                # Recurse into nested defs / classes declared inside this function.
                self._index_scope(
                    conn, file_id, content_lines, node.body,
                    prefix=qualified_name,
                    parent_symbol_id=symbol_id,
                    parent_is_class=False,
                    top_level_symbol_ids=top_level_symbol_ids,
                )

    def _insert_symbol(
        self,
        conn,
        file_id: int,
        node,
        symbol_type: str,
        qualified_name: str,
        parent_symbol_id: Optional[int],
        content_lines: List[str],
    ) -> Optional[int]:
        """Inserts a symbol row.

        Top-level symbols keep their simple ``name`` (backward compatibility with
        existing retriever queries); nested/method symbols use the dotted qualified
        name so the ``UNIQUE(file_id, name)`` constraint is not violated.
        """
        name = node.name if parent_symbol_id is None else qualified_name
        start_line = max(0, node.lineno - 1)
        end_line = getattr(node, "end_lineno", start_line + 1)
        symbol_body = "\n".join(content_lines[start_line:end_line])

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO symbols
                (file_id, name, type, body, qualified_name, parent_symbol_id, lineno)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, name, symbol_type, symbol_body, qualified_name, parent_symbol_id, node.lineno),
        )
        return cursor.lastrowid

    def _collect_scope_calls(self, scope_node) -> List[Tuple[str, Optional[int]]]:
        """Collects function-call edges lexically within ``scope_node``.

        Descends through the scope's statements but stops at nested function/class
        definitions, since those own their own call edges as separate symbols.
        """
        calls: List[Tuple[str, Optional[int]]] = []

        def visit(n):
            for child in ast.iter_child_nodes(n):
                # Do not descend into nested scopes; they are indexed separately.
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(child, ast.Call):
                    callee_name = self._callee_name(child.func)
                    if callee_name:
                        calls.append((callee_name, getattr(child, "lineno", None)))
                visit(child)

        visit(scope_node)
        return calls

    def _callee_name(self, func_node) -> Optional[str]:
        """Resolves the written name of a call target.

        Handles simple names (``foo()``) and attribute chains (``a.b.c()``),
        returning a dotted string. Returns None for calls that are not resolvable
        to a name (e.g. calls on subscripts or call results).
        """
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            parts = [func_node.attr]
            current = func_node.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _extract_imports(self, tree) -> List[Tuple[str, str]]:
        """Extracts imports as (target_symbol_name, resolved_import_path) pairs.

        ``target_symbol_name`` keeps the same value emitted previously (the imported
        name) so existing retriever joins keep working, while ``import_path`` now
        carries the resolved dotted module path.
        """
        entries: List[Tuple[str, str]] = []
        seen = set()

        def add(target_name: str, import_path: str):
            key = (target_name, import_path)
            if key not in seen:
                seen.add(key)
                entries.append((target_name, import_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add(alias.name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = ("." * node.level) + (node.module or "")
                for alias in node.names:
                    import_path = f"{module}.{alias.name}" if module else alias.name
                    add(alias.name, import_path)
        return entries
