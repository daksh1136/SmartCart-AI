---
name: SmartCart AI
description: Pick. Scan. Go. Securely.
colors:
  primary: '#176b50'
  secondary: '#80550f'
  ink: '#20322d'
  ground: '#f5f6f2'
  surface: '#ffffff'
  line: '#dfe5df'
typography:
  display: 'DM Sans, Arial, sans-serif'
  body: 'DM Sans, Arial, sans-serif'
rounded:
  card: '12px'
  control: '7px'
spacing:
  content: 'clamp(16px, 3vw, 38px)'
  panel: '20px'
  compact: '8px'
components:
  button-primary: 'emerald fill, white label, 7px radius'
  button-secondary: 'soft neutral fill, green-gray border, dark green label'
  cart-panel: 'white surface, hairline border, restrained shadow, 12px radius'
  status-warning: 'pale amber surface, dark amber label'
  status-verified: 'pale green surface, dark emerald label'
---

# Design System: SmartCart AI

## Overview

**Creative North Star: "Retail Tally Sheet"**

SmartCart AI makes the shelf-to-cart relationship legible while someone shops. A warm, quiet retail surface keeps scan and checkout actions clear and gives physical and scanned quantities a consistent place to meet. The aligned shopper workspace shows scanning and reconciliation together on desktop, then stacks naturally when the available width narrows.

The visual voice is practical and trustworthy. Compact item proof is the signature detail: shelf zone and two counts sit directly beneath each product, with a plain-language status beside them. Camera and sensor states use the same restrained palette while keeping simulated events explicit.

**Key Characteristics:**
- Warm neutral background, white work surfaces, and restrained borders
- Deep green action color with distinct verified and amber review states
- DM Sans typography with compact operational labels and readable headings
- Item-level physical/scanned count proof as a recurring pattern

## Colors

The palette uses softened greens and warm gray-green neutrals, with amber reserved for review states.

### Primary
- **Shelf Emerald** (#176b50): Primary actions, focus accents, and trusted navigation states.
- **Deep Forest** (#12583f): Hover state for primary actions.

### Secondary
- **Review Amber** (#80550f): Discrepancy and pending-evidence text on pale amber surfaces.

### Neutral
- **Deep Cart Ink** (#20322d): Main text and strong labels.
- **Quiet Moss** (#596d61): Supporting copy and metadata.
- **Warm Ground** (#f5f6f2): Application canvas.
- **Clean Surface** (#ffffff): Panels, dialogs, and input surfaces.
- **Divider Gray Green** (#dfe5df): Borders and separators.

**The Status Pair Rule.** Emerald means verified or ready; amber means review is needed. State never relies on color alone: each state keeps a written label.

## Typography

**Display Font:** DM Sans (with Arial, sans-serif fallback)
**Body Font:** DM Sans (with Arial, sans-serif fallback)

**Character:** A single, familiar sans-serif family keeps operational screens calm and consistent. Weight, size, and spacing provide hierarchy rather than decorative font pairing.

### Hierarchy
- **Display** (700, 25px, 1.2): Shopper and operations page heading.
- **Headline** (700, 17px): Panel title.
- **Body** (400, 12–13px, 1.5): Instructions and supporting interface copy.
- **Label** (700, 9–10px, slight positive tracking, uppercase where operational): Section eyebrow and evidence labels.
- **Data** (700, 9–21px, tabular numerals): Cart counts, totals, and status values.

## Layout

The application uses a compact heading and session strip above its primary work area. At wider desktop sizes, scanning and the virtual cart share a balanced two-column workspace. At tablet widths, both shopper and operations work areas stack to prevent cramped columns. At phone widths, the navigation docks across the bottom and the cart, camera, and primary actions flow in one column. The session summary wraps into readable groups.

Spacing is compact and consistent: panels use about 20px padding on desktop and 14px on narrow screens; neighboring work areas keep about 16px separation.

## Elevation & Depth

Panels use a fine border and a restrained, low offset shadow. Larger hierarchy comes from surface separation and spacing rather than colored glow or stacked card treatments.

## Shapes

Panels use a softly rounded 12px corner. Buttons and inputs use tighter 7px corners. Status labels are compact rectangular chips with written state names. The evidence strip uses straight separators to connect shelf location and counts.

## Components

### Buttons
- **Shape:** Compact rounded corners (7px).
- **Primary:** Shelf Emerald background with a white label; hover shifts to Deep Forest.
- **Secondary:** Warm neutral fill, light green-gray border, and dark green text.
- **Focus:** Visible emerald outline; disabled actions remain visibly subdued.

### Chips
- **Verified:** Pale green surface with dark emerald text.
- **Review:** Pale amber surface with Review Amber text.
- **Neutral:** Soft gray-green surface with Quiet Moss text.
- **State:** Always include readable status wording.

### Cards / Containers
- **Corner Style:** Soft corners (12px).
- **Background:** White work surface over Warm Ground.
- **Shadow Strategy:** Subtle offset shadow with a hairline divider.
- **Internal Padding:** About 20px desktop and 14px on phone.

### Inputs / Fields
- **Style:** White fill, green-gray stroke, 7px radius.
- **Focus:** Visible emerald outline.
- **Error / Disabled:** Error copy identifies the problem; disabled actions preserve their explanation nearby.

### Navigation
- **Style:** Light persistent rail on wide screens, compact icon rail at tablet widths, and labeled fixed bottom navigation on phones. The selected surface uses a soft green fill and clear text contrast.

### Cart Proof Strip
Each product row puts shelf zone, physical quantity, and scanned quantity directly below the product identity. A plain-language verified or discrepancy label sits in the same row so shoppers can see why checkout is available or blocked.

## Do's and Don'ts

### Do:
- **Do** keep shelf and scanned counts together for every product.
- **Do** make checkout state and its reason visible beside the cart total.
- **Do** identify simulated sensor, camera, and billing behaviors in the interface.
- **Do** keep the primary task usable at tablet and phone widths.

### Don't:
- **Don't** imply simulated weights, exit gates, or mock payments are production hardware or charges.
- **Don't** communicate a discrepancy with color alone.
- **Don't** hide the shopping and checkout path behind operational metrics.
