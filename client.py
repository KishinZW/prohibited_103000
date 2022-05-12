from genericpath import exists
import py7zr, os, json, hashlib, requests
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode as ub64e
from getpass import getpass

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
    (0x4E00, 0x9FA5),  # Chinese
    (0xAC00, 0xD7A3),  # Korean
]
SENSITIVES = {
    30775,
    23254,
    32911,
    23620,
    33068,
    33071,
    33105,
    33126,
    33125,
    33140,
    33144,
    33153,
    33155,
    33160,
    27695,
    20083,
    35273,
    24339,
    32925,
    32958,
    31348,
    33190,
    30967,
    32962,
    38090,
    38512,
    38452,
    24202,
    26538,
    35064,
    28139,
    39578,
    24361,
    20992,
    27696,
    27682,
    23014,
    14011,
    27686,
    38146,
    38093,
    30844,
    30899,
    27694,
    27687,
    27679,
    27670,
    38048,
    38209,
    38109,
    30789,
    30967,
    30827,
    27695,
    27689,
    38078,
    38041,
    38058,
    38043,
    38034,
    38124,
    38192,
    38081,
    38068,
    38221,
    38108,
    38156,
    38227,
    38167,
    30775,
    30802,
    28340,
    27690,
    38135,
    38198,
    38023,
    38150,
    38092,
    38076,
    38173,
    38028,
    38097,
    38063,
    38134,
    38217,
    38111,
    38177,
    38161,
    30898,
    30872,
    27673,
    38127,
    38049,
    38247,
    38088,
    38248,
    38071,
    38071,
    38032,
    38101,
    38022,
    38060,
    38237,
    38060,
    38098,
    38117,
    38257,
    38245,
    38122,
    38077,
    38056,
    38140,
    38151,
    38129,
    38082,
    37329,
    27742,
    38090,
    38085,
    38091,
    38027,
    30777,
    27681,
    38059,
    38253,
    38165,
    38029,
    38244,
    38080,
    38222,
    38042,
    38213,
    38164,
    38187,
    38158,
    38207,
    38212,
    38036,
    38168,
    38097,
}
NUMSYS_CHARSET = list(
    filter(
        lambda char: char.isprintable() and ord(char) not in SENSITIVES, 
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
HEADERS = {
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    'Accept-Encoding': "gzip, deflate, br",
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32',
    'Host': 'gitee.com',
    'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="101", "Microsoft Edge";v="101"',
    'sec-ch-ua-mobile': "?0",
    'sec-ch-ua-platform': "windows",
    'Sec-Fetch-Dest': "document",
    'Sec-Fetch-Mode': "navigate",
    'Sec-Fetch-Site': "none",
    'Sec-Fetch-User': "?1",
    'Upgrade-Insecure-Requests': '1'
}
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

resname = input("Please input resource name: ")
for h in hashpool:
    h.update(resname.encode('utf-8'))
digested_length = hex((len(resname) + offset) % HASHSIZE)[2:]
dirname = f'{digested_length}_{"_".join(map(lambda x: hex((int(x.hexdigest(), base=16) + offset) % HASHSIZE)[2:], hashpool))}'

print("fetching metadata...")
resp = requests.get('https://gitee.com/KishinZW/prohibited_103000/raw/master/metadata.json', headers=HEADERS)
cookies = resp.cookies
metadata = json.loads(resp.text)
res_info = json.loads(decoder.decrypt(metadata[dirname].encode('utf-8')).decode('utf-8'))

slices = res_info['slices']
with open("_tmp.7z", "wb") as f:
    for i in range(slices):
        print(f"fetching slice {i + 1}/{slices}...")
        resp = requests.get(
            f'https://gitee.com/KishinZW/prohibited_103000/raw/master/{dirname}/{i}.json', 
            headers=HEADERS, cookies=cookies
        )
        with open(f'{i}.7slice', 'wb') as target:
            for chunk in resp.json():
                hex_chunk = _33115_translate_hex(chunk)
                byte_list = []
                for j in range(2, len(hex_chunk), 2):
                    byte_list.append(int(hex_chunk[j:j + 2], base=16))
                target.write(bytes(byte_list))

        print(f"Extracting slice {i + 1}/{slices}...")
        with py7zr.SevenZipFile(f'{i}.7slice', 'r', password=password) as target:
            target.extractall()
        with open(f"{i}.slice", 'rb') as f2:
            plate = f2.read()
            dec_plate = decoder.decrypt(plate)
            f.write(dec_plate)

        os.remove(f'{i}.7slice')
        os.remove(f'{i}.slice')

print("Extracting merged 7zip...")
cnt_dir = os.getcwd()
os.mkdir(resname)
with py7zr.SevenZipFile("_tmp.7z", "r") as f:
    os.chdir(resname)
    f.extractall()

os.chdir(cnt_dir)
os.remove('_tmp.7z')
print("Success!")
