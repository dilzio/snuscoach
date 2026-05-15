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

/* Uniform uppercase label used on all card headers */
.sc-label {
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: var(--sc-label-color) !important;
  line-height: 1.2 !important;
}

/* Downsize any H1 that the nudge markdown might render */
.sc-nudge-md h1 {
  font-size: 0.95rem !important;
  font-weight: 600 !important;
  margin: 0 0 6px 0 !important;
  line-height: 1.4 !important;
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
"""


def apply_theme() -> None:
    app.colors(**_COLORS)
    ui.add_head_html(f"<style>{_CSS}</style>", shared=True)
