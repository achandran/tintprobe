from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Exercise real zsh ZLE vi keymaps in an isolated PTY, displayed by Ghostty."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import struct
import subprocess
import termios
import time


def fixtures(output):
    rows=[]
    for keymap,style in [('vicmd','steady-block'),('viins','steady-bar')]:
        name='shell-'+keymap;payload='return attempt <= 3\n'
        (output/(name+'.ansi')).write_text(payload)
        rows.append({'id':name,'kind':'native-shell','status':'prepared' if shutil.which('zsh') else 'blocked',
                     'ansi':name+'.ansi','sha256':hashlib.sha256(payload.encode()).hexdigest(),
                     'keymap':keymap,'cursor':{'row':0,'column':16,'text':'=','style':style}})
    return rows


def launch(payload,ready,release):
    keymap=payload.stem.removeprefix('shell-')
    state=payload.with_suffix('.keymap')
    state.unlink(missing_ok=True)
    zdot=payload.parent/(payload.stem+'-zsh');zdot.mkdir(exist_ok=True)
    (zdot/'.zshrc').write_text('''
unset HISTFILE
SAVEHIST=0
PS1=''
RPS1=''
KEYTIMEOUT=1
bindkey -v
function zle-keymap-select {
  printf '\\033[?25h'
  if [[ $KEYMAP == vicmd ]]; then printf '\\033[2 q'; else printf '\\033[6 q'; fi
  print -r -- "$KEYMAP" > '''+shlex.quote(str(state))+'''
  bindkey -lL main > '''+shlex.quote(str(state.with_suffix('.binding')))+'''
}
function zle-line-init { zle-keymap-select }
zle -N zle-keymap-select
zle -N zle-line-init
''')
    master,slave=pty.openpty()
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0,termios.TIOCSCTTY,0)
    proc=subprocess.Popen([shutil.which('zsh'),'-d','-i'],stdin=slave,stdout=slave,stderr=slave,
                          preexec_fn=controlling_terminal,
                          env=dict(os.environ,ZDOTDIR=str(zdot),TERM='xterm-256color'))
    os.close(slave)
    calibration=''.join(f'\x1b[48;5;{i}m      ' for i in range(1,7))+'\x1b[0m\n\n'
    os.write(1,('\x1b[0m\x1b[2J\x1b[H'+calibration).encode())
    def pump(duration):
        deadline=time.monotonic()+duration
        while time.monotonic()<deadline:
            if proc.poll() is not None:raise RuntimeError('zsh exited before native capture')
            if select.select([master],[],[],min(.05,max(0,deadline-time.monotonic())))[0]:
                os.write(1,os.read(master,65536))
    try:
        deadline=time.monotonic()+5
        while not state.exists():
            if time.monotonic()>deadline:raise RuntimeError('zsh ZLE startup timed out')
            pump(.05)
        # Real editing input only. Never accept/execute the command buffer.
        os.write(master,b'return attempt <= 3\x1b');pump(.2)
        os.write(master,b'016l');pump(.15)
        if keymap=='viins':os.write(master,b'i');pump(.15)
        actual=state.read_text().strip()
        binding=state.with_suffix('.binding').read_text().strip()
        resolved='viins' if actual=='main' and binding=='bindkey -A viins main' else actual
        if resolved!=keymap:raise RuntimeError('zsh did not enter required keymap: '+actual+' / '+binding)
        (payload.with_suffix('.shell.json')).write_text(json.dumps({
            'keymap':resolved,'raw_keymap':actual,'main_binding':binding,'input':'isolated PTY bytes; command buffer never accepted',
            'scope':'Real zsh ZLE with fixture-local conventional cursor hooks, not the user\'s installed shell hooks',
            'zshrc_sha256':hashlib.sha256((zdot/'.zshrc').read_bytes()).hexdigest()}))
        ready.write_text('ready')
        deadline=time.monotonic()+90
        while not release.exists() and time.monotonic()<deadline:pump(.05)
    finally:
        os.close(master)  # Closing the owned PTY sends SIGHUP to its shell.
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload',type=Path,required=True)
    p.add_argument('--ready',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True)
    a=p.parse_args();launch(a.payload,a.ready,a.release)
