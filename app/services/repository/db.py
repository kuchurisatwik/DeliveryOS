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
            is_test BOOLEAN NOT NULL DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'class' or 'function'
            body TEXT NOT NULL, -- source code
            FOREIGN KEY(file_id) REFERENCES files(id),
            UNIQUE(file_id, name)
        );
        
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_symbol_id INTEGER,
            target_symbol_name TEXT NOT NULL,
            import_path TEXT,
            FOREIGN KEY(source_symbol_id) REFERENCES symbols(id)
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
            
    def clear(self):
        """Clears all data for a fresh indexing run."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tests_mapping")
            conn.execute("DELETE FROM dependencies")
            conn.execute("DELETE FROM symbols")
            conn.execute("DELETE FROM files")
