"""Native macOS Ghostty capture worker. Run only where native UI access is allowed."""
import argparse
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import time
import signal
from uuid import uuid4



def pixel_gate(measurement, colors):
    missing = [color for color in colors if measurement.get('counts', {}).get(color, 0) < 100]
    return {'pass':not missing, 'missing_swatches':missing,
            'scope':'Calibration swatch presence only; does not certify glyph legibility, font, cursor, selection, or content completeness.'}


def emit_scene(payload, ready, release, cursor=None, style="steady-block", control=None):
    calibration = ''.join(f'\x1b[48;5;{i}m      ' for i in range(1, 7))+'\x1b[0m\n\n'
    os.write(1, ('\x1b[0m\x1b[?25l\x1b[2J\x1b[H'+calibration).encode()+payload.read_bytes()+b'\x1b[0m\n')
    def set_cursor(style):
        row,column=cursor
        codes={'blinking-block':1,'steady-block':2,'blinking-underline':3,'steady-underline':4,'blinking-bar':5,'steady-bar':6,'hidden':2}
        visible='l' if style=='hidden' else 'h'
        os.write(1,f'\x1b[{codes[style]} q\x1b[?25{visible}\x1b[{row+3};{column+1}H'.encode())
    if cursor is not None:set_cursor(style)
    ready.write_text('ready')
    deadline = time.monotonic()+180
    sequence=None
    while not release.exists() and time.monotonic() < deadline:
        if control and control.exists():
            request=json.loads(control.read_text())
            if request['sequence']!=sequence:
                set_cursor(request['style']);sequence=request['sequence']
                ready.write_text(str(sequence))
        time.sleep(.05)


def write_launcher(output, name, payload, ready, release, cursor=None, control=None):
    """Keep argument quoting and child errors independent of app launch parsing."""
    launcher = output/(name+'.launch.sh')
    started, log = output/(name+'.started'), output/(name+'.child.log')
    for path in (started, log):
        path.unlink(missing_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), '--emit', str(payload),
               '--ready', str(ready), '--release', str(release)]
    if cursor is not None:
        command += ['--cursor-row',str(cursor['row']),'--cursor-column',str(cursor['column']), '--cursor-style',cursor.get('style','steady-block')]
    if control:command += ['--control',str(control)]
    launcher.write_text('#!/bin/sh\n'+
        'printf started > '+shlex.quote(str(started))+'\n'+
        'exec '+shlex.join(command)+' 2>'+shlex.quote(str(log))+'\n')
    return launcher, started, log


def timeout_reason(ready, started, log):
    if ready.exists():
        return 'Fixture rendered, but no uniquely titled Ghostty window was found'
    detail = log.read_text(errors='replace').strip() if log.exists() else ''
    if detail:
        return 'Fixture child failed: '+detail[-4000:]
    if started.exists():
        return 'Fixture launcher started, but child did not write the ready marker; inspect '+str(log)
    return 'Ghostty did not start the fixture launcher; inspect its startup/configuration error window'


def build_helper(output):
    from tintprobe.context import ROOT, script_path
    helper = output/'ghostty-capture'
    subprocess.run(['swiftc', '-module-cache-path', '/private/tmp/ithilien-swift-cache',
                    str(script_path('ghostty_capture.swift')), '-o', str(helper)], check=True, timeout=120)
    return helper


def session_worker(request_path, stop_path):
    """One terminal child, multiple sequential scenes, bounded lifetime.

    No shell evaluates requests. Only fixture subprocesses in this checkout are
    launched. The parent releases each scene before submitting the next one.
    """
    previous = None
    deadline = time.monotonic()+900
    while not stop_path.exists() and time.monotonic()<deadline:
        if not request_path.exists():
            time.sleep(.05); continue
        request = json.loads(request_path.read_text())
        if request['sequence'] == previous:
            time.sleep(.05); continue
        previous = request['sequence']
        ready, release = Path(request['ready']), Path(request['release'])
        if request['kind'] == 'native-neovim':
            command = [sys.executable, str(Path(__file__).with_name('ghostty_neovim.py')),
                       '--request', request['payload'], '--ready', str(ready), '--release', str(release)]
        elif request['kind'] == 'native-shell':
            command = [sys.executable, str(Path(__file__).with_name('ghostty_shell.py')),
                       '--payload', request['payload'], '--ready', str(ready), '--release', str(release)]
        else:
            command = [sys.executable, str(Path(__file__).resolve()), '--emit', request['payload'],
                       '--ready', str(ready), '--release', str(release)]
            cursor=request.get('cursor')
            if cursor:
                command += ['--cursor-row',str(cursor['row']),'--cursor-column',str(cursor['column']), '--cursor-style',cursor['style']]
            if request.get('control'): command += ['--control',request['control']]
        with Path(request['log']).open('w') as log:
            child = subprocess.Popen(command, stderr=log)
            try:
                while child.poll() is None:
                    if stop_path.exists() or time.monotonic()>deadline:
                        release.touch(); break
                    time.sleep(.05)
                try: child.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    child.terminate(); child.wait(timeout=5)
            finally:
                Path(request['finished']).write_text(str(child.returncode))


