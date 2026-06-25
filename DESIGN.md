---
name: GKGuard C2 Workbench
description: Campus-security AI search workbench for evidence review, candidate comparison, and route context.
colors:
  primary: "#246FF5"
  primary-hover: "#1858D6"
  surface: "#FFFFFF"
  surface-soft: "#F8FBFF"
  background: "#F4F7FB"
  sidebar: "#EEF4FB"
  border: "#DFE6F1"
  border-strong: "#CDD8E8"
  text: "#142033"
  text-muted: "#66758A"
  success: "#0F766E"
  warning: "#B45309"
  danger: "#B4233A"
  evidence-bg: "#111927"
typography:
  title:
    fontFamily: "Segoe UI, Microsoft YaHei, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "0"
  body:
    fontFamily: "Segoe UI, Microsoft YaHei, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  label:
    fontFamily: "Segoe UI, Microsoft YaHei, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "0"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "38px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary-hover}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "38px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "40px"
---

# Design System: GKGuard C2 Workbench

## 1. Overview

**Creative North Star: "The Evidence Desk"**

GKGuard C2 should feel like a controlled evidence desk for campus-security review: left-side navigation, a stable work surface, precise filters, visible candidate uncertainty, and evidence imagery at the center of attention. The interface is not a dashboard, not a command center, and not a marketing surface.

The visual system is restrained and task-oriented. It uses cool neutral surfaces, a single blue action color, compact typography, and clear structural borders. Images, event cards, route nodes, and model output labels create the hierarchy; decoration is intentionally minimal.

**Key Characteristics:**

- Fixed left navigation with two primary entries.
- Evidence imagery and route context are the main visual material.
- Candidate comparison and event details use right-side drawers to preserve context.
- Status labels are concise and model-aware.
- Responsive behavior reorganizes panels instead of shrinking text.

## 2. Colors

The palette is a cool, restrained product palette with one blue action color and semantic status colors reserved for states and model interpretation.

### Primary

- **Operational Blue**: the primary action and selection color. Use it for active navigation, primary buttons, selected events, selected face boxes, and focused route nodes only.

### Secondary

- **Evidence Teal**: the success/high-similarity annotation color. Use it for face boxes, confidence labels, and positive model status labels where the result is still expressed as a model score.
- **Review Amber**: the low-confidence or partial-match color. Use it for low-confidence candidates and "需要人工确认" style states.
- **Blocking Red**: the error and mismatch color. Use it for failed requests, invalid input, and visible mismatch notes in similar-result cards.

### Neutral

- **Workbench Background**: the page background behind the desktop shell.
- **Surface White**: cards, filters, drawers, and content panels.
- **Soft Surface**: secondary information groups, metadata rows, and inactive thumbnail backgrounds.
- **Evidence Black**: media-viewer and keyframe letterbox background.
- **Ink Text**: headings and high-priority labels.
- **Muted Text**: supporting descriptions and metadata labels.

### Named Rules

**The One Accent Rule.** Operational Blue is the only general-purpose accent and must stay under roughly 10% of a screen.

**The Evidence Contrast Rule.** Evidence images are never placed on decorative gradients; they sit on neutral surfaces or Evidence Black.

## 3. Typography

**Display Font:** Segoe UI / Microsoft YaHei / system sans.
**Body Font:** Segoe UI / Microsoft YaHei / system sans.
**Label/Mono Font:** Use the same sans stack unless code-like values need the browser monospace default.

**Character:** Familiar product typography with enough weight for scanning. The interface should read as native, stable, and operational, not editorial.

### Hierarchy

- **Display**: not used for app UI except the app title in narrow onboarding contexts.
- **Headline** (800, 22-26px, 1.25): page titles and drawer titles.
- **Title** (800, 16-20px, 1.3): panel headings, event section headings, candidate groups.
- **Body** (400-600, 14px, 1.5): field text, metadata, descriptions, and table-like rows.
- **Label** (700, 12-13px, 1.25): chips, model-score labels, field labels, compact statuses.

### Named Rules

**The Fixed Scale Rule.** Product text uses fixed rem/px sizes; do not use viewport-scaled headings.

**The No Eyebrow Rule.** Avoid decorative uppercase kickers and numbered section markers unless the content is a real ordered process.

## 4. Elevation

Depth is conveyed through light borders, tonal surfaces, and modest shadows. Panels should feel separated enough for repeated scanning but never like floating promotional cards.

### Shadow Vocabulary

- **Panel Shadow** (`0 18px 42px rgba(30, 50, 82, 0.13)`): major workbench surfaces and modal/drawer shells.
- **Soft Shadow** (`0 10px 24px rgba(44, 70, 110, 0.09)`): secondary panels and selected record emphasis.
- **Annotation Shadow** (`0 6px 14px rgba(15, 23, 42, 0.18)`): face-score labels over media.

### Named Rules

**The Flat At Rest Rule.** Most surfaces are flat with borders. Strong shadows appear only for overlays, active selection, or transient feedback.

## 5. Components

### Buttons

- **Shape:** gently squared product controls (6px radius).
- **Primary:** Operational Blue background, white text, strong weight, compact height.
- **Hover / Focus:** darker blue on hover, visible blue focus ring, no layout shift.
- **Secondary:** white surface, blue text, thin border.

### Chips

- **Style:** compact, rounded labels with tonal backgrounds and explicit text.
- **State:** selected chips use Operational Blue; model-state chips use semantic colors. Do not rely on color alone.

### Cards / Containers

- **Corner Style:** 8px for repeated items, 12px for large workbench shells.
- **Background:** Surface White for primary panels, Soft Surface for metadata groups.
- **Shadow Strategy:** follow the Flat At Rest Rule.
- **Border:** thin neutral borders define structure.
- **Internal Padding:** 12-24px depending on density.

### Inputs / Fields

- **Style:** white fill, neutral border, 6px radius, 40px base height.
- **Focus:** blue focus ring and border shift.
- **Error / Disabled:** use semantic border/text colors plus explicit helper text.

### Navigation

- Fixed left sidebar with two primary entries: "人脸以图搜人" and "人物特征搜索". Active state uses a restrained blue indicator, stronger text, and a light surface. The sidebar should not collapse into icon-only mode at normal desktop widths.

### Evidence Media

Keyframes, body crops, face crops, and query images preserve aspect ratio. Overlays must align to the actual rendered image content area, not letterbox padding. Similarity labels sit outside the face rectangle where space allows.

### Drawers

Candidate-person and event-detail drawers slide from the right, cover part of the current workspace, and preserve the underlying context. They must include close controls, focus-visible states, and recoverable loading/error states.

## 6. Do's and Don'ts

### Do:

- **Do** keep the fixed left navigation and right work area as the primary shell.
- **Do** put event evidence, route context, and model metadata ahead of decoration.
- **Do** show "无法判断" for unknown attributes.
- **Do** separate "完全匹配" and "相似结果" visibly in person-attribute search.
- **Do** keep low-confidence or partial-match states available for human review.
- **Do** use drawers for candidate switching and event detail when context should remain visible.
- **Do** test desktop, medium-width, and mobile/narrow viewports.

### Don't:

- **Don't** create a marketing hero, homepage overview, or generic dashboard landing screen.
- **Don't** use large gradients, glassmorphism, neon security aesthetics, or decorative metric cards.
- **Don't** describe model output as "已确认本人", "绝对匹配", or equivalent certainty.
- **Don't** hide similar results behind tabs; show them below exact matches.
- **Don't** let images, face boxes, labels, or side panels overlap metadata or controls.
- **Don't** collapse the main sidebar into icon-only mode for normal desktop use.
