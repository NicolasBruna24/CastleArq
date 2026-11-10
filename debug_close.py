import threading
import time
import sys
sys.path.insert(0, '.')
from castlearq.chat import OpenVINOChatSession
from tests.test_openvino_chat_session import BlockingService

blocker = threading.Event()
svc = BlockingService(blocker)
s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)

assert svc.close_calls == 0

def worker():
    print('worker: entering send', flush=True)
    try:
        s.send("blocked")
    finally:
        print('worker: send done', flush=True)

t = threading.Thread(target=worker)
t.start()
time.sleep(0.5)
print('main: about to call close()', flush=True)
t0 = time.time()
s.close()
print('main: close() returned after %.2fs close_calls=%d' % (time.time() - t0, svc.close_calls), flush=True)
blocker.set()
t.join(timeout=8)
print('after join alive=%s close=%d calls=%d' % (t.is_alive(), svc.close_calls, len(svc.calls)), flush=True)
