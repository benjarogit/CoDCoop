"""Real loopback TCP download faults against production Python/WinINet paths.

Native mode requires an explicitly built probe and an isolated Wine prefix.
This is Wine evidence, not native Windows hardware certification.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('http_installer',ROOT/'tools/install-linux.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
DATA=bytes(range(251))*8400+bytes(range(137))
SHA=hashlib.sha256(DATA).hexdigest()


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def do_GET(self):
        mode=self.server.mode;header=self.headers.get('Range');offset=int(header[6:-1]) if header else 0
        self.server.requests.append({'range':header,'mode':mode})
        body=DATA[offset:];status=206 if header else 200
        content_range=f'bytes {offset}-{len(DATA)-1}/{len(DATA)}'
        if mode=='ignore':offset=0;body=DATA;status=200
        if mode=='bad_hash':body=b'X'*len(body)
        if mode=='bad_start':content_range=f'bytes {offset+1}-{len(DATA)-1}/{len(DATA)}'
        if mode=='bad_end':content_range=f'bytes {offset}-{len(DATA)}/{len(DATA)}'
        if mode=='bad_total':content_range=f'bytes {offset}-{len(DATA)-1}/{len(DATA)+1}'
        if mode=='backwards':content_range=f'bytes {offset}-{offset-1}/{len(DATA)}'
        if mode=='segment':
            body=body[:17000];status=206;content_range=f'bytes {offset}-{offset+len(body)-1}/{len(DATA)}'
        self.send_response(status)
        if status==206 and mode!='missing_range':self.send_header('Content-Range',content_range)
        if mode!='no_length':self.send_header('Content-Length',str(len(body)+(1 if mode=='bad_length' else 0)))
        self.send_header('Connection','close');self.end_headers()
        try:
            sent=body[:(1<<20)+113] if mode=='interrupt' else body
            self.wfile.write(sent);self.wfile.flush()
            if mode=='interrupt':self.connection.shutdown(socket.SHUT_WR)
        except (BrokenPipeError,ConnectionResetError,OSError):pass
        self.close_connection=True


class PythonDownloadHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.dest=Path(self.temp.name)/'asset.zip'
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.mode='good';self.server.requests=[]
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01},daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/asset.zip'
    def close_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)
    def transfer(self):
        try:installer.download(self.url,str(self.dest),SHA,len(DATA));return True
        except (OSError,ValueError):return False
    @property
    def part(self):return Path(str(self.dest)+'.part')

    def test_real_disconnect_keeps_partial_then_resumes_exact_stored_offset(self):
        self.server.mode='interrupt';self.assertFalse(self.transfer())
        self.assertFalse(self.dest.exists());self.assertTrue(self.part.exists())
        offset=self.part.stat().st_size;self.assertGreater(offset,0);self.assertLess(offset,len(DATA))
        self.assertEqual(self.part.read_bytes(),DATA[:offset])
        self.server.mode='good';self.assertTrue(self.transfer())
        self.assertEqual(self.server.requests[-1]['range'],f'bytes={offset}-')
        self.assertEqual(self.dest.read_bytes(),DATA);self.assertFalse(self.part.exists())

    def test_invalid_range_or_length_never_modifies_existing_partial(self):
        for mode in ['bad_start','bad_end','bad_total','backwards','missing_range','bad_length']:
            with self.subTest(mode=mode):
                self.part.write_bytes(DATA[:7]);self.server.mode=mode
                self.assertFalse(self.transfer());self.assertEqual(self.part.read_bytes(),DATA[:7])
                self.assertFalse(self.dest.exists())

    def test_ignored_range_replaces_partial_and_cache_hit_performs_no_http(self):
        self.part.write_bytes(b'wrong-prefix');self.server.mode='ignore'
        self.assertTrue(self.transfer());self.assertEqual(self.dest.read_bytes(),DATA)
        calls=len(self.server.requests);self.assertTrue(self.transfer());self.assertEqual(len(self.server.requests),calls)

    def test_corrupt_cache_is_repaired_and_bad_checksum_never_promoted(self):
        self.dest.write_bytes(b'OLD_CACHE');self.server.mode='bad_hash'
        self.assertFalse(self.transfer());self.assertEqual(self.dest.read_bytes(),b'OLD_CACHE');self.assertFalse(self.part.exists())
        self.server.mode='good';self.assertTrue(self.transfer());self.assertEqual(self.dest.read_bytes(),DATA)
        self.dest.write_bytes(b'Z'*len(DATA));self.assertTrue(self.transfer());self.assertEqual(self.dest.read_bytes(),DATA)
        self.dest.unlink();self.part.write_bytes(b'corrupt-prefix')
        self.assertFalse(self.transfer());self.assertFalse(self.dest.exists());self.assertFalse(self.part.exists())
        self.assertTrue(self.transfer());self.assertEqual(self.dest.read_bytes(),DATA)

    def test_valid_segment_can_resume_again_and_unknown_length_is_hash_checked(self):
        self.part.write_bytes(DATA[:7]);self.server.mode='segment'
        self.assertFalse(self.transfer());offset=self.part.stat().st_size
        self.assertEqual(offset,17007);self.assertEqual(self.part.read_bytes(),DATA[:offset])
        self.server.mode='good';self.assertTrue(self.transfer())
        self.dest.unlink();self.server.mode='no_length';self.assertTrue(self.transfer());self.assertEqual(self.dest.read_bytes(),DATA)


@unittest.skipUnless(os.environ.get('COOP_NATIVE_DOWNLOAD_PROBE') and (os.name=='nt' or os.environ.get('COOP_WINE_PREFIX')),'requires native probe and isolated Wine prefix on Linux')
class NativeDownloadHTTP(PythonDownloadHTTP):
    def transfer(self):
        exe=str(Path(os.environ['COOP_NATIVE_DOWNLOAD_PROBE']).resolve());dest=str(self.dest.resolve())
        env=os.environ.copy()
        if os.name=='nt':command=[exe,self.url,dest,SHA,str(len(DATA))]
        else:
            env.update(WINEPREFIX=str(Path(os.environ['COOP_WINE_PREFIX']).resolve()),WINEDEBUG='-all')
            command=['wine',exe,self.url,'Z:'+dest.replace('/','\\'),SHA,str(len(DATA))]
        run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=60)
        if run.returncode not in (0,1):raise AssertionError((run.returncode,run.stdout,run.stderr))
        return run.returncode==0


if __name__=='__main__':unittest.main()
