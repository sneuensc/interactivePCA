var dagcomponentfuncs = (window.dashAgGridComponentFunctions =
    window.dashAgGridComponentFunctions || {});

/**
 * ColorPickerRenderer
 *
 * Renders an <input type="color"> inside an AG Grid cell.
 * Uses local React state so the picker responds smoothly without
 * round-tripping to Python on every frame.  The value is only
 * committed back to AG Grid (and therefore to Dash's rowData) when
 * the picker is closed (onBlur), keeping network traffic minimal.
 */
dagcomponentfuncs.ColorPickerRenderer = function (props) {
    var _React$useState = React.useState(props.value || '#cccccc');
    var color = _React$useState[0];
    var setColor = _React$useState[1];

    // Keep local state in sync when AG Grid pushes a new value
    // (e.g. after undo, row refresh, or external rowData update).
    React.useEffect(function () {
        setColor(props.value || '#cccccc');
    }, [props.value]);

    return React.createElement(
        'div',
        {
            style: {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%'
            }
        },
        React.createElement('input', {
            type: 'color',
            value: color,
            onChange: function (e) {
                setColor(e.target.value);
            },
            onBlur: function (e) {
                props.node.setDataValue(props.column.colId, e.target.value);
            },
            style: {
                width: '40px',
                height: '32px',
                padding: '0',
                border: '1px solid #ced4da',
                cursor: 'pointer',
                borderRadius: '3px'
            }
        })
    );
};