class FixtureSession:
    """Own exactly one new window and explicitly close only that window."""
    def __init__(self, output, helper):
        self.output, self.helper = output, helper
        self.title = 'Ithilien evaluation '+uuid4().hex
        self.window = None
        self.request = output/'session-request.json'
        self.stop = output/'session-stop'
        self.request.unlink(missing_ok=True); self.stop.unlink(missing_ok=True)
        self.sequence = 0

    def open(self):
        self.previous_pid=json.loads(subprocess.check_output([str(self.helper),'frontmost'],timeout=10))['pid']
        config = self.output/'session.conf'
        config.write_text((self.output/'ghostty.conf').read_text()+
                          f'\ntitle = {self.title}\nwindow-width = 120\nwindow-height = 40\nconfirm-close-surface = false\n')
        launcher = self.output/'session.launch.sh'
        command = [sys.executable,str(Path(__file__).resolve()),'--session',str(self.request),'--stop',str(self.stop)]
        launcher.write_text('#!/bin/sh\nexec '+shlex.join(command)+' 2>'+shlex.quote(str(self.output/'session.log'))+'\n')
        subprocess.run(['open','-na','Ghostty','--args','--config-default-files=false',
                        '--config-file='+str(config),'--shell-integration=none',
                        '--quit-after-last-window-closed=true',
                        '--initial-command=shell:'+shlex.join(['/bin/sh',str(launcher)])],
                       check=True,timeout=15,capture_output=True)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            found=json.loads(subprocess.check_output([str(self.helper),'windows',self.title],timeout=10))['windows']
            if len(found)>1: raise RuntimeError('Ambiguous fixture window; refusing input')
            if found:
                self.window=found[0]
                (self.output/'session-window.json').write_text(json.dumps({'title':self.title,'window':self.window}))
                return
            time.sleep(.1)
        raise RuntimeError('Isolated Ghostty window did not open; see session.log')

    def scene(self, row, ready, release, control):
        self.sequence += 1
        ready.unlink(missing_ok=True); release.unlink(missing_ok=True)
        finished=self.output/(row['id']+'.finished');finished.unlink(missing_ok=True)
        log=self.output/(row['id']+'.child.log')
        cursor=row.get('cursor') or {'row':0,'column':0,'style':'hidden'}
        payload=self.output/(row.get('request') or row['ansi'])
        request={'sequence':self.sequence,'kind':row.get('kind','command'),'payload':str(payload),
                 'ready':str(ready),'release':str(release),'finished':str(finished),'log':str(log),
                 'cursor':cursor,'control':str(control) if control else None}
        pending=self.request.with_suffix('.pending')
        pending.write_text(json.dumps(request));pending.replace(self.request)
        deadline=time.monotonic()+20
        while not ready.exists():
            if finished.exists(): raise RuntimeError('Native fixture exited: '+log.read_text()[-4000:])
            if time.monotonic()>deadline: raise RuntimeError('Native fixture ready timeout: '+str(log))
            time.sleep(.05)
        return finished

    def close(self):
        # Close before terminating the terminal child: this avoids Ghostty's
        # post-exit surface lingering and still permits exact window identity.
        try:
            found=json.loads(subprocess.check_output([str(self.helper),'windows',self.title],timeout=10))['windows']
            if len(found)>1: raise RuntimeError('Ambiguous fixture cleanup identity')
            if found:
                if self.window is not None and found != [self.window]: raise RuntimeError('Fixture cleanup identity changed')
                subprocess.run([str(self.helper),'close',self.title,str(found[0])],check=True,capture_output=True,timeout=10)
            deadline=time.monotonic()+5
            while found and time.monotonic()<deadline:
                time.sleep(.1)
                found=json.loads(subprocess.check_output([str(self.helper),'windows',self.title],timeout=10))['windows']
            if found: raise RuntimeError('Fixture window remained open after cleanup')
            (self.output/'session-cleanup.json').write_text(json.dumps({'closed':True,'title':self.title,'window':self.window}))
        finally:
            self.stop.touch()


