import os
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import deque
from app.services.repository.db import RepositoryDB
from app.schemas.repository import (
    RepositoryContext,
    RetrievedSymbol,
    RetrievedTest,
    RelatedSymbol,
    SymbolReachability,
    ChangedFeature,
)
from app.utils.logger import logger

class ContextRetrievalEngine:
    """Deterministically queries the SQLite index to fetch only relevant context based on changed files."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.db = RepositoryDB(workspace_path)

    def retrieve(self, changed_files: List[str], structured_diff: Optional[Dict[str, Any]] = None) -> RepositoryContext:
        """Retrieve targeted context for the changed files.

        Backward-compatible: existing callers pass only ``changed_files`` and continue
        to receive ``target_symbols`` / ``dependencies`` / ``related_tests``. The
        security pipeline additionally consumes ``related_symbols`` (callers/callees/
        imports resolved from the call & dependency graphs), per-symbol
        ``reachability`` inputs, and a ``changed_feature`` bundle. ``structured_diff``
        is optional and only refines which files/symbols form the Changed_Feature.
        """
        logger.info(f"Retrieving context for {len(changed_files)} changed files...")

        target_symbols: List[RetrievedSymbol] = []
        dependencies: List[RetrievedSymbol] = []
        related_tests: List[RetrievedTest] = []
        related_symbols: List[RelatedSymbol] = []
        reachability: List[SymbolReachability] = []

        target_symbol_names: Set[str] = set()
        # (symbol_id, name, qualified_name, type, file_path) for each target symbol
        target_symbol_rows: List[Dict[str, Any]] = []

        with self.db.get_connection() as conn:
            # 1. Fetch Target Symbols (from changed files)
            for file_path in changed_files:
                if not file_path.endswith(".py"):
                    continue

                cursor = conn.execute(
                    """
                    SELECT s.id, s.name, s.type, s.body, s.qualified_name, f.path
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
                    target_symbol_rows.append({
                        "id": row["id"],
                        "name": row["name"],
                        "qualified_name": row["qualified_name"],
                        "type": row["type"],
                        "file_path": row["path"],
                    })

            # 2. Fetch Dependencies (things imported by the target symbols) — name-based,
            # preserved for backward compatibility with the prompt assembler.
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

            # 4. Graph traversal: callers, callees, and imported modules (Requirement 2.4).
            related_symbols = self._resolve_related_symbols(conn, target_symbol_rows)

            # 5. Reachability inputs derived from the call graph (consumed by Layer 3).
            reachability = self._compute_reachability(conn, target_symbol_rows)

        # 6. Map changed files / diff into the Changed_Feature shape (Requirement 2.1, 2.5).
        changed_feature = self._build_changed_feature(
            changed_files, target_symbols, related_symbols, structured_diff
        )

        return RepositoryContext(
            target_symbols=target_symbols,
            dependencies=dependencies,
            related_tests=related_tests,
            related_symbols=related_symbols,
            reachability=reachability,
            changed_feature=changed_feature,
        )

    # ------------------------------------------------------------------ #
    # Graph traversal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _simple_name(dotted: Optional[str]) -> Optional[str]:
        """Return the final component of a (possibly dotted) callee name."""
        if not dotted:
            return None
        return dotted.split(".")[-1]

    def _resolve_related_symbols(
        self, conn, target_symbol_rows: List[Dict[str, Any]]
    ) -> List[RelatedSymbol]:
        """Traverse the call & dependency graphs to collect callers, callees, and
        imported modules for each target symbol."""
        related: List[RelatedSymbol] = []
        seen: Set[Tuple[str, Optional[str], str]] = set()

        def add(rel: RelatedSymbol):
            key = (rel.name, rel.file_path, rel.relation)
            if key not in seen:
                seen.add(key)
                related.append(rel)

        target_ids = {r["id"] for r in target_symbol_rows}

        for target in target_symbol_rows:
            simple = self._simple_name(target["name"]) or target["name"]

            # --- Callers: edges whose callee resolves to this symbol's name. ---
            caller_rows = conn.execute(
                """
                SELECT DISTINCT s.name, s.type, s.qualified_name, f.path
                FROM calls c
                JOIN symbols s ON c.caller_symbol_id = s.id
                JOIN files f ON c.file_id = f.id
                WHERE (c.callee_name = ? OR c.callee_name LIKE ?)
                  AND c.caller_symbol_id IS NOT NULL
                """,
                (simple, f"%.{simple}"),
            ).fetchall()
            for row in caller_rows:
                add(RelatedSymbol(
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    type=row["type"],
                    file_path=row["path"],
                    relation="caller",
                ))

            # --- Callees: edges originating from this symbol; resolve callee name
            # to a defined symbol where possible. ---
            callee_rows = conn.execute(
                "SELECT DISTINCT callee_name FROM calls WHERE caller_symbol_id = ?",
                (target["id"],),
            ).fetchall()
            for crow in callee_rows:
                callee_name = crow["callee_name"]
                callee_simple = self._simple_name(callee_name)
                resolved = conn.execute(
                    """
                    SELECT s.name, s.type, s.qualified_name, f.path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.name = ? OR s.qualified_name = ? OR s.name = ?
                    LIMIT 5
                    """,
                    (callee_name, callee_name, callee_simple),
                ).fetchall()
                if resolved:
                    for row in resolved:
                        add(RelatedSymbol(
                            name=row["name"],
                            qualified_name=row["qualified_name"],
                            type=row["type"],
                            file_path=row["path"],
                            relation="callee",
                        ))
                else:
                    # Unresolved (external/builtin) callee — still a related symbol.
                    add(RelatedSymbol(
                        name=callee_name,
                        qualified_name=None,
                        type="external",
                        file_path=None,
                        relation="callee",
                    ))

            # --- Imported modules from the dependency graph. ---
            import_rows = conn.execute(
                """
                SELECT DISTINCT d.target_symbol_name, d.import_path
                FROM dependencies d
                WHERE d.source_symbol_id = ?
                """,
                (target["id"],),
            ).fetchall()
            for row in import_rows:
                add(RelatedSymbol(
                    name=row["target_symbol_name"],
                    qualified_name=None,
                    type="import",
                    file_path=None,
                    relation="imported",
                    import_path=row["import_path"],
                ))

        return related

    def _compute_reachability(
        self, conn, target_symbol_rows: List[Dict[str, Any]]
    ) -> List[SymbolReachability]:
        """Compute per-target-symbol reachability inputs from the call graph.

        Builds the repo-wide symbol call graph once, determines which symbols are
        transitively reachable from entrypoints (symbols with no incoming call
        edges), and reports caller/callee counts plus reachability booleans for each
        changed symbol.
        """
        if not target_symbol_rows:
            return []

        # Load every symbol so callee names can be resolved to symbol ids.
        symbol_rows = conn.execute(
            "SELECT id, name, qualified_name FROM symbols"
        ).fetchall()

        name_to_ids: Dict[str, Set[int]] = {}
        for row in symbol_rows:
            for key in filter(None, (row["name"], row["qualified_name"], self._simple_name(row["qualified_name"]))):
                name_to_ids.setdefault(key, set()).add(row["id"])

        # Build caller -> {callee_ids} adjacency from the calls table.
        adjacency: Dict[int, Set[int]] = {}
        incoming: Dict[int, int] = {}
        all_symbol_ids = {row["id"] for row in symbol_rows}
        call_rows = conn.execute(
            "SELECT caller_symbol_id, callee_name FROM calls WHERE caller_symbol_id IS NOT NULL"
        ).fetchall()
        for row in call_rows:
            caller_id = row["caller_symbol_id"]
            callee_name = row["callee_name"]
            callee_ids = name_to_ids.get(callee_name) or name_to_ids.get(self._simple_name(callee_name), set())
            for callee_id in callee_ids:
                if callee_id == caller_id:
                    continue
                adjacency.setdefault(caller_id, set()).add(callee_id)
                incoming[callee_id] = incoming.get(callee_id, 0) + 1

        # Entrypoints/roots = symbols with no incoming call edges. BFS forward to
        # find everything reachable from an entrypoint (roots included).
        roots = [sid for sid in all_symbol_ids if incoming.get(sid, 0) == 0]
        reachable: Set[int] = set()
        queue = deque(roots)
        reachable.update(roots)
        while queue:
            node = queue.popleft()
            for nxt in adjacency.get(node, ()):  # forward edges
                if nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)

        results: List[SymbolReachability] = []
        for target in target_symbol_rows:
            simple = self._simple_name(target["name"]) or target["name"]
            caller_count = conn.execute(
                """
                SELECT COUNT(*) AS n FROM calls
                WHERE caller_symbol_id IS NOT NULL
                  AND (callee_name = ? OR callee_name LIKE ?)
                """,
                (simple, f"%.{simple}"),
            ).fetchone()["n"]
            callee_count = conn.execute(
                "SELECT COUNT(*) AS n FROM calls WHERE caller_symbol_id = ?",
                (target["id"],),
            ).fetchone()["n"]

            results.append(SymbolReachability(
                symbol_name=target["name"],
                qualified_name=target["qualified_name"],
                file_path=target["file_path"],
                caller_count=caller_count,
                callee_count=callee_count,
                has_callers=caller_count > 0,
                reachable_from_entrypoint=target["id"] in reachable,
            ))
        return results

    def _build_changed_feature(
        self,
        changed_files: List[str],
        target_symbols: List[RetrievedSymbol],
        related_symbols: List[RelatedSymbol],
        structured_diff: Optional[Dict[str, Any]],
    ) -> ChangedFeature:
        """Assemble the Changed_Feature from changed files + resolved symbols."""
        files: List[str] = list(changed_files)
        # Fold in any paths mentioned in the structured diff (added/modified).
        if structured_diff:
            for change_type in ("added", "modified"):
                for entry in structured_diff.get(change_type, []) or []:
                    path = entry.get("path") if isinstance(entry, dict) else None
                    if path and path not in files:
                        files.append(path)

        functions = [s for s in target_symbols if s.type in ("function", "method")]
        classes = [s for s in target_symbols if s.type == "class"]

        return ChangedFeature(
            files=files,
            functions=functions,
            classes=classes,
            related_symbols=related_symbols,
        )
