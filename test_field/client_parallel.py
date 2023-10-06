import os, json, hashlib, threading, traceback
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode as ub64e
from getpass import getpass
from time import time, sleep
from queue import Queue
from shutil import rmtree
from pip import main as install

NUMSYS_RANGES = [
    (32, 126),         # ASCII Printable
    (0x370, 0x377),    # Greek and Coptic below, for strange reasons in unicode
    (0x37A, 0x37F),
    (0x384, 0x38A),
    (0x38C, 0x38C),
    (0x38E, 0x3A1),
    (0x3A3, 0x3FF),
    (0x400, 0x4FF),    # Cyrillic
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3040, 0x3096),  # Hiragana
    (0x3099, 0x309F),  # Hiragana-Katakana
    (0x30A0, 0x30FF),  # Katakana
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
    # (0x4E00, 0x9FA5),  # Chinese
    (0xAC00, 0xD7A3),  # Korean
]
NUMSYS_CHARSET = list(
    filter(
        lambda char: char.isprintable(), 
        ''.join(
            map(
                lambda r: ''.join(
                    map(chr, range(r[0], r[1] + 1))
                ), 
                NUMSYS_RANGES
            )
        )
    )
)
NUMSYS_REVERSED_CHARSET = dict(
    map(
        lambda pair: (pair[1], pair[0]),
        enumerate(NUMSYS_CHARSET)
    )
)
NUMSYS_K = len(NUMSYS_CHARSET)
def _33115_translate_hex(num):
    ans = 0
    power = 1
    for char in num:
        ans += NUMSYS_REVERSED_CHARSET[char] * power
        power *= NUMSYS_K
    return hex(ans)[2:]

HASHSIZE = 1 << 224


THREAD_LOCK = threading.RLock()
def atomic_print(string):
    with THREAD_LOCK:
        print(string)

def fetch_and_extract(slice_num):
    print(f"fetching slice {slice_num + 1}/{slices}...")
    resp = requests.get(
        f'{accelerator}https://raw.githubusercontent.com/KishinZW/prohibited_103000/master/{dirname}/{slice_num}.json')
    while resp.status_code != 200:
        print(f"failed to fetch slice {slice_num + 1}/{slices}, waiting 2 secs for retrying...")
        sleep(2)
        print(f"fetching slice {slice_num + 1}/{slices}...")
        resp = requests.get(
            f'{accelerator}https://raw.githubusercontent.com/KishinZW/prohibited_103000/master/{dirname}/{slice_num}.json')
    print(f"fetched slice {slice_num + 1}/{slices}...")
    with open(f'{slice_num}.7slice', 'wb') as target:
        for chunk in resp.json():
            hex_chunk = _33115_translate_hex(chunk)
            byte_list = []
            for j in range(2, len(hex_chunk), 2):
                byte_list.append(int(hex_chunk[j:j + 2], base=16))
            target.write(bytes(byte_list))
    print(f"Extracting slice {slice_num + 1}/{slices}...")
    try:
        with py7zr.SevenZipFile(f'{slice_num}.7slice', 'r', password=password) as target:
            target.extractall()
    except:
        print(traceback.format_exc())
    os.remove(f'{slice_num}.7slice')
    print(f"Extracted slice {slice_num + 1}/{slices}.")


class LimitedThreadPool:
    def __init__(self):
        self.waitlist = Queue()
        self.workers = []
    
    def add(self, func, args: tuple):
        self.workers.append(threading.Thread(target=func, args=args))
    
    def start_running(self):
        for worker in self.workers:
            worker.start()
    
    def join(self):
        for worker in self.workers:
            worker.join()


password = getpass("Please input password")
if len(password) > 32:
    print("password is too long")
    exit()
decoder = Fernet(ub64e(password.zfill(32).encode('utf-8')))
hashpool = [hashlib.sha3_224(), hashlib.blake2b(digest_size=28)]
for h in hashpool:
    h.update(password.encode('utf-8'))
offset = sum(map(lambda h: int(h.hexdigest(), base=16), hashpool)) % HASHSIZE
hashpool = [hashlib.sha3_224(), hashlib.blake2b(digest_size=28)]


workdir = input("Please input the output directory: ")
os.chdir(workdir)
print(f"Working at: {os.getcwd()}")


resname = input("Please input resource name: ")
if os.path.exists(os.path.join(os.getcwd(), resname)):
    no_overwrite = input("Directory already exists. Overwrite (Y/n)? ") != 'Y'
    if no_overwrite:
        exit()
    else:
        rmtree(os.path.join(os.getcwd(), resname))
for h in hashpool:
    h.update(resname.encode('utf-8'))
digested_length = hex((len(resname) + offset) % HASHSIZE)[2:]
dirname = f'{digested_length}_{"_".join(map(lambda x: hex((int(x.hexdigest(), base=16) + offset) % HASHSIZE)[2:], hashpool))}'

accelerator = input("Please input proxy: ")


print('start timing...')
t1 = time()

print('installing required modules...')
THIRD_PARTY = ["requests", "py7zr", "click"]
THIRD_PARTY_MODULES = {}
for module in THIRD_PARTY:
    try:
        THIRD_PARTY_MODULES[module] = __import__(module)
    except:
        install(['install', '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple', module])
        THIRD_PARTY_MODULES[module] = __import__(module)
requests = THIRD_PARTY_MODULES['requests']
py7zr = THIRD_PARTY_MODULES['py7zr']

print("fetching metadata...")
resp = requests.get(f'{accelerator}https://raw.githubusercontent.com/KishinZW/prohibited_103000/master/metadata.json')
metadata = json.loads(resp.text)
res_info = json.loads(decoder.decrypt(metadata[dirname].encode('utf-8')).decode('utf-8'))

slices = res_info['slices']
thread_pool = LimitedThreadPool()
with open("_tmp.7z", "wb") as f:
    for i in range(slices):
        thread_pool.add(fetch_and_extract, (i,))
    thread_pool.start_running()
    thread_pool.join()
    print("Extracted all slices. Merging...")
    for i in range(slices):
        with open(f"{i}.slice", 'rb') as f2:
            plate = f2.read()
            dec_plate = decoder.decrypt(plate)
            f.write(dec_plate)
        os.remove(f"{i}.slice")

print("Extracting merged 7zip...")
cnt_dir = os.getcwd()
os.mkdir(resname)
with py7zr.SevenZipFile("_tmp.7z", "r") as f:
    os.chdir(resname)
    f.extractall()

os.chdir(cnt_dir)
os.remove('_tmp.7z')
print(f"Time used: {time() - t1}s")
print("Success!")
input("Press enter to exit...")
