from nicegui import app, ui

_COLORS = dict(
    primary="#3b82f6",
    secondary="#6366f1",
    accent="#0ea5e9",
    dark="#0f172a",
    positive="#10b981",
    negative="#ef4444",
    warning="#f59e0b",
    info="#0ea5e9",
)

_CSS = """
:root {
  --sc-sidebar-bg:    #1e293b;
  --sc-sidebar-hover: #334155;
  --sc-content-bg:    #f1f5f9;
  --sc-nav-text:      #94a3b8;
  --sc-text-sec:      #475569;
  --sc-text-muted:    #94a3b8;
  --sc-label-color:   #64748b;
  --sc-border:        #e2e8f0;
  --sc-border-light:  #f1f5f9;
  --sc-accent-nudge:  #6366f1;
  --sc-accent-meet:   #0ea5e9;
  --sc-accent-wins:   #f59e0b;
  --sc-shadow-card:   0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04);
  --sc-shadow-hover:  0 4px 14px rgba(0,0,0,0.1);
  --sc-radius-card:   10px;
}

/* Card base — override Quasar's 4px radius and default shadow */
.sc-card.q-card {
  border-radius: var(--sc-radius-card) !important;
  box-shadow: var(--sc-shadow-card) !important;
  transition: box-shadow 0.2s;
}
.sc-card.q-card:hover { box-shadow: var(--sc-shadow-hover) !important; }

/* Left-accent card variants */
.sc-card--nudge.q-card  { border-left: 3px solid var(--sc-accent-nudge); }
.sc-card--meet.q-card   { border-left: 3px solid var(--sc-accent-meet); }
.sc-card--wins.q-card   { border-left: 3px solid var(--sc-accent-wins); }
.sc-card--wins-ok.q-card { border-left: 3px solid var(--q-color-positive); }

/* Card header label */
.sc-label {
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.03em !important;
  color: var(--sc-label-color) !important;
  line-height: 1.2 !important;
}

/* Nudge markdown — small, clean, consistent across all elements */
.sc-nudge-md { font-size: 13px !important; line-height: 1.4 !important; }
.sc-nudge-md h1 {
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  margin: 6px 0 3px 0 !important;
  line-height: 1.3 !important;
}
.sc-nudge-md h2,
.sc-nudge-md h3 {
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  margin: 4px 0 2px 0 !important;
  line-height: 1.3 !important;
}
.sc-nudge-md p { font-size: 0.8rem !important; margin: 3px 0 !important; }
.sc-nudge-md ul,
.sc-nudge-md ol { margin: 3px 0 !important; padding-left: 18px !important; }
.sc-nudge-md li { font-size: 0.8rem !important; margin: 2px 0 !important; line-height: 1.4 !important; }
.sc-nudge-md blockquote {
  margin: 4px 0 4px 6px !important;
  padding: 2px 8px !important;
  border-left: 2px solid var(--sc-accent-nudge) !important;
  font-size: 0.78rem !important;
  color: var(--sc-text-sec) !important;
}
.sc-nudge-md code {
  font-size: 0.75rem !important;
  background: #f1f5f9 !important;
  padding: 1px 4px !important;
  border-radius: 3px !important;
}
.sc-nudge-md pre {
  font-size: 0.75rem !important;
  background: #f1f5f9 !important;
  padding: 6px 8px !important;
  border-radius: 4px !important;
  margin: 4px 0 !important;
  overflow-x: auto !important;
}

/* Sidebar nav items */
.sc-nav-item {
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  padding: 8px 10px !important;
  border-radius: 6px !important;
  cursor: pointer !important;
  color: var(--sc-nav-text) !important;
  font-size: 14px !important;
  width: 100% !important;
  transition: background 0.15s, color 0.15s !important;
  user-select: none !important;
  text-decoration: none !important;
}
.sc-nav-item:not(.bg-primary):hover {
  background: var(--sc-sidebar-hover) !important;
  color: #cbd5e1 !important;
}
/* Icon + label inside nav items inherit the item's text colour */
.sc-nav-item .q-icon,
.sc-nav-item .q-item__label {
  color: inherit !important;
}

/* ── List-page header bar (white with bottom border) ────────── */
.sc-page-header {
  padding: 13px 20px !important;
  border-bottom: 1px solid var(--sc-border) !important;
  background: #fff !important;
  align-items: center !important;
  flex-shrink: 0 !important;
}

/* ── Full-page data table ────────────────────────────────────── */
.sc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.sc-table thead th {
  text-align: left;
  font-size: 11px !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  color: var(--sc-label-color) !important;
  padding: 9px 14px !important;
  border-bottom: 2px solid var(--sc-border) !important;
  background: #fafafa !important;
  position: sticky;
  top: 0;
  z-index: 1;
  white-space: nowrap;
}
.sc-table tbody td {
  padding: 10px 14px !important;
  border-bottom: 1px solid var(--sc-border-light) !important;
  vertical-align: middle !important;
}
.sc-table tbody tr.sc-tr-click:hover td { background: #f8faff !important; }
.sc-table tbody tr.sc-tr-section td {
  background: #f8fafc !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  color: var(--sc-label-color) !important;
  padding: 6px 14px !important;
  border-bottom: 1px solid var(--sc-border) !important;
}

/* Status dot (filled / empty) */
.sc-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.sc-dot--on  { background: var(--q-color-positive); }
.sc-dot--off { background: #e2e8f0; border: 1.5px solid #cbd5e1; }

/* Page-header title — 19px/600 matching mockup .page-title */
.sc-page-title {
  font-size: 19px !important;
  font-weight: 600 !important;
  color: #0f172a !important;
  line-height: 1.2 !important;
}

/* Chat message bubbles */
.q-message-text-content { font-size: 13.5px !important; line-height: 1.5 !important; }
.q-message-name { font-size: 10px !important; color: var(--sc-text-muted) !important; }
/* Remove any border/outline from bubble wrappers */
.q-message-text { border: none !important; box-shadow: none !important; outline: none !important; }
.q-message-text-content--sent {
  background: var(--q-color-primary) !important;
  color: #fff !important;
  border: none !important;
}
/* Coach bubble: no border, subtly different background from user bubble */
.q-message-text-content--received {
  background: #edf0f5 !important;
  color: #0f172a !important;
  border: none !important;
  outline: none !important;
}

/* Quasar buttons: no uppercase */
.q-btn { text-transform: none !important; letter-spacing: normal !important; }

/* Outlined inputs: thin 1px border in all states */
.q-field--outlined .q-field__control:before,
.q-field--outlined.q-field--focused .q-field__control:after {
  border-width: 1px !important;
}
"""


def apply_theme() -> None:
    app.colors(**_COLORS)
    ui.add_head_html(f"<style>{_CSS}</style>", shared=True)
