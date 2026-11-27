# Build workflow

Build each package independently from its own project root. Build artifacts should be written to a temporary or ignored output directory, never committed.

```bash
python -m build --outdir /tmp/pvm-control-engine-dist pvm_control_engine
python -m build --outdir /tmp/plaivid-ui-dist UI
```

The Engine distribution is `pvm-control-engine`, import package `pvm_control_engine`, entry point `pvm-control-engine`. The UI distribution is `plaivid-ui`, import package `plaivid_ui`, entry point `plaivid`. There is no root Python build and no third runtime package.

Install/test each wheel in an isolated environment for release validation. UI requires its own Textual dependency and the local Engine socket at runtime; it does not install Engine as a library dependency. The Engine install does not include UI source or dependencies. See each project's README for individual developer commands.
