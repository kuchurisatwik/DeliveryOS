import os
from typing import List, Dict, Set
from app.services.repository.db import RepositoryDB
from app.schemas.repository import RepositoryContext, RetrievedSymbol, RetrievedTest
from app.utils.logger import logger

class ContextRetrievalEngine:
    """Deterministically queries the SQLite index to fetch only relevant context based on changed files."""
    
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.db = RepositoryDB(workspace_path)
        
    def retrieve(self, changed_files: List[str]) -> RepositoryContext:
        logger.info(f"Retrieving context for {len(changed_files)} changed files...")
        
        target_symbols: List[RetrievedSymbol] = []
        dependencies: List[RetrievedSymbol] = []
        related_tests: List[RetrievedTest] = []
        
        target_symbol_names = set()
        
        with self.db.get_connection() as conn:
            # 1. Fetch Target Symbols (from changed files)
            for file_path in changed_files:
                if not file_path.endswith(".py"):
                    continue
                    
                cursor = conn.execute(
                    """
                    SELECT s.name, s.type, s.body, f.path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE f.path = ?
                    """, (file_path,)
                )
                
                for row in cursor.fetchall():
                    target_symbol_names.add(row["name"])
                    target_symbols.append(RetrievedSymbol(
                        name=row["name"],
                        type=row["type"],
                        file_path=row["path"],
                        body=row["body"]
                    ))
                    
            # 2. Fetch Dependencies (things imported by the target symbols)
            # For simplicity, we just fetch symbols whose names exist in the workspace
            # that were imported by the changed files.
            for symbol in target_symbols:
                cursor = conn.execute(
                    """
                    SELECT s2.name, s2.type, s2.body, f.path
                    FROM dependencies d
                    JOIN symbols s1 ON d.source_symbol_id = s1.id
                    JOIN symbols s2 ON d.target_symbol_name = s2.name
                    JOIN files f ON s2.file_id = f.id
                    WHERE s1.name = ? AND f.path != ?
                    LIMIT 15
                    """, (symbol.name, symbol.file_path)
                )
                
                for row in cursor.fetchall():
                    # Avoid duplicates
                    if row["name"] not in target_symbol_names:
                        dependencies.append(RetrievedSymbol(
                            name=row["name"],
                            type=row["type"],
                            file_path=row["path"],
                            body=row["body"]
                        ))
                        
            # 3. Fetch Related Tests
            for name in target_symbol_names:
                cursor = conn.execute(
                    """
                    SELECT f.path
                    FROM tests_mapping tm
                    JOIN files f ON tm.test_file_id = f.id
                    WHERE tm.target_symbol_name = ?
                    LIMIT 10
                    """, (name,)
                )
                
                for row in cursor.fetchall():
                    test_path = row["path"]
                    full_path = os.path.join(self.workspace_path, test_path)
                    if os.path.exists(full_path):
                        with open(full_path, "r", encoding="utf-8") as f:
                            body = f.read()
                        
                        # Avoid duplicates
                        if not any(t.file_path == test_path for t in related_tests):
                            related_tests.append(RetrievedTest(
                                file_path=test_path,
                                body=body
                            ))
                            
            # Always try to fetch conftest.py if it exists
            conftest_path = "conftest.py"
            full_conftest = os.path.join(self.workspace_path, conftest_path)
            if os.path.exists(full_conftest) and not any(t.file_path == conftest_path for t in related_tests):
                with open(full_conftest, "r", encoding="utf-8") as f:
                    related_tests.append(RetrievedTest(
                        file_path=conftest_path,
                        body=f.read()
                    ))
                    
        return RepositoryContext(
            target_symbols=target_symbols,
            dependencies=dependencies,
            related_tests=related_tests
        )
