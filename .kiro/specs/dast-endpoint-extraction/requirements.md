# Requirements Document

## Introduction

The DAST pipeline's scanners are only as good as the list of endpoints they are
handed. ZAP only attacks URLs already on its site tree, and Schemathesis only
generates requests for operations declared in an OpenAPI schema. Today both are
seeded from a single source: the OpenAPI spec fetched from the running target at
preflight (`dast/preflight.py` `_fetch_spec_paths`). When a target exposes no spec —
or exposes an incomplete one — that source returns nothing, the scanners get an
empty map, and the whole run reports a false all-clear. A Go `net/http` service, a
Ruby Sinatra app, or an Express API that never publishes `/openapi.json` is exactly
the case that slips through.

Endpoint extraction closes that gap by reading the endpoints out of the *source code*
of the target repository instead of relying on the running application to describe
itself. It walks the checked-out repository, recognises route declarations across
several languages and frameworks, and produces a normalised, deduplicated inventory
of endpoints — each carrying an HTTP method, a templatised path, and its parameters.
That inventory is then reconciled with any runtime OpenAPI spec, used to populate
`DastScope.spec_paths` so URLs templatise into stable finding identities, and
synthesised into a minimal OpenAPI document that Schemathesis can consume when the
target publishes none.

This feature MUST fit the existing architecture rather than reinvent it. It reuses the
`DastScope`, the `spec_paths` contract already consumed by the ZAP and Schemathesis
adapters, the `dast.urls` normalisation (`normalize_path` / `endpoint_identity` and the
shared `{id}` placeholder), and the `DAST_`-prefixed configuration convention. It feeds
the same Phase 2 liveness/trust model that keeps "zero findings" honest: an empty
inventory is surfaced as an unavailable seed source, never silently accepted as a
scanned-and-clean application. Extraction is static only — it reads files, and never
executes code from the target repository.

## Glossary

- **DAST_Service**: The standalone service that queues and runs dynamic scans against a
  running target. The system under specification.
- **Endpoint_Extractor**: The new component that reads a Target_Repository's source
  code and produces an Endpoint_Inventory. The primary subject of these requirements.
- **Target_Repository**: The source tree, checked out at the commit under scan, from
  which endpoints are extracted. Identified by a filesystem root path.
- **Source_File**: A single file within the Target_Repository that the
  Endpoint_Extractor may read.
- **Language_Extractor**: A registered unit that recognises Route_Declarations for one
  language or web framework (for example Python Flask/FastAPI, JavaScript/TypeScript
  Express, Go `net/http`, or Ruby Sinatra/Rails).
- **Route_Declaration**: A source-code construct that registers an HTTP endpoint, such
  as `app.get("/users/:id", ...)`, `@app.route("/users/<id>")`, or
  `http.HandleFunc("/user", ...)`.
- **Extracted_Endpoint**: One normalised endpoint carrying an HTTP_Method, a
  Path_Template, a set of Endpoint_Parameters, and the Source_File location it was
  read from.
- **HTTP_Method**: The uppercase HTTP verb of an Extracted_Endpoint (for example `GET`,
  `POST`, `PUT`, `DELETE`, `PATCH`).
- **Path_Template**: A normalised endpoint path whose dynamic segments are replaced by
  the shared `{id}` placeholder defined in `dast.urls` (for example `/users/{id}`).
- **Endpoint_Parameter**: A named path or query parameter of an Extracted_Endpoint.
- **Endpoint_Identity**: The pair `(HTTP_Method, Path_Template)` that uniquely
  identifies an Extracted_Endpoint for deduplication, consistent with
  `dast.urls.endpoint_identity`.
- **Endpoint_Inventory**: The deduplicated collection of Extracted_Endpoints produced by
  one extraction run over one Target_Repository.
- **OpenAPI_Spec**: The target's runtime OpenAPI specification, whose path templates are
  fetched at preflight and carried on `DastScope.spec_paths`.
- **Synthesized_Schema**: A minimal, valid OpenAPI document emitted from an
  Endpoint_Inventory so Schemathesis can be driven when the target publishes no
  OpenAPI_Spec.
- **Spec_Paths**: The `DastScope.spec_paths` tuple of path templates consumed by the ZAP
  and Schemathesis adapters to seed their scan surface and templatise URLs.
