import sqlite3
import os
from contextlib import contextmanager
from app.utils.logger import logger

class RepositoryDB:
    """Manages the SQLite database for repository intelligence."""
    
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.db_dir = os.path.join(workspace_path, ".deliveryos")
        self.db_path = os.path.join(self.db_dir, "repository.db")
        
        os.makedirs(self.db_dir, exist_ok=True)
        self._init_db()
        
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Creates the necessary schema if it does not exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            is_test BOOLEAN NOT NULL DEFAULT 0,
            -- Files that could not be parsed into an AST are recorded here
            -- instead of being silently skipped (Requirement 2.6).
            unparseable BOOLEAN NOT NULL DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            name TEXT NOT NULL,           -- simple name for top-level, dotted qualified name for nested/methods
            type TEXT NOT NULL,           -- 'class', 'function', or 'method'
            body TEXT NOT NULL,           -- source code
            -- Fully-qualified dotted name (e.g. 'MyClass.my_method'); enables call-graph resolution.
            qualified_name TEXT,
            -- id of the enclosing class/function symbol (NULL for top-level symbols).
            parent_symbol_id INTEGER,
            -- 1-based line where the symbol is defined.
            lineno INTEGER,
            FOREIGN KEY(file_id) REFERENCES files(id),
            FOREIGN KEY(parent_symbol_id) REFERENCES symbols(id),
            UNIQUE(file_id, name)
        );
        
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_symbol_id INTEGER,
            target_symbol_name TEXT NOT NULL,
            import_path TEXT,             -- resolved dotted import path where determinable
            FOREIGN KEY(source_symbol_id) REFERENCES symbols(id)
        );
        
        -- Call graph: one row per function-call edge (caller -> callee).
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            caller_symbol_id INTEGER,     -- enclosing symbol; NULL for module-level calls
            callee_name TEXT NOT NULL,    -- called name as written (dotted for attribute calls)
            lineno INTEGER,
            FOREIGN KEY(file_id) REFERENCES files(id),
            FOREIGN KEY(caller_symbol_id) REFERENCES symbols(id)
        );
        
        CREATE TABLE IF NOT EXISTS tests_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_file_id INTEGER NOT NULL,
            target_symbol_name TEXT NOT NULL,
            FOREIGN KEY(test_file_id) REFERENCES files(id)
        );
        """
        with self.get_connection() as conn:
            conn.executescript(schema)
            self._migrate_schema(conn)

    def _migrate_schema(self, conn):
        """Adds newly-introduced columns to pre-existing databases without dropping data."""
        # files.unparseable
        existing_file_cols = {row["name"] for row in conn.execute("PRAGMA table_info(files)")}
        if "unparseable" not in existing_file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN unparseable BOOLEAN NOT NULL DEFAULT 0")

        # symbols.qualified_name / parent_symbol_id / lineno
        existing_symbol_cols = {row["name"] for row in conn.execute("PRAGMA table_info(symbols)")}
        if "qualified_name" not in existing_symbol_cols:
            conn.execute("ALTER TABLE symbols ADD COLUMN qualified_name TEXT")
        if "parent_symbol_id" not in existing_symbol_cols:
            conn.execute("ALTER TABLE symbols ADD COLUMN parent_symbol_id INTEGER")
        if "lineno" not in existing_symbol_cols:
            conn.execute("ALTER TABLE symbols ADD COLUMN lineno INTEGER")
            
    def clear(self):
        """Clears all data for a fresh indexing run."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tests_mapping")
            conn.execute("DELETE FROM calls")
            conn.execute("DELETE FROM dependencies")
            conn.execute("DELETE FROM symbols")
            conn.execute("DELETE FROM files")
