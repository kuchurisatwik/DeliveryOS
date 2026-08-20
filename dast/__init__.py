"""DeliveryOS DAST — a standalone dynamic application security testing service.

This package is a **separate service** from the SAST pipeline in ``app/``. It has
its own FastAPI app (:mod:`dast.main`), its own scan queue, its own state
directory, and its own container image (``Dockerfile.dast``).

Why standalone: SAST needs a git commit, DAST needs a *deployed, running* app.
They start at different moments and run at very different speeds — a 45-minute
active web scan sitting in the SAST queue would block every code scan behind it.

What is deliberately **shared** (imported, not forked): the finding data model in
``app.security.models`` (:class:`~app.security.models.Finding`,
:class:`~app.security.models.Severity`, :class:`~app.security.models.Location`,
:class:`~app.security.models.ScannerCoverage`) and the subprocess/parse helpers in
``app.security.detection.adapters.base``. Same plates, different kitchen — a shared
finding schema keeps the door open to correlating the two pipelines later.
"""