def capture(output, report):
    from tintprobe.context import ROOT, load_palette
    if sys.platform != 'darwin':
        raise RuntimeError('Native Ghostty capture currently requires macOS')
    helper = build_helper(output)
    # Read-only preflight before launching any fixture windows. Never requests permission.
    subprocess.run([str(helper), 'windows', 'ithilien-preflight'], check=True, capture_output=True, timeout=10)
    palette = load_palette()
    colors = list(dict.fromkeys(list(palette['ansi'].values())[1:7]))
    results = []
    report['native_captures'] = results
    session = FixtureSession(output, helper)
    def terminate(signum, frame):
        raise KeyboardInterrupt('Native capture terminated; cleaning up fixture')
    previous_sigterm = signal.signal(signal.SIGTERM, terminate)
    try:
        session.open()
        for row in report['results']:
            if row['status'] != 'prepared':
                results.append({'id':row['id'], 'pass':False, 'reason':'Command fixture failed to prepare'})
                continue
            title, window = session.title, session.window
            ready, release = output/(row['id']+'.ready'), output/(row['id']+'.release')
            control=output/(row['id']+'.control.json') if row.get('transitions') else None
            if control:control.unlink(missing_ok=True)
            finished = None
            try:
                finished = session.scene(row, ready, release, control)
                if row.get('cursor') or row.get('selection') or row.get('kind')=='native-neovim':
                    subprocess.run([str(helper),'focus',title,str(window)],check=True,capture_output=True,timeout=10)
                time.sleep(.5)
                image = output/(row['id']+'.png')
                def grab(path):
                    # macOS can transiently reject a just-redrawn window. Retry
                    # the same identity only; never capture a desktop fallback.
                    for attempt in range(3):
                        found=json.loads(subprocess.check_output([str(helper),'windows',title],timeout=10))['windows']
                        if found != [window]: raise RuntimeError('Fixture capture identity changed')
                        path.unlink(missing_ok=True)
                        try:
                            subprocess.run(['/usr/sbin/screencapture','-x','-o','-l',str(window),str(path)],check=True,timeout=15,capture_output=True)
                            return
                        except subprocess.CalledProcessError:
                            if attempt==2: raise
                            time.sleep(.25)
                interaction_evidence={}
                if row.get('inactive'):
                    interaction_evidence=json.loads(subprocess.check_output([str(helper),'deactivate',title,str(window),str(session.previous_pid)],timeout=10))
                    time.sleep(.3)
                if row.get('selection'):
                    from tintprobe.ghostty_quality import grid,srgb_image
                    from tintprobe.ghostty_interactions import drag_points
                    before=output/(row['id']+'.before.png');grab(before)
                    decoded=srgb_image(before)
                    points=drag_points(grid(decoded,colors),decoded.size,row['selection'])
                    subprocess.run([str(helper),'drag',title,str(window),*[str(v) for v in points]],
                                   check=True,capture_output=True,timeout=10)
                    interaction_evidence={'before_image':before.name,'drag_fractions':points,'input':'native mouse drag','window':window}
                    time.sleep(.2)
                frames=[]
                if row.get('transitions'):
                    for i,style in enumerate(row['transitions']):
                        pending=control.with_suffix('.pending')
                        pending.write_text(json.dumps({'sequence':i,'style':style}));pending.replace(control)
                        deadline=time.monotonic()+3
                        while ready.read_text()!=str(i):
                            if time.monotonic()>deadline:raise RuntimeError('Cursor transition handshake timed out')
                            time.sleep(.05)
                        time.sleep(.15)
                        path=output/(row['id']+f'.state-{i:02}.png');grab(path)
                        frames.append({'image':path.name,'style':style,'time':time.monotonic()})
                    image.write_bytes((output/frames[0]['image']).read_bytes())
                elif row.get('cursor',{}).get('style','').startswith('blinking-'):
                    for i in range(16):
                        path=output/(row['id']+f'.phase-{i:02}.png')
                        grab(path);frames.append({'image':path.name,'time':time.monotonic()})
                        time.sleep(.15)
                    image.write_bytes((output/frames[0]['image']).read_bytes())
                else:grab(image)
                measurement = json.loads(subprocess.check_output([str(helper), 'pixels', str(image), *colors], timeout=30))
                import hashlib
                oracle=output/(row['id']+'.cells.json')
                results.append({'id':row['id'], 'image':image.name, 'pixels':measurement,
                                'cells_sha256':hashlib.sha256(oracle.read_bytes()).hexdigest() if oracle.exists() else None,
                                'frames':frames,'interaction':interaction_evidence,'calibration':pixel_gate(measurement, colors)})
                report['coverage']['native_pixels']=f'{len(results)} framesets captured; per-case quality analysis follows'
                report['render_profile']['light']['native_capture']='captured in Ghostty'
                report['scope']='Native frames captured for the completed cases; missing cases and full native workflows remain unverified.'
            except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
                if not row.get('inactive'):raise
                # An original app on a different macOS Space can make the
                # inactive window unavailable to screencapture. Keep that gap
                # visible and continue other scenes in the same owned window.
                results.append({'id':row['id'],'capture_status':'blocked','reason':str(exc)})
            finally:
                release.write_text('release')
                if finished:
                    deadline=time.monotonic()+8
                    while not finished.exists():
                        if time.monotonic()>deadline: raise RuntimeError('Fixture failed to exit after release')
                        time.sleep(.05)
                    if finished.read_text()!='0': raise RuntimeError('Fixture cleanup failed; see '+row['id']+'.child.log')
    finally:
        try:
            session.close()
        finally:
            # Preserve acquisition evidence even for interruption/cleanup error.
            (output/'report.json').write_text(json.dumps(report,indent=2))
            signal.signal(signal.SIGTERM, previous_sigterm)
    report['native_captures'] = results
    report['coverage']['native_pixels'] = 'captured; per-case quality analysis follows'
    report['render_profile']['light']['native_capture'] = 'captured in Ghostty'
    report['scope'] = ('Native Ghostty screenshots of prepared command output and a labeled ANSI probe. '
                       'Per-case text and interaction gates follow capture; font identity, native editor/agent workflows, and comfort remain unverified.')
    report['status'] = 'fail' if any(not r.get('calibration', {}).get('pass') for r in results) else 'incomplete'
    report['reason'] = 'Native screenshots captured; see per-case command and interaction quality evidence.'
    report['pass'] = False
    return report


