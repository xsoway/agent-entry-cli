## ADDED Requirements
### Requirement: Enhanced terminal presentation
Interactive terminals SHALL display project/model header, styled input with command completion and state hints, user/assistant hierarchy and execution status. Presentation SHALL retain secret and terminal-control filtering.

#### Scenario: Enhanced interaction
- **WHEN** a user starts the CLI in a supported terminal
- **THEN** the header and editor show project/model information and run/cancel/queue controls remain usable

#### Scenario: Plain or colorless output
- **WHEN** plain mode or NO_COLOR is selected
- **THEN** output remains readable without color escapes and plain mode omits panels