- **Exclusion_Pattern**: A glob pattern naming directories or files the
  Endpoint_Extractor never reads (for example `node_modules`, `vendor`, `.git`).
- **Extraction_Activity**: The evidence record of one extraction run, carrying the count
  of Source_Files scanned, the count of Extracted_Endpoints found, and the set of
  languages detected.

## Requirements

### Requirement 1: Endpoint extractor component

**User Story:** As a DAST operator, I want a component that reads endpoints out of a
repository's source, so that scanners can be seeded even when the running target
publishes no OpenAPI spec.

#### Acceptance Criteria

1. WHEN the Endpoint_Extractor operation is invoked with a Target_Repository root path,
   THE Endpoint_Extractor SHALL return exactly one Endpoint_Inventory.
2. THE Endpoint_Extractor SHALL perform no network I/O.
3. THE Endpoint_Extractor SHALL read only Source_Files whose resolved absolute path lies
   within the Target_Repository root path.
4. IF a Source_File's resolved absolute path (after resolving symbolic links and relative
   path segments) lies outside the Target_Repository root path, THEN THE Endpoint_Extractor
   SHALL skip that Source_File, SHALL exclude it from the Endpoint_Inventory, and SHALL
   continue processing the remaining Source_Files without raising an error.
5. THE Endpoint_Extractor SHALL NOT execute code contained in any Source_File of the
   Target_Repository.
6. THE Endpoint_Extractor SHALL NOT import code contained in any Source_File of the
   Target_Repository.
7. THE Endpoint_Extractor SHALL NOT evaluate code contained in any Source_File of the
   Target_Repository.
8. THE Endpoint_Extractor SHALL NOT invoke code contained in any Source_File of the
   Target_Repository.
9. WHEN the Endpoint_Extractor is invoked twice over an unchanged Target_Repository with
   unchanged configuration, THE Endpoint_Extractor SHALL return two Endpoint_Inventories
   that contain an identical set of Extracted_Endpoints, where an identical set means the
   two Endpoint_Inventories contain the same collection of Endpoint_Identities and, for
   each shared Endpoint_Identity, the same HTTP_Method, the same Path_Template, and the
   same set of Endpoint_Parameters.
10. THE DAST_Service SHALL read every Endpoint_Extractor configuration value from a
    setting whose name begins with the `DAST_` prefix.
11. THE DAST_Service SHALL NOT read any Endpoint_Extractor configuration value from a
    setting whose name begins with the `SECURITY_` prefix.

### Requirement 2: Multi-language route discovery

**User Story:** As a DAST operator, I want endpoints discovered across the languages our
services are written in, so that a target in any supported stack gets a seeded scan
surface.

#### Acceptance Criteria

1. THE Endpoint_Extractor SHALL discover Route_Declarations through a set of registered
   Language_Extractors in which each registered Language_Extractor recognises
   Route_Declarations for exactly one language or web framework.
2. WHEN the Endpoint_Extractor processes a Source_File whose language matches exactly one
   registered Language_Extractor, THE Endpoint_Extractor SHALL apply that
   Language_Extractor to the Source_File to discover its Route_Declarations.
3. IF the Endpoint_Extractor processes a Source_File whose language matches no registered
   Language_Extractor, THEN THE Endpoint_Extractor SHALL skip that Source_File without
   recording an extraction error.
4. WHEN the Endpoint_Extractor processes a Source_File whose language matches more than
   one registered Language_Extractor, THE Endpoint_Extractor SHALL apply every matching
   Language_Extractor to the Source_File and combine their discovered Route_Declarations
   into that Source_File's set of Route_Declarations.
5. THE Endpoint_Extractor SHALL support registering an additional Language_Extractor
   without modifying any existing registered Language_Extractor.

### Requirement 3: Extract method, path, and parameters

**User Story:** As a DAST operator, I want each discovered route captured with its
method, path, and parameters, so that the scanners receive the full attack surface
rather than a bare path list.

#### Acceptance Criteria

1. WHEN a Language_Extractor discovers a Route_Declaration, THE Endpoint_Extractor SHALL
   record one Extracted_Endpoint carrying the Route_Declaration's HTTP_Method,
   Path_Template, Endpoint_Parameters, and originating Source_File location, where the
   Source_File location comprises the Source_File's Target_Repository-relative path and
   the 1-based line number at which the Route_Declaration begins.
