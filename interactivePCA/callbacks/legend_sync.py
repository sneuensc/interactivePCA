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

Re-entrancy (our own programmatic restyle on the other plots firing their
own restyleData right back at this same callback) is handled by comparing
against the last known visibility per trace NAME (window._legendVisState)
rather than a "did we just touch this plot" skip flag: restyling a plot to
the value it's already being set to is a no-op by definition, so the echo
is recognised and dropped without needing to track which plot caused it.
This matters because a per-plot skip flag only survives for exactly one
echo — if a "hide" click's echoes haven't all arrived yet when "show" is
clicked, the flag for a given plot can get consumed by the wrong event,
silently dropping that plot from the next sync (visible as: hiding a
group syncs everywhere, but showing it again only updates the plot you
clicked on).
"""

import dash
from dash import Input, Output, State


def _register_apply_callback(app, plot_ids):
    """Apply hidden-groups-store to all plot divs when the store changes from
    a source other than a legend click (e.g. Status dropdown in the table).
    Registered regardless of how many plots are active — even a single plot
    needs to react to the table's Status column, which is the only other
    writer of hidden-groups-store.
    """
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

        // Keep the legend-click sync's own last-known-value cache consistent,
        // so a plain restyle echo from this call reads as "unchanged" there
        // too, instead of being mistaken for a fresh legend click.
        if (!window._legendVisState) window._legendVisState = {{}};

        allIds.forEach(function(plotId) {{
            var div = getDiv(plotId);
            if (!div) return;
            var idxList = [], visList = [];
            for (var j = 0; j < div.data.length; j++) {{
                var tname = div.data[j].name;
                if (!tname || tname === '__hover_highlight__') continue;
                var val = hiddenSet.has(tname) ? 'legendonly' : true;
                idxList.push(j);
                visList.push(val);
                window._legendVisState[tname] = val;
            }}
            if (idxList.length) {{
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

    # window._legendVisState is keyed by trace NAME only (see module docstring),
    # so a name that was hidden under one group (e.g. 'Female' under 'Sex') and
    # happens to reappear under a different group (e.g. 'Female' under 'Status')
    # would otherwise read as "already at that visibility" and get silently
    # dropped from the next sync. Clearing the cache whenever the grouping
    # variable changes — the one event after which every trace name is
    # genuinely fresh — avoids that stale cross-group collision.
    app.clientside_callback(
        """
        function(_group) {
            window._legendVisState = {};
            return window.dash_clientside.no_update;
        }
        """,
        Output('hover-sync-dummy', 'data', allow_duplicate=True),
        Input('dropdown-group', 'value'),
        prevent_initial_call=True,
    )

    plot_ids = ['pca-plot']
    if show_map_plot:
        plot_ids.append('pca-map-plot')
    if show_time_plot:
        plot_ids.append('time-histogram')

    # Cross-plot legend-click sync only makes sense with 2+ plots — skip
    # registering it (and the name-collision cache above still applies, it's
    # harmless with one plot) when there's nothing else to sync to. The
    # apply_js callback below (hidden-groups-store -> plots, e.g. from the
    # table's Status column) still matters with a single plot, so it is
    # registered unconditionally further down.
    if len(plot_ids) < 2:
        _register_apply_callback(app, plot_ids)
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

        // ── Keep only names whose visibility actually changed ───────────────
        // Restyling the other plots below fires their own restyleData right
        // back at this callback; by the time that echo arrives,
        // _legendVisState already holds the new value, so it's recognised as
        // "nothing changed" and dropped — no per-plot skip bookkeeping needed.
        if (!window._legendVisState) window._legendVisState = {{}};
        var changedMap = {{}};
        var anyChanged = false;
        for (var name in visMap) {{
            var newVal = visMap[name];
            if (window._legendVisState[name] !== newVal) {{
                changedMap[name] = newVal;
                window._legendVisState[name] = newVal;
                anyChanged = true;
            }}
        }}
        if (!anyChanged) return [NO_UPDATE, NO_UPDATE];

        // ── Apply visibility across all plots ───────────────────────────────
        // The source plot is included too: in dual (colour+shape) mode the
        // clickable colour legend entry is a neutral swatch trace while the
        // data lives in a separate same-named trace, so the source plot's data
        // trace must be toggled here as well.
        allIds.forEach(function(plotId) {{
            var div = getDiv(plotId);
            if (!div) return;

            var idxList = [], visList = [];
            for (var j = 0; j < div.data.length; j++) {{
                var tname = div.data[j].name;
                if (tname in changedMap) {{
                    idxList.push(j);
                    visList.push(changedMap[tname]);
                }}
            }}

            if (idxList.length) {{
                Plotly.restyle(div, {{visible: visList}}, idxList);
            }}
        }});

        // ── Update hidden-groups-store ─────────────────────────────────────
        if (!group) return [NO_UPDATE, NO_UPDATE];

        var hidden = new Set(((hiddenStore || {{}})[group] || []));
        for (var name in changedMap) {{
            var vis = changedMap[name];
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

    _register_apply_callback(app, plot_ids)
