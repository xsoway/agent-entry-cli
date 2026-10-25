## ADDED Requirements

### Requirement: Self-contained official page
The site SHALL open without external runtime resources, default to Chinese, support complete English switching, expose actual project usage and show responsive accessible controls.

#### Scenario: Offline navigation and interaction
- **WHEN** a user opens the page at desktop or 380px width, switches language, selects commands and toggles a directory
- **THEN** content remains usable, translated, free of overflow and JavaScript errors, with no fabricated business result

#### Scenario: Reduced motion
- **WHEN** system reduced motion is enabled or the user disables animation
- **THEN** typewriter, loop animation and reveal remain static with all content readable

### Requirement: Safe local release preparation
The project SHALL reject private Git identity metadata, detected secrets and incomplete source snapshots before release, without printing secret values.

#### Scenario: Sensitive identity or credential
- **WHEN** a candidate repository contains a non-noreply author identity or a real-shaped credential in working or reachable historical content
- **THEN** preflight fails and reports only rule and location

#### Scenario: Incomplete snapshot
- **WHEN** required source files are untracked or the release worktree is dirty
- **THEN** release preflight fails until a complete commit is prepared

### Requirement: Truthful deployment state
The site and docs SHALL distinguish prepared URLs from verified live services and preserve user Chinese documentation preference.

#### Scenario: Repository not yet deployed
- **WHEN** local preparation completes before remote authorization
- **THEN** a usable local official page and deployment workflow exist, and the remote acceptance gate remains explicitly pending
