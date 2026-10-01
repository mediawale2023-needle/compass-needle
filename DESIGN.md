# Needle Admin Design System

Needle Admin is the operational/control-plane expression of the Briefcase visual language. It shares the same institutional warmth and typographic restraint but uses independently named Admin tokens and components.

## Direction

- Mode: operate.
- Character: warm paper, precise ink, quiet institutional authority.
- Density: compact enough for operations, with clear grouping and generous separation between workflows.
- Shape: restrained 4–8px corners, hairline borders, minimal shadow, no decorative glass or gradients.
- Motion: 120–180ms state feedback only; no page-entry choreography.

## Semantic Colour

- Paper: `#F2EBD9`
- Deep paper: `#E8E0CB`
- Surface: `#FBF6E7`
- Warm surface: `#F7F0DC`
- Ink: `#1A1812`
- Muted ink: `#625C4D`
- Hairline: `#D4C9AF`
- Needle green: `#006A4D`
- Deep green: `#003B2A`
- Green tint: `#DFE9E2`
- Saffron/warning: `#C76A1A`
- Red/failure: `#8B2E1F`
- Blue/information: `#23496B`

Colour is semantic. Green indicates primary action or healthy/ready state; saffron indicates attention; red indicates failure or destructive action; blue is reserved for neutral information. Inactive UI remains ink and paper.

## Typography

IBM Plex Sans carries operational UI and IBM Plex Serif carries page and major section headings. IBM Plex Mono is limited to identifiers, counts, timestamps, and machine state. Page headings are direct and do not require eyebrow labels.

## Layout and Navigation

- The fixed domain sidebar is the global navigation.
- Domain children use one persistent horizontal secondary navigation.
- Page headers state the task and may include one primary action.
- Operational pages use one principal surface rather than grids of equal promotional cards.
- Context headers and query parameters carry account/seat scope between modules.

## Components

- Buttons, inputs, selects, tabs, status badges, notices, empty/error/loading states, tables, pagination, and confirmation UI share the Admin primitives in `admin/components/admin-ui/`.
- Loading states reserve the final layout.
- Error states name what is unavailable and provide a safe recovery action where one exists.
- Tables scroll horizontally below their minimum readable width and keep actions explicit.
- Destructive and retry actions explain scope and consequence.

## Responsive Contract

At narrower desktop/tablet widths the sidebar collapses, header actions wrap, metric strips become two columns, and tables use labelled overflow rather than compressing columns into illegibility. At phone widths the interface remains operable, with 44px interactive targets and stacked filters.
