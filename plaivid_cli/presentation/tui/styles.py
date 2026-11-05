"""Semantic CSS for the Textual dashboard."""

TUI_CSS = """
        Screen { background: $p-bg; color: $p-text; }
        #shell { height: 1fr; padding: 0 1; background: $p-bg; }
        #topbar { height: 2; padding: 0 1; margin: 0 0 1 0;
                  background: $p-panel; border-bottom: solid $p-border; }
        #brand { width: 1fr; content-align: left middle; }
        #session-label { width: auto; color: $p-green; content-align: right middle; padding: 0 1; }
        #logout { width: 6; min-width: 6; height: 1; margin: 0; padding: 0;
                  background: $p-surface; color: $p-rose; border: none; }
        #logout:focus { background: $p-surface; color: $p-rose; text-style: bold underline; }

        #login-box { width: 64; max-width: 92%; height: auto; border-left: solid $p-blue;
                     background: $p-panel; padding: 1 2; margin: 2 0; }
        #login-title { color: $p-blue; text-style: bold; padding-bottom: 1; }
        #login-warning { color: $p-yellow; padding: 1 0; }
        #login-error { color: $p-rose; padding: 1 0; }
        #login-buttons { height: 1; align-horizontal: right; margin-top: 1; }
        Input { background: $p-surface; border: solid $p-border; color: $p-text; }
        Input:focus { border: solid $p-blue; }

        /* One-line actions in every page; reserve filled color for keyboard focus. */
        Button, Button.-primary, Button.-style-default, Button.-style-flat {
            height: 1; min-width: 0; width: auto; padding: 0 1;
            border: none; background: $p-panel; color: $p-text;
        }
        Button.-primary { color: $p-blue; text-style: bold; }
        Button:hover, Button.-primary:hover { border: none; background: $p-surface; color: $p-blue; }
        Button:focus, Button.-primary:focus {
            border: none; background: $p-surface; color: $p-blue; text-style: bold underline;
        }
        Button:disabled { border: none; background: $p-panel; color: $p-muted; }
        Select { height: 1; color: $p-text; }
        Select > SelectCurrent {
            height: 1; padding: 0 1; border: none; background: $p-surface; color: $p-text;
        }
        Select:focus > SelectCurrent {
            border: none; background: $p-surface; color: $p-blue; text-style: bold;
        }
        Checkbox { height: 1; padding: 0; border: none; background: $p-panel; color: $p-muted; }
        Checkbox:focus { border: none; background: $p-surface; color: $p-blue; }
        Checkbox.-on { color: $p-text; }

        TabbedContent { height: 1fr; background: $p-bg; }
        TabbedContent > ContentTabs { background: $p-panel; }
        TabbedContent Tab { color: $p-muted; background: $p-panel; }
        TabbedContent Tab.-active { color: $p-bg; background: $p-blue; text-style: bold; }
        TabbedContent Tab:focus { text-style: bold; }
        TabPane { padding: 0 1; background: $p-bg; }
        Footer { background: $p-panel; color: $p-text; }
        #notice { height: 1; color: $p-muted; padding: 0 1; }

        #overview { height: 1fr; }
        #overview-scroll { height: 1fr; scrollbar-color: $p-border; }
        #overview-toolbar { height: 3; background: $p-panel; border-bottom: solid $p-border;
                            padding: 0 1; margin-top: 1; }
        #overview-title { width: 1fr; color: $p-blue; text-style: bold; }
        #refresh-label { width: 14; color: $p-cyan; }
        #interval-input { width: 5; height: 1; margin: 0 1; padding: 0 1;
                          border: none; background: $p-surface; color: $p-cyan; }
        #interval-input:focus { border: none; background: $p-surface; color: $p-cyan; text-style: underline; }
        #interval-apply { width: 8; min-width: 8; height: 1; padding: 0; }
        #overview-refresh, #rediscover { width: 11; min-width: 11; height: 1; padding: 0; }
        #overview-toolbar Button { border: none; background: $p-surface;
                                   color: $p-cyan; text-style: bold; }
        #overview-toolbar Button:focus { background: $p-surface; color: $p-blue; text-style: bold underline; }
        #interval-error { height: 1; color: $p-rose; }
        #host-identity { height: auto; color: $p-muted; }
        #overview-grid { height: auto; grid-size: 1; grid-gutter: 1 2; grid-rows: auto; margin-top: 1; }
        .cols-2 #overview-grid { grid-size: 2; }
        .cols-2 #col-right { column-span: 2; }
        .cols-3 #overview-grid { grid-size: 3; }
        .card-column { height: auto; }
        .card-column > .card { margin-bottom: 1; }
        .card { height: auto; background: $p-panel; border: round $p-border; padding: 0 1;
                border-title-color: $p-blue; border-title-style: bold; color: $p-text; }
        .card Static { height: auto; background: $p-panel; color: $p-text; }
        #cpu-chart, #load-chart { width: 100%; height: 9; margin-top: 1; text-wrap: nowrap; text-overflow: clip; }
        #running-card { color: $p-cyan; margin-top: 1; }
        #host-logo { width: 100%; height: auto; text-align: center; margin-bottom: 1; }
        #host-banner { width: 100%; height: auto; text-align: center; margin-bottom: 1; }
        #host-status { color: $p-text; padding: 0 0 0 2; }
        #nic-tabs { height: auto; }
        #nic-tabs .nic-tab { width: auto; min-width: 0; height: 1; margin-right: 2; padding: 0 1;
                             border: none; background: $p-surface; color: $p-muted; }
        #nic-tabs .nic-tab:hover { background: $p-panel; color: $p-text; }
        #nic-tabs .nic-tab:focus { text-style: underline; }
        #nic-tabs .nic-tab.-primary, #nic-tabs .nic-tab.-primary:hover, #nic-tabs .nic-tab.-primary:focus {
            background: $p-blue; color: $p-bg; text-style: bold; }
        #nic-detail { height: auto; color: $p-muted; margin-top: 1; }
        #rediscover { margin: 1 0 0 0; }
        #processes-card { margin-top: 1; }
        #process-row { height: auto; }
        #metrics-processes { width: 1fr; }
        #metrics-commands { width: 36; border-left: solid $p-border; padding-left: 1; color: $p-cyan; }
        .cols-1 #process-row, .cols-2 #process-row { layout: vertical; }
        .cols-1 #metrics-processes, .cols-2 #metrics-processes { width: 100%; }
        .cols-1 #metrics-commands, .cols-2 #metrics-commands { width: 100%; border-left: none;
                                                              border-top: solid $p-border;
                                                              padding: 1 0 0 0; margin-top: 1; }
        #fleet-summary { height: 5; margin-top: 1; align-vertical: middle; }
        .metric-card { width: 1fr; height: 5; margin-right: 1; padding: 0 1;
                       border-left: solid $p-border; background: $p-surface; }
        .metric-card:focus-within { border-left: solid $p-blue; }
        .metric-title { color: $p-muted; text-style: bold; }
        .metric-value { color: $p-cyan; text-style: bold; }
        #refresh-button { width: 11; min-width: 11; margin: 0 0 0 1; }
        #vm-list { height: 1fr; min-height: 13; border: round $p-border;
                   background: $p-panel; }
        #vm-toolbar { height: 3; padding: 0 1; align-vertical: middle; background: $p-panel; }
        #bulk-actions { width: 20; }
        #select-all { width: auto; margin-left: 2; }
        #audit-toggle { width: 11; min-width: 11; margin-left: 2; }
        #fleet-table { height: 1fr; min-height: 8; background: $p-surface;
                       border: round $p-border; }
        DataTable > .datatable--header { background: $p-panel; color: $p-text; text-style: bold; }
        DataTable:focus > .datatable--cursor { background: $p-blue; color: $p-bg; }
        #detail-box { height: 10; margin-top: 1; border: round $p-border;
                      background: $p-panel; padding: 1; }
        #action-status { height: 1; color: $p-yellow; }
        #desktop-summary { height: 5; margin-top: 1; align-vertical: middle; }
        #desktop-refresh { width: 11; min-width: 11; margin: 0 0 0 1; }
        #desktop-list { height: 1fr; min-height: 13; border: round $p-border;
                        background: $p-panel; }
        #desktop-toolbar { height: 3; padding: 0 1; align-vertical: middle;
                           background: $p-panel; }
        #desktop-actions { width: 20; }
        #desktop-all { width: auto; margin-left: 2; }
        #desktop-audit-toggle { width: 11; min-width: 11; margin-left: 2; }
        #desktop-search, #vm-search { width: 1fr; height: 1; margin-left: 1; padding: 0 1;
                                      border: none; background: $p-surface; }
        #desktop-search:focus, #vm-search:focus { border: none; background: $p-surface;
                                                  color: $p-blue; text-style: underline; }
        #desktop-table { height: 1fr; min-height: 8; background: $p-surface;
                         border: round $p-border; }
        #desktop-scope, #vm-scope { height: 1; color: $p-muted; }
        #desktop-detail-scroll { height: 10; margin-top: 1;
                                 border: round $p-border; background: $p-panel; }
        #desktop-audit-panel { display: none; height: auto; min-height: 7;
                               border: round $p-border; background: $p-panel; padding: 1; }
        #desktop-detail { height: auto; background: $p-panel; padding: 1; }
        #desktop-action-status { height: auto; color: $p-yellow; }
        #audit-panel { display: none; height: auto; min-height: 7;
                       border: round $p-border; background: $p-panel; padding: 1; }
        """
