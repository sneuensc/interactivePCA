"""
Process-relaunch helper shared by the setup wizard and the main app.

Both the wizard's "Launch" and the main app's "Restart" restart the process on
the same port with a (possibly empty) argument list. ``os.execv`` cannot be used
because it keeps the PID and the old listening socket lingers, so the new bind
fails ("Address already in use"). Instead we spawn a fresh, detached session
that waits briefly and then starts the app, and exit this process immediately so
the port is free by the time the child binds it. A tiny client-side poller
(``POLLER_JS``) reloads the browser once the new server answers.
"""

import logging
import os
import shlex
import subprocess
import sys
import threading


def schedule_relaunch(argv, delay=0.8):
    """Relaunch ``python -m interactive_pca <argv>`` in a detached session.

    The current process exits (freeing its port) once the child is spawned.
    """
    cmd = [sys.executable, '-m', 'interactive_pca', *argv]
    logging.info("Relaunching: %s", ' '.join(cmd))
    inner = ' '.join(shlex.quote(x) for x in cmd)

    def _relaunch():
        subprocess.Popen(['/bin/sh', '-c', f'sleep 1; exec {inner}'],
                         start_new_session=True)
        os._exit(0)

    # Fire after the HTTP response has been flushed to the browser.
    threading.Timer(delay, _relaunch).start()


# Client-side poller: once a relaunch is triggered, reload as soon as the new
# server on `data.port` answers. Used as a clientside_callback body in both apps.
POLLER_JS = """
function(data) {
    if (!data || !data.go) { return window.dash_clientside.no_update; }
    var url = window.location.protocol + '//' + window.location.hostname
              + ':' + data.port + '/';
    var tries = 0;
    var iv = setInterval(function() {
        tries++;
        fetch(url, {mode: 'no-cors', cache: 'no-store'})
            .then(function() { clearInterval(iv); window.location.href = url; })
            .catch(function() { /* server still restarting */ });
        if (tries > 120) { clearInterval(iv); }
    }, 1000);
    return window.dash_clientside.no_update;
}
"""