2. WHEN a Route_Declaration registers more than one HTTP_Method for a single path, THE
   Endpoint_Extractor SHALL record one Extracted_Endpoint per HTTP_Method.
3. WHERE a Route_Declaration specifies no explicit HTTP_Method, THE Endpoint_Extractor
   SHALL record the Extracted_Endpoint with the HTTP_Method `GET`.
4. WHEN a Route_Declaration's path contains dynamic segments, THE Endpoint_Extractor
   SHALL record each dynamic segment as a path-kind Endpoint_Parameter of the
   Extracted_Endpoint whose name equals the segment name declared in the
   Route_Declaration.
5. IF a Route_Declaration registers an HTTP_Method outside the supported set
   {GET, POST, PUT, PATCH, DELETE}, THEN THE Endpoint_Extractor SHALL skip that
   HTTP_Method without recording an Extracted_Endpoint for it, SHALL not raise an error,
   and SHALL continue recording Extracted_Endpoints for the remaining supported
   HTTP_Methods of that Route_Declaration.

### Requirement 4: Normalise path templates to the shared placeholder

**User Story:** As a DAST operator, I want extracted paths normalised the same way the
scanners normalise live URLs, so that extracted endpoints and scanner findings share one
stable identity.

#### Acceptance Criteria

1. WHEN the Endpoint_Extractor records a Path_Template, THE Endpoint_Extractor SHALL
   replace each dynamic path segment with the shared `{id}` placeholder defined in
   `dast.urls` and preserve every non-dynamic path segment unchanged.
2. THE Endpoint_Extractor SHALL convert framework-specific dynamic-segment syntaxes —
   including the `:name` colon form, the `<name>` and `<type:name>` angle-bracket forms,
   the `{name}` brace form, and a `*` wildcard segment — into the shared `{id}`
   placeholder.
3. THE Endpoint_Extractor SHALL produce each Path_Template with exactly one leading `/`
   and without a scheme or host component.
4. WHEN the Endpoint_Extractor records a Path_Template, THE Endpoint_Extractor SHALL
   collapse each run of two or more consecutive `/` separators into a single `/`.
5. WHEN the Endpoint_Extractor records a Path_Template other than the root path `/`, THE
   Endpoint_Extractor SHALL remove any trailing `/`.
6. WHEN a Path_Template produced by the Endpoint_Extractor is passed to
   `dast.urls.endpoint_identity` with no additional Spec_Paths supplied, THE resulting
   endpoint identity SHALL equal that Path_Template unchanged.

### Requirement 5: Deduplicate endpoints deterministically

**User Story:** As a DAST operator, I want duplicate route declarations collapsed to one
endpoint, so that a route registered in several files does not inflate the inventory.

#### Acceptance Criteria

1. WHEN two or more Extracted_Endpoints share the same Endpoint_Identity, THE
   Endpoint_Extractor SHALL retain exactly one Extracted_Endpoint for that
   Endpoint_Identity in the Endpoint_Inventory, selecting the retained Extracted_Endpoint
   deterministically as the one whose Source_File location is ordered first by ascending
   Target_Repository-relative Source_File path and then by ascending line position within
   that Source_File.
2. WHEN merging two or more Extracted_Endpoints that share an Endpoint_Identity, THE
   Endpoint_Extractor SHALL retain on the single retained Extracted_Endpoint the union,
   keyed by Endpoint_Parameter name, of those Extracted_Endpoints' Endpoint_Parameters,
   such that each distinct Endpoint_Parameter name appears exactly once.
3. WHEN the Endpoint_Extractor processes the same set of Source_Files in two different
   traversal orders, THE Endpoint_Extractor SHALL produce two Endpoint_Inventories
   containing an identical set of Extracted_Endpoints, where each retained
   Extracted_Endpoint carries the identical Endpoint_Identity, retained Source_File
   location, and set of Endpoint_Parameters in both Endpoint_Inventories.

### Requirement 6: Reconcile with the runtime OpenAPI spec

**User Story:** As a DAST operator, I want extracted endpoints combined with any runtime
OpenAPI spec, so that the scan surface is the most complete view available from both
sources.

