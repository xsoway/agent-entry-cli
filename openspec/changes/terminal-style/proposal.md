## Why
The independent CLI lost the styled presentation of its original terminal entry point.

## What Changes
Restore enhanced header, input background, command menu, hints and role/result hierarchy using existing libraries. Preserve plain output, NO_COLOR and all runtime controls.

## Impact
Only terminal presentation and regression tests; no runtime or public API changes.
