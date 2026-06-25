# Product

## Register

product

## Users

GKGuard is used by campus security and management staff who need to search historical surveillance material, compare uncertain model matches, inspect event evidence, and reconstruct a person's route across camera locations. Users work in a desktop environment where evidence readability, predictable controls, and recoverable states matter more than decorative presentation.

## Product Purpose

GKGuard C2 is a campus-security AI search workbench. It provides local FastAPI services, the Electron desktop shell, CampusVision C1 proxy integration, face-image search, person-attribute search, event evidence presentation, candidate-person comparison, route visualization, mock fallback, release engineering, and documentation support. Success means an operator can move from query input to candidate review, event inspection, route context, and export/hand-off without losing state or mistaking model scores for absolute identity confirmation.

## Brand Personality

Professional, calm, evidence-first.

The interface should feel like an operational investigation tool: restrained, trustworthy, dense enough for repeated use, and visually quiet around the evidence imagery. It should avoid dramatizing AI results and instead make uncertainty, model confidence, and data source boundaries explicit.

## Anti-references

- Marketing landing pages, hero sections, welcome dashboards, and promotional copy.
- Generic SaaS dashboard templates with decorative metric cards, oversized gradients, or repetitive card grids.
- Dark command-center aesthetics, neon security styling, glassmorphism, or excessive glow.
- Interfaces that imply identity certainty with phrases such as "confirmed person" or "absolute match".
- Layouts that hide event evidence, collapse the main navigation into icons, or force large horizontal scrolling in normal desktop use.

## Design Principles

- Evidence leads the layout. Body crops, face crops, keyframes, route nodes, and event metadata carry the visual hierarchy.
- Uncertainty stays visible. Similarity, confidence, partial matches, and unknown attributes are model outputs, not facts.
- The workbench remains stable. Navigation, filters, selected candidates, opened drawers, and event selection should preserve context.
- Density is earned. Repeated operational tasks should be compact and scannable without becoming cramped.
- Integration boundaries are explicit. CampusVision C1, GKGuard C2, mock fallback, and placeholder CampusCar/UE capabilities must remain distinguishable.

## Accessibility & Inclusion

Target at least WCAG AA contrast for text and controls. Keyboard navigation, focus-visible states, touch targets, reduced-motion behavior, recoverable loading/error states, and non-color-only status indicators are required. Unknown model attributes should display as "无法判断" rather than false negative claims.