#### Acceptance Criteria

1. WHERE both a non-empty OpenAPI_Spec and a non-empty Endpoint_Inventory are present,
   THE DAST_Service SHALL produce a reconciled set of Path_Templates that is the union
   of the OpenAPI_Spec path templates and the Endpoint_Inventory Path_Templates, with
   each distinct Path_Template included exactly once.
2. IF a Path_Template from the Endpoint_Inventory denotes the same Endpoint_Identity as
   a template declared in the OpenAPI_Spec, THEN THE DAST_Service SHALL include exactly
   one Path_Template for that Endpoint_Identity in the reconciled set and SHALL retain
   the OpenAPI_Spec template.
3. WHERE the OpenAPI_Spec is empty and the Endpoint_Inventory is non-empty, THE
   DAST_Service SHALL produce the reconciled set from the Endpoint_Inventory
   Path_Templates alone.
4. WHERE the Endpoint_Inventory is empty and the OpenAPI_Spec is non-empty, THE
   DAST_Service SHALL produce the reconciled set from the OpenAPI_Spec path templates
   alone.
5. WHERE both the OpenAPI_Spec and the Endpoint_Inventory are empty, THE DAST_Service
   SHALL produce an empty reconciled set of Path_Templates.

### Requirement 7: Seed the scanners through DastScope.spec_paths

**User Story:** As a DAST operator, I want the reconciled endpoints placed on
`DastScope.spec_paths`, so that the existing ZAP and Schemathesis adapters seed their
scan surface with no changes to those adapters.

#### Acceptance Criteria

1. WHEN a scan scope is assembled, THE DAST_Service SHALL populate
   `DastScope.spec_paths` with exactly the reconciled set of Path_Templates, such that
   every Path_Template in the reconciled set is present, no Path_Template absent from the
   reconciled set is present, and each Path_Template appears exactly once.
2. THE DAST_Service SHALL populate `DastScope.spec_paths` such that it contains every
   path template the OpenAPI_Spec alone would have provided.
3. THE DAST_Service SHALL place each Path_Template on `DastScope.spec_paths` in the
   normalised `dast.urls` form the OpenAPI_Spec path templates already use: beginning
   with a single leading `/`, and carrying no scheme or host component.
4. IF the reconciled set of Path_Templates is empty, THEN THE DAST_Service SHALL populate
   `DastScope.spec_paths` as an empty collection and SHALL NOT add any placeholder or
   synthesised Path_Template.

### Requirement 8: Synthesise an OpenAPI schema for Schemathesis

**User Story:** As a DAST operator, I want a minimal OpenAPI document generated from the
extracted endpoints, so that Schemathesis can run against a target that publishes no
spec of its own.

#### Acceptance Criteria

1. WHEN the Endpoint_Extractor synthesises a Synthesized_Schema from an
   Endpoint_Inventory, THE Endpoint_Extractor SHALL emit a document in which each
   Extracted_Endpoint is represented by exactly one operation whose path equals that
   Extracted_Endpoint's Path_Template and whose verb equals that Extracted_Endpoint's
   HTTP_Method.
2. WHEN the Endpoint_Extractor emits a Synthesized_Schema, THE Endpoint_Extractor SHALL
   produce a document that Schemathesis loads without raising a schema-validation error.
3. FOR ALL Endpoint_Inventories, synthesising a Synthesized_Schema and then parsing that
   Synthesized_Schema SHALL yield an Endpoint_Inventory whose set of Endpoint_Identities
   equals the original Endpoint_Inventory's set of Endpoint_Identities (round-trip
   property).
4. WHEN the Endpoint_Inventory is empty, THE Endpoint_Extractor SHALL emit a
   Synthesized_Schema that declares zero operations while remaining a structurally valid
   OpenAPI document.
5. WHERE an Extracted_Endpoint's Path_Template contains the shared `{id}` placeholder,
   THE Endpoint_Extractor SHALL declare `{id}` as a required path parameter of the
   corresponding operation in the Synthesized_Schema.
6. WHEN the Endpoint_Extractor synthesises a Synthesized_Schema from the same
   Endpoint_Inventory over two separate invocations, THE Endpoint_Extractor SHALL emit
   byte-identical Synthesized_Schema documents.