if __name__ == '__main__':
    def terminate(signum, frame):
        raise KeyboardInterrupt('Native fixture process terminated')
    signal.signal(signal.SIGTERM, terminate)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session', type=Path)
    p.add_argument('--stop', type=Path)
    p.add_argument('--emit', type=Path)
    p.add_argument('--ready', type=Path)
    p.add_argument('--release', type=Path)
    p.add_argument('--control', type=Path)
    p.add_argument('--cursor-row', type=int)
    p.add_argument('--cursor-column', type=int)
    p.add_argument('--cursor-style', choices=('steady-block','steady-bar','steady-underline','blinking-block','blinking-bar','blinking-underline','hidden'),default='steady-block')
    args = p.parse_args()
    if args.session and args.stop:
        session_worker(args.session, args.stop)
    elif args.emit and args.ready and args.release:
        cursor=None
        if args.cursor_row is not None or args.cursor_column is not None:
            if args.cursor_row is None or args.cursor_column is None or not 0<=args.cursor_row<36 or not 0<=args.cursor_column<120:
                p.error('Cursor requires row 0..35 and column 0..119')
            cursor=(args.cursor_row,args.cursor_column)
        emit_scene(args.emit, args.ready, args.release, cursor, args.cursor_style, args.control)
    else:
        p.error('Use evaluate_ghostty.py --capture to run the capture worker')
