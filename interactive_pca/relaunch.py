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

    # Under --dev, Werkzeug's own reloader stamps WERKZEUG_RUN_MAIN/
    # WERKZEUG_SERVER_FD onto this process's environment so it can hand its
    # bound socket to its restarted child. That fd is meaningless to our own
    # freshly spawned process (a new session, not a Werkzeug-reloaded child),
    # so inheriting it makes the child try to rebuild a socket from a stale fd
    # number and crash with "Socket operation on non-socket". Strip them so
    # the child starts exactly as if launched fresh from a terminal.
    env = os.environ.copy()
    env.pop('WERKZEUG_RUN_MAIN', None)
    env.pop('WERKZEUG_SERVER_FD', None)

    def _relaunch():
        subprocess.Popen(['/bin/sh', '-c', f'sleep 1; exec {inner}'],
                         start_new_session=True, env=env)
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
    var maxTries = 60;
    var iv = setInterval(function() {
        tries++;
        fetch(url, {mode: 'no-cors', cache: 'no-store'})
            .then(function() {
                clearInterval(iv);
                console.log('Server is up, reloading in 2 seconds...');
                setTimeout(function() {
                    console.log('Reloading now');
                    window.location.href = url;
                }, 2000);
            })
            .catch(function() { /* server still restarting */ });
        if (tries > maxTries) {
            clearInterval(iv);
            // Give up silently on a hung "Starting..." message: the process
            // most likely crashed on startup (a data-loading error, say), and
            // without this the page just waits forever with no feedback.
            var banner = document.createElement('div');
            banner.textContent = 'The server did not come back after ' + maxTries +
                ' seconds — it may have crashed while restarting. Check the ' +
                'terminal/log for a traceback, fix the issue, then reload this page.';
            banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;' +
                'background:#f8d7da;color:#842029;padding:12px 20px;' +
                'font:14px -apple-system,sans-serif;border-bottom:2px solid #f5c2c7;';
            document.body.prepend(banner);
        }
    }, 1000);
    return window.dash_clientside.no_update;
}
"""