### Requirement 9: Bounded and safe traversal

**User Story:** As a DAST operator, I want traversal confined to relevant source files,
so that extraction stays fast and never wanders into dependency or version-control
directories.

#### Acceptance Criteria

1. THE DAST_Service SHALL read the set of Exclusion_Patterns from a `DAST_`-prefixed
   configuration setting.
2. IF the `DAST_`-prefixed Exclusion_Patterns configuration setting is absent or empty,
   THEN THE DAST_Service SHALL apply a default set of Exclusion_Patterns that matches
   dependency directories and version-control directories.
3. WHILE traversing the Target_Repository, THE Endpoint_Extractor SHALL skip every
   directory and Source_File whose Target_Repository-relative path matches a configured
   Exclusion_Pattern.
4. WHEN the Endpoint_Extractor skips a directory whose Target_Repository-relative path
   matches an Exclusion_Pattern, THE Endpoint_Extractor SHALL skip that directory's
   entire descendant subtree without traversing any file or subdirectory within it.
5. THE DAST_Service SHALL read a maximum Source_File size, expressed in bytes, from a
   `DAST_`-prefixed configuration setting.
6. IF the `DAST_`-prefixed maximum Source_File size configuration setting is absent or
   empty, THEN THE DAST_Service SHALL apply a finite, positive default maximum
   Source_File size expressed in bytes.
7. WHEN a Source_File's size in bytes is strictly greater than the configured maximum
   Source_File size, THE Endpoint_Extractor SHALL skip that Source_File without reading
   its contents into the extraction.

### Requirement 10: Graceful degradation on malformed input

**User Story:** As a DAST operator, I want an unreadable file or a bad repository path to
degrade cleanly, so that one broken file never discards the endpoints extracted from the
rest of the repository.

#### Acceptance Criteria

1. IF a Source_File cannot be read or cannot be parsed by its Language_Extractor, THEN
   THE Endpoint_Extractor SHALL skip that Source_File, SHALL continue processing the
   remaining Source_Files, and SHALL return an Endpoint_Inventory containing every
   Extracted_Endpoint discovered from those remaining Source_Files.
2. IF the Target_Repository root path does not exist OR the Target_Repository root path
   is not a directory, THEN THE Endpoint_Extractor SHALL raise an error identifying the
   offending Target_Repository root path and SHALL NOT return an Endpoint_Inventory.
3. WHEN the Target_Repository contains no discoverable Route_Declarations, THE
   Endpoint_Extractor SHALL return an Endpoint_Inventory containing zero
   Extracted_Endpoints without raising an error.
4. WHEN every Source_File matched by a Language_Extractor is skipped because it cannot
   be read or cannot be parsed, THE Endpoint_Extractor SHALL return an Endpoint_Inventory
   containing zero Extracted_Endpoints without raising an error.

### Requirement 11: Extraction evidence and trust integration

**User Story:** As a DAST operator, I want extraction to report what it actually found,
so that an empty inventory is treated as a missing seed source rather than a clean
application.

#### Acceptance Criteria

1. WHEN an extraction run completes, including a run degraded by skipped Source_Files,
   THE Endpoint_Extractor SHALL populate an Extraction_Activity record with the count of
   Source_Files read by a Language_Extractor during the run, the count of
   Extracted_Endpoints in the resulting Endpoint_Inventory, and the set of languages
   whose registered Language_Extractor was applied to at least one Source_File.
2. IF the Endpoint_Inventory is empty AND the OpenAPI_Spec is empty, THEN THE
   DAST_Service SHALL mark the scan surface with a status that is distinct from
   scanned-and-clean and that identifies the scan surface as unseeded.
3. IF the Endpoint_Inventory is empty AND the OpenAPI_Spec is empty, THEN THE
   DAST_Service SHALL NOT report the resulting scan as clean.
4. WHEN the reconciled set of Path_Templates is non-empty, THE DAST_Service SHALL record,
   in the scan's preflight record, the count of distinct Path_Templates placed on
   `DastScope.spec_paths` to seed the scan.
5. WHEN the reconciled set of Path_Templates is empty, THE DAST_Service SHALL record a
   seed count of zero together with an unseeded indication in the scan's preflight
   record.
