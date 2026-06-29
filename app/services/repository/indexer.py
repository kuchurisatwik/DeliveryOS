import os
import ast
from typing import List, Set
from app.services.repository.db import RepositoryDB
from app.utils.logger import logger

class RepositoryIndexer:
    """Parses AST of Python files and stores structural metadata in SQLite."""
    
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
                
            # Parse AST
            tree = ast.parse(content, filename=rel_path)
            
            with self.db.get_connection() as conn:
                # Insert File
                cursor = conn.execute(
                    "INSERT INTO files (path, is_test) VALUES (?, ?)", 
                    (rel_path, is_test)
                )
                file_id = cursor.lastrowid
                
                # Extract Imports
                imported_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported_names.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            imported_names.add(alias.name)
                            
                # For test files, we just record dependencies mapping
                if is_test:
                    for name in imported_names:
                        conn.execute(
                            "INSERT INTO tests_mapping (test_file_id, target_symbol_name) VALUES (?, ?)",
                            (file_id, name)
                        )
                else:
                    # For production files, we extract classes and functions
                    for node in tree.body:
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"
                            symbol_name = node.name
                            
                            # Get exact source code for the symbol
                            start_line = max(0, node.lineno - 1)
                            end_line = getattr(node, 'end_lineno', start_line + 1)
                            symbol_body = "\n".join(content.split("\n")[start_line:end_line])
                            
                            cursor = conn.execute(
                                "INSERT INTO symbols (file_id, name, type, body) VALUES (?, ?, ?, ?)",
                                (file_id, symbol_name, symbol_type, symbol_body)
                            )
                            symbol_id = cursor.lastrowid
                            
                            # Insert dependencies
                            for name in imported_names:
                                conn.execute(
                                    "INSERT INTO dependencies (source_symbol_id, target_symbol_name, import_path) VALUES (?, ?, ?)",
                                    (symbol_id, name, "")
                                )
                                
        except SyntaxError:
            logger.warning(f"SyntaxError while parsing {rel_path}. Skipping.")
        except Exception as e:
            logger.error(f"Failed to index {rel_path}: {e}")
