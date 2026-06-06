"""
Snapshot export — clientside callback that builds a self-contained HTML file
directly in the browser from Plotly's live in-memory figure state.
"""

from dash import Input, Output, State


def register_snapshot_callback(app):
    app.clientside_callback(
        """
        function(n_clicks, rowData, colDefs) {
            if (!n_clicks) return window.dash_clientside.no_update;

            // ── read current pane sizes from the live DOM ────────────────
            function px(id, prop) {
                var el = document.getElementById(id);
                return el ? Math.round(el.getBoundingClientRect()[prop]) : 0;
            }
            var leftW  = px('pca-left-pane',  'width');
            var rightW = px('pca-right-pane', 'width');
            var pcaH   = px('pca-plot',        'height');
            var timeH  = px('time-histogram',  'height');
            var mapH   = px('pca-map-plot',    'height');
            // Use measured values if available; fall back to equal/default split
            var colCss = (leftW && rightW)
                ? '#left-col{flex:0 0 '+leftW+'px}#right-col{flex:0 0 '+rightW+'px}'
                : '#left-col,#right-col{flex:1 1 0}';
            var pcaFlex  = pcaH  ? 'flex:0 0 '+pcaH+'px'  : 'flex:0 0 60%';
            var timeFlex = timeH ? 'flex:0 0 '+timeH+'px' : 'flex:1 1 auto';
            var mapFlex  = mapH  ? 'flex:0 0 '+mapH+'px'  : 'flex:0 0 60%';

            // ── capture figures ─────────────────────────────────────────
            var PLOT_IDS = ['pca-plot', 'pca-map-plot', 'time-histogram'];
            var panels = {};
            var first  = true;

            PLOT_IDS.forEach(function(compId) {
                var wrapper = document.getElementById(compId);
                if (!wrapper) return;
                var el = wrapper.querySelector('.js-plotly-plot') || wrapper;
                if (!el || !el.data) return;

                var data = el.data.filter(function(t) {
                    return t.name !== '__hover_highlight__';
                });
                var layout = Object.assign({}, el.layout || {});
                delete layout.uirevision;
                layout.autosize = true;
                delete layout.width;
                delete layout.height;

                var cfg = {responsive:true, scrollZoom:true, displayModeBar:true};
                var plotlyTag = first
                    ? '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"><\\/script>\\n'
                    : '';
                first = false;

                var id = 'p_' + compId.replace(/-/g,'_');
                panels[compId] =
                    plotlyTag +
                    '<div id="' + id + '" style="width:100%;height:100%"><\\/div>\\n' +
                    '<script>Plotly.newPlot(' +
                        JSON.stringify(id) + ',' +
                        JSON.stringify(data) + ',' +
                        JSON.stringify(layout) + ',' +
                        JSON.stringify(cfg) +
                    ')<\\/script>';
            });

            // ── build table HTML from Dash State (all rows, not just visible)
            function makeTable(rows, cols) {
                if (!rows || !rows.length || !cols || !cols.length) return '';
                var vcols = cols.filter(function(c) {
                    return c.field && c.field !== 'Selected' && !c.hide;
                });
                if (!vcols.length) return '';
                var th = vcols.map(function(c) {
                    return '<th style="padding:4px 8px;text-align:left;white-space:nowrap;' +
                           'font-size:11px;background:#f8f9fa;position:sticky;top:0;' +
                           'border-bottom:2px solid #dee2e6">' +
                           (c.headerName || c.field) + '<\\/th>';
                }).join('');
                var trs = rows.map(function(row) {
                    var cells = vcols.map(function(c) {
                        var v = row[c.field];
                        return '<td style="padding:3px 8px;border-bottom:1px solid #f0f0f0;' +
                               'white-space:nowrap;font-size:12px">' +
                               (v != null ? String(v) : '') + '<\\/td>';
                    }).join('');
                    return '<tr>' + cells + '<\\/tr>';
                }).join('');
                return '<div style="overflow:auto;height:100%;font-family:sans-serif">' +
                       '<table style="border-collapse:collapse;width:100%">' +
                       '<thead><tr>' + th + '<\\/tr><\\/thead>' +
                       '<tbody>' + trs + '<\\/tbody><\\/table><\\/div>';
            }

            var tblHtml = makeTable(rowData, colDefs);

            // ── assemble HTML ────────────────────────────────────────────
            var ts = new Date().toISOString().slice(0,19).replace(/:/g,'-');
            var html = [
                '<!DOCTYPE html><html lang="en"><head>',
                '<meta charset="utf-8"/>',
                '<meta name="viewport" content="width=device-width,initial-scale=1"/>',
                '<title>interactivePCA snapshot ' + ts + '<\\/title>',
                '<style>',
                '*{box-sizing:border-box;margin:0;padding:0}',
                'html,body{height:100%;font-family:sans-serif;background:#fff;overflow:hidden}',
                'header{height:38px;padding:0 14px;background:#f8f9fa;',
                '  border-bottom:1px solid #dee2e6;display:flex;align-items:center;gap:12px}',
                'header h1{font-size:14px;font-weight:600}',
                'header span{font-size:11px;color:#888}',
                '#workspace{display:flex;height:calc(100vh - 38px);overflow:hidden}',
                colCss + '#left-col,#right-col{min-width:0;display:flex;flex-direction:column;overflow:hidden}',
                '#pca-wrap{'  + pcaFlex  + ';min-height:0}',
                '#time-wrap{' + timeFlex + ';min-height:0}',
                '#map-wrap{'  + mapFlex  + ';min-height:0}',
                '#tbl-wrap{flex:1 1 auto;min-height:0;overflow:auto}',
                '.rv{width:6px;cursor:col-resize;background:#ccc;flex:0 0 6px}',
                '.rh{height:6px;cursor:row-resize;background:#ccc;flex:0 0 6px}',
                '.rv:hover,.rh:hover{background:#888}',
                '<\\/style>',
                '<\\/head><body>',
                '<header><h1>interactivePCA snapshot<\\/h1>',
                '<span>' + ts.replace('T',' ') + '<\\/span><\\/header>',
                '<div id="workspace">',
                '  <div id="left-col">',
                '    <div id="pca-wrap">'  + (panels['pca-plot']      || '') + '<\\/div>',
                '    <div class="rh" id="hl"><\\/div>',
                '    <div id="time-wrap">' + (panels['time-histogram'] || '') + '<\\/div>',
                '  <\\/div>',
                '  <div class="rv" id="vr"><\\/div>',
                '  <div id="right-col">',
                '    <div id="map-wrap">'  + (panels['pca-map-plot']  || '') + '<\\/div>',
                '    <div class="rh" id="hr"><\\/div>',
                '    <div id="tbl-wrap">'  + tblHtml + '<\\/div>',
                '  <\\/div>',
                '<\\/div>',
                '<script>',
                '(function(){',
                '  var raf=null;',
                '  function rp(){if(raf)return;raf=requestAnimationFrame(function(){raf=null;',
                '    document.querySelectorAll(".js-plotly-plot").forEach(function(e){',
                '      if(!e.layout)return;',
                '      var p=e.parentElement;if(!p)return;',
                '      var r=p.getBoundingClientRect();',
                '      if(r.width>0&&r.height>0)',
                '        try{Plotly.relayout(e,{width:r.width,height:r.height})}catch(x){}',
                '    });',
                '  });}',
                '  function iv(r,l,ri){',
                '    var re=document.getElementById(r);if(!re)return;',
                '    re.addEventListener("mousedown",function(e){e.preventDefault();',
                '      var le=document.getElementById(l),re2=document.getElementById(ri);',
                '      var x0=e.clientX,lw=le.getBoundingClientRect().width,',
                '          rw=re2.getBoundingClientRect().width,tot=lw+rw;',
                '      function mv(e){var d=e.clientX-x0,w=Math.max(120,Math.min(tot-120,lw+d));',
                '        le.style.flex="0 0 "+w+"px";re2.style.flex="0 0 "+(tot-w)+"px";rp();}',
                '      function up(){document.removeEventListener("mousemove",mv);',
                '        document.removeEventListener("mouseup",up);rp();}',
                '      document.addEventListener("mousemove",mv);',
                '      document.addEventListener("mouseup",up);',
                '    });',
                '  }',
                '  function ih(r,t,b){',
                '    var re=document.getElementById(r);if(!re)return;',
                '    re.addEventListener("mousedown",function(e){e.preventDefault();',
                '      var te=document.getElementById(t),be=document.getElementById(b);',
                '      var y0=e.clientY,th=te.getBoundingClientRect().height,',
                '          bh=be.getBoundingClientRect().height,tot=th+bh;',
                '      function mv(e){var d=e.clientY-y0,h=Math.max(60,Math.min(tot-60,th+d));',
                '        te.style.flex="0 0 "+h+"px";be.style.flex="0 0 "+(tot-h)+"px";rp();}',
                '      function up(){document.removeEventListener("mousemove",mv);',
                '        document.removeEventListener("mouseup",up);rp();}',
                '      document.addEventListener("mousemove",mv);',
                '      document.addEventListener("mouseup",up);',
                '    });',
                '  }',
                '  window.addEventListener("load",function(){',
                '    iv("vr","left-col","right-col");',
                '    ih("hl","pca-wrap","time-wrap");',
                '    ih("hr","map-wrap","tbl-wrap");',
                '    setTimeout(rp,80);',
                '  });',
                '})();',
                '<\\/script><\\/body><\\/html>'
            ].join('\\n');

            var blob = new Blob([html], {type:'text/html'});
            var url  = URL.createObjectURL(blob);
            var a    = Object.assign(document.createElement('a'),
                           {href:url, download:'interactivePCA_'+ts+'.html'});
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function(){URL.revokeObjectURL(url);}, 2000);
            return window.dash_clientside.no_update;
        }
        """,
        Output('download-snapshot', 'data'),
        Input('export-snapshot-btn', 'n_clicks'),
        State('pca-annotation-table', 'rowData'),
        State('pca-annotation-table', 'columnDefs'),
        prevent_initial_call=True,
    )
