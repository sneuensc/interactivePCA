"""
Legend-visibility synchronisation across all active plots.

When the user clicks a legend item to hide/show a categorical group in
any plot, the same group is hidden/shown in every other active plot.
The hidden groups are also written to `hidden-groups-store` so other
callbacks (annotation table, selection counter) can reflect the three-way
status: selected / unselected / hidden.

Implementation mirrors hover_sync: a single clientside callback listens to
`restyleData` from every plot.  The callback calls Plotly.restyle() directly
on the other divs (no Python round-trip) and returns an updated store value.
A Set-based skip flag prevents the programmatic restyle from re-entering.
"""

import dash
from dash import Input, Output, State


def register_legend_sync_callbacks(app, show_map_plot=True, show_time_plot=True):

    # Reset hidden-groups-store entry for the new group whenever the dropdown
    # changes: the figure is re-rendered with all traces visible, so the store
    # must agree.
    @app.callback(
        Output('hidden-groups-store', 'data', allow_duplicate=True),
        Input('dropdown-group', 'value'),
        State('hidden-groups-store', 'data'),
        prevent_initial_call=True
    )
    def reset_hidden_on_group_change(group, hidden_store):
        if not hidden_store or not group:
            return dash.no_update
        if hidden_store.get(group):
            new_store = dict(hidden_store)
            new_store[group] = []
            return new_store
        return dash.no_update

    plot_ids = ['pca-plot']
    if show_map_plot:
        plot_ids.append('pca-map-plot')
    if show_time_plot:
        plot_ids.append('time-histogram')

    if len(plot_ids) < 2:
        return

    all_ids_js = '[' + ', '.join(f"'{p}'" for p in plot_ids) + ']'
    fn_args    = ', '.join(f'rd{i}' for i in range(len(plot_ids)))

    js = f"""
    function({fn_args}, hiddenStore, group) {{
        var NO_UPDATE = window.dash_clientside.no_update;
        var ctx = dash_clientside.callback_context;
        var triggered = ctx.triggered && ctx.triggered[0];
        if (!triggered) return [NO_UPDATE, NO_UPDATE];

        var triggeredId = ctx.triggered_id ||
            (triggered ? triggered.prop_id.split('.')[0] : null);

        // Skip if this restyle was triggered by us (prevents infinite loop)
        if (!window._legendSyncSkip) window._legendSyncSkip = new Set();
        if (window._legendSyncSkip.has(triggeredId)) {{
            window._legendSyncSkip.delete(triggeredId);
            return [NO_UPDATE, NO_UPDATE];
        }}

        // Locate the restyleData that fired
        var allIds = {all_ids_js};
        var args   = [{fn_args}];
        var restyleData = null;
        for (var k = 0; k < allIds.length; k++) {{
            if (allIds[k] === triggeredId) {{ restyleData = args[k]; break; }}
        }}

        if (!restyleData || !restyleData[0] || !('visible' in restyleData[0])) {{
            return [NO_UPDATE, NO_UPDATE];
        }}

        var propDict     = restyleData[0];
        var traceIndices = restyleData[1];
        var visArray     = propDict['visible'];

        // Helper: resolve the Plotly div for a component id
        function getDiv(id) {{
            var el = document.getElementById(id);
            if (!el) return null;
            if (el.data) return el;
            var inner = el.querySelector && el.querySelector('.js-plotly-plot');
            return (inner && inner.data) ? inner : null;
        }}

        var srcDiv = getDiv(triggeredId);
        if (!srcDiv) return [NO_UPDATE, NO_UPDATE];

        // Build name → visible map from the source figure's trace names
        var visMap = {{}};
        for (var i = 0; i < traceIndices.length; i++) {{
            var idx  = traceIndices[i];
            var name = srcDiv.data[idx] && srcDiv.data[idx].name;
            if (name && name !== '__hover_highlight__') {{
                visMap[name] = Array.isArray(visArray) ? visArray[i] : visArray;
            }}
        }}

        if (!Object.keys(visMap).length) return [NO_UPDATE, NO_UPDATE];

        // ── Apply visibility to every other plot ───────────────────────────
        allIds.forEach(function(plotId) {{
            if (plotId === triggeredId) return;
            var div = getDiv(plotId);
            if (!div) return;

            var idxList = [], visList = [];
            for (var j = 0; j < div.data.length; j++) {{
                var tname = div.data[j].name;
                if (tname in visMap) {{
                    idxList.push(j);
                    visList.push(visMap[tname]);
                }}
            }}

            if (idxList.length) {{
                window._legendSyncSkip.add(plotId);
                Plotly.restyle(div, {{visible: visList}}, idxList);
            }}
        }});

        // ── Update hidden-groups-store ─────────────────────────────────────
        if (!group) return [NO_UPDATE, NO_UPDATE];

        var hidden = new Set(((hiddenStore || {{}})[group] || []));
        for (var name in visMap) {{
            var vis = visMap[name];
            if (vis === false || vis === 'legendonly') {{
                hidden.add(name);
            }} else {{
                hidden.delete(name);
            }}
        }}
        var newStore = Object.assign({{}}, hiddenStore || {{}});
        newStore[group] = Array.from(hidden);

        // Signal to apply_hidden_groups_to_plots that plots are already up to
        // date so it can skip the redundant restyle.
        window._hiddenStoreFromLegend = true;

        return [NO_UPDATE, newStore];
    }}
    """

    inputs = [Input(pid, 'restyleData') for pid in plot_ids]

    app.clientside_callback(
        js,
        Output('hover-sync-dummy', 'data', allow_duplicate=True),
        Output('hidden-groups-store', 'data', allow_duplicate=True),
        *inputs,
        State('hidden-groups-store', 'data'),
        State('dropdown-group', 'value'),
        prevent_initial_call=True
    )

    # Apply hidden-groups-store to all plot divs when the store changes from
    # a source other than a legend click (e.g. Status dropdown in the table).
    all_ids_apply_js = '[' + ', '.join(f"'{p}'" for p in plot_ids) + ']'
    apply_js = f"""
    function(hiddenStore, group) {{
        var NO_UPDATE = window.dash_clientside.no_update;

        // Skip if the store was just written by a legend click — the plots
        // are already up to date from the legend_sync restyle.
        if (window._hiddenStoreFromLegend) {{
            window._hiddenStoreFromLegend = false;
            return NO_UPDATE;
        }}

        function getDiv(id) {{
            var el = document.getElementById(id);
            if (!el) return null;
            if (el.data) return el;
            var inner = el.querySelector && el.querySelector('.js-plotly-plot');
            return (inner && inner.data) ? inner : null;
        }}

        var hiddenSet = new Set(((hiddenStore || {{}})[group || ''] || []).map(String));
        var allIds = {all_ids_apply_js};

        allIds.forEach(function(plotId) {{
            var div = getDiv(plotId);
            if (!div) return;
            var idxList = [], visList = [];
            for (var j = 0; j < div.data.length; j++) {{
                var tname = div.data[j].name;
                if (!tname || tname === '__hover_highlight__') continue;
                idxList.push(j);
                visList.push(hiddenSet.has(tname) ? 'legendonly' : true);
            }}
            if (idxList.length) {{
                if (!window._legendSyncSkip) window._legendSyncSkip = new Set();
                window._legendSyncSkip.add(plotId);
                Plotly.restyle(div, {{visible: visList}}, idxList);
            }}
        }});

        return NO_UPDATE;
    }}
    """

    app.clientside_callback(
        apply_js,
        Output('hover-sync-dummy', 'data', allow_duplicate=True),
        Input('hidden-groups-store', 'data'),
        State('dropdown-group', 'value'),
        prevent_initial_call=True
    )
