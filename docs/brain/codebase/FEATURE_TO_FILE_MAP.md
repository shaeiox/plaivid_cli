# Feature-to-file map

### Feature: Engine local lifecycle and authentication
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/bootstrap.py`, `pvm_control_engine/src/pvm_control_engine/composition.py`, `pvm_control_engine/src/pvm_control_engine/auth/`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/user/`, `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/registry.py`
- **Shared dependencies:** Python standard library, local configured sbell
- **Data models:** `pvm_control_engine/src/pvm_control_engine/domain/models/session.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`
- **Related contracts:** `pvm_control_engine/docs/ARCHITECTURE.md`
- **Potential impact areas:** UI connect/logout states; Engine session cache; socket serving and cleanup lifecycle
- **Files that should NOT be modified:** `UI/tui/src/plaivid_ui/engine_client/client.py`
- **Documentation references:** `pvm_control_engine/README.md`

### Feature: JSON-RPC transport and allowlist
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/ipc/dispatcher.py`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/ipc/server.py`, `UI/tui/src/plaivid_ui/engine_client/client.py`
- **Shared dependencies:** AF_UNIX, JSON-RPC 2.0
- **Data models:** `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`, `UI/tests/unit/test_ipc_boundary.py`
- **Related contracts:** `UI/docs/IPC.md`, `docs/brain/contracts/API_CONTRACTS.md`
- **Potential impact areas:** both DTO codecs, socket permissions and request bounds
- **Files that should NOT be modified:** arbitrary dispatch or raw command interfaces (none permitted)
- **Documentation references:** `pvm_control_engine/docs/ARCHITECTURE.md`

### Feature: VM inventory and selected details
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/application/service.py`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/infrastructure/pvm/adapter/local.py`, `UI/tui/src/plaivid_ui/presentation/tui/pages/virtual_machines/`
- **Shared dependencies:** Engine RPC only
- **Data models:** `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`, `UI/tests/unit/test_ipc_boundary.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** stale/partial indicators and canonical UUID handling
- **Files that should NOT be modified:** UI-to-Engine internal imports
- **Documentation references:** `UI/docs/ARCHITECTURE.md`

### Feature: VM lifecycle operations
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/vm/`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/application/service.py`, `UI/tui/src/plaivid_ui/presentation/tui/pages/virtual_machines/operations.py`
- **Shared dependencies:** allowlisted VM action methods
- **Data models:** `pvm_control_engine/src/pvm_control_engine/domain/models/operations.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** action allowlist, uncertainty and bulk limits
- **Files that should NOT be modified:** arbitrary sbell/XML parameters from the UI
- **Documentation references:** `pvm_control_engine/docs/ARCHITECTURE.md`

### Feature: Desktop inventory and operations
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/desktop/`
- **Supporting modules:** `UI/tui/src/plaivid_ui/presentation/tui/pages/virtual_desktops/`
- **Shared dependencies:** `desktop.list`, `desktop.operate`
- **Data models:** `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** selection freshness, action results
- **Files that should NOT be modified:** local PVM behavior in UI
- **Documentation references:** `UI/docs/ARCHITECTURE.md`

### Feature: Host and local monitoring display
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/application/service.py`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/infrastructure/local/`, `UI/tui/src/plaivid_ui/presentation/tui/pages/overview/`
- **Shared dependencies:** fixed snapshot section set
- **Data models:** `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`, `UI/tests/unit/test_ipc_boundary.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** freshness, source and quality metadata
- **Files that should NOT be modified:** UI process collection
- **Documentation references:** `UI/docs/MONITORING_DASHBOARD.md`

### Feature: Audit display
- **Main implementation:** `pvm_control_engine/src/pvm_control_engine/infrastructure/local/audit.py`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/application/service.py`, `UI/tui/src/plaivid_ui/presentation/tui/audit.py`
- **Shared dependencies:** bounded `audit.recent` RPC
- **Data models:** `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** redaction, read-only database access
- **Files that should NOT be modified:** direct SQLite reads in UI
- **Documentation references:** `pvm_control_engine/docs/ARCHITECTURE.md`

### Feature: Terminal layout, theme and navigation
- **Main implementation:** `UI/tui/src/plaivid_ui/presentation/tui/app.py`
- **Supporting modules:** `UI/tui/src/plaivid_ui/presentation/theme.py`, `UI/tui/src/plaivid_ui/presentation/tui/`
- **Shared dependencies:** Textual and Rich
- **Data models:** UI-owned DTOs in `UI/tui/src/plaivid_ui/engine_client/dto.py`
- **Tests:** `UI/tests/unit/test_setup_script.py`, `UI/tests/unit/test_ipc_boundary.py`
- **Related contracts:** `UI/docs/ARCHITECTURE.md`
- **Potential impact areas:** keyboard behavior and color-safe display
- **Files that should NOT be modified:** Engine policy to change UI appearance
- **Documentation references:** `UI/README.md`

### Feature: UI package and command entry point
- **Main implementation:** `UI/pyproject.toml`
- **Supporting modules:** `UI/tui/src/plaivid_ui/engine_client/cli.py`, `UI/tui/src/plaivid_ui/bootstrap.py`
- **Shared dependencies:** independent `plaivid-ui` distribution
- **Data models:** none
- **Tests:** `UI/tests/unit/test_ipc_boundary.py`
- **Related contracts:** `UI/docs/IPC.md`
- **Potential impact areas:** console script mapping and package discovery
- **Files that should NOT be modified:** root-level third product metadata
- **Documentation references:** `UI/README.md`

### Feature: Engine package and serve entry point
- **Main implementation:** `pvm_control_engine/pyproject.toml`
- **Supporting modules:** `pvm_control_engine/src/pvm_control_engine/bootstrap.py`, `pvm_control_engine/src/pvm_control_engine/ipc/server.py`
- **Shared dependencies:** independent `pvm-control-engine` distribution
- **Data models:** Engine domain values under `pvm_control_engine/src/pvm_control_engine/domain/`
- **Tests:** `pvm_control_engine/tests/unit/test_pvm_control_engine.py`
- **Related contracts:** `pvm_control_engine/docs/ARCHITECTURE.md`
- **Potential impact areas:** Engine-only installation, Unix socket permissions
- **Files that should NOT be modified:** UI imports into Engine internals
- **Documentation references:** `pvm_control_engine/README.md`
