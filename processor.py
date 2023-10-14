import py7zr, os, json, hashlib
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode as ub64e
from getpass import getpass
from shutil import rmtree

AUTO_UPLOAD = False
def auto_upload():
    AUTO_UPLOAD = input('Auto upload? [Y/n] ') == 'Y'
    print('Uploading to GitHub...')
    failed = True
    while failed:
        err_code = os.system('git push github master')
        if err_code:
            if AUTO_UPLOAD:
                print("Failed to upload due to GitHub's instability, retrying...")
            else:
                print("Error occured while uploading. Probably not using git fetch?")
                input("Please try git fetch somewhere else. Press enter to retry.")
        else:
            failed = False
    print("Success! Modification has been synchronized.")
    exit()

if input("Directly jump to upload phase? [Y/n] ") == 'Y':
    auto_upload()

BACKSLASH = '\\'
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
NUMSYS_K = len(NUMSYS_CHARSET)
PARTICLE_LIMIT = 128
def hex_translate_33115(num):
    num = int(num, base=16)
    ans = []
    while num != 0:
        num, rem = divmod(num, NUMSYS_K)
        ans.append(NUMSYS_CHARSET[rem])
    return ''.join(ans)

password = getpass("Please input password")
if len(password) > 32:
    print("password is too long")
    exit()

encoder = Fernet(ub64e(password.zfill(32).encode('utf-8')))
LIMIT = 200 * 1024
HASHSIZE = 1 << 224
hashpool = [hashlib.sha3_224(), hashlib.blake2b(digest_size=28)]
for h in hashpool:
    h.update(password.encode('utf-8'))
offset = sum(map(lambda h: int(h.hexdigest(), base=16), hashpool)) % HASHSIZE
hashpool = [hashlib.sha3_224(), hashlib.blake2b(digest_size=28)]

is_directory = input("Directory (Y/n)? ") == "Y"
resname = input(f"Please input {'directory' if is_directory else 'file'}: ")
absname = resname

resname = os.path.split(resname)[-1]
for h in hashpool:
    h.update(resname.encode('utf-8'))
digested_length = hex((len(resname) + offset) % HASHSIZE)[2:]
dirname = f'{digested_length}_{"_".join(map(lambda x: hex((int(x.hexdigest(), base=16) + offset) % HASHSIZE)[2:], hashpool))}'
if os.path.exists(dirname):
    no_overwrite = input("Directory already exists. Overwrite (Y/n)? ") != 'Y'
    if no_overwrite:
        exit()
    else:
        rmtree(dirname)

cnt_dir = os.getcwd()
if is_directory:
    os.chdir(absname)
print("Zipping 7z...")
if is_directory:
    with py7zr.SevenZipFile(f'{cnt_dir}{BACKSLASH}_tmp.7z', 'w') as target:
        for root, _, i in os.walk('.'):
            for n in i:
                target.write('\\'.join((root, n)))
else:
    with py7zr.SevenZipFile('_tmp.7z', 'w') as target:
        target.write(resname);

os.chdir(cnt_dir)
print("Slicing...")
with open('_tmp.7z', 'rb') as f:
    if not os.path.exists(dirname):
        os.mkdir(dirname)
    os.chdir(dirname)
    counter = 0
    plate = f.read(LIMIT)
    while plate != b'':
        print(f"Sliced: {counter}.slice")
        with open(f"{counter}.slice", 'wb') as f2:
            enc_plate = encoder.encrypt(plate)
            f2.write(enc_plate)
        with py7zr.SevenZipFile(f"{counter}.7slice", "w", password=password) as target:
            target.write(f"{counter}.slice")
        print(f"Packing {counter}.7slice...")
        with open(f"{counter}.7slice", 'rb') as f2:
            hashlike_list = []
            particle = f2.read(PARTICLE_LIMIT)
            while particle != b'':
                hex_expr = f"ff{''.join(map(lambda i: hex(i)[2:].rjust(2, '0'), particle))}"
                hashlike_list.append(hex_translate_33115(hex_expr))
                particle = f2.read(64)
        with open(f"{counter}.json", 'w', encoding='utf-8') as f2:
            json.dump(hashlike_list, f2, ensure_ascii=False)
        os.remove(f"{counter}.slice")
        os.remove(f"{counter}.7slice")
        plate = f.read(LIMIT)
        counter += 1;

print("Writing to metadata...")
os.chdir('..')
os.remove('_tmp.7z')
metadata = {}
if os.path.exists("metadata.json"):
    with open("metadata.json", 'r') as f:
        metadata = json.load(f)
header = {"slices": counter, "is_directory": is_directory}
metadata[dirname] = encoder.encrypt(json.dumps(header).encode('utf-8')).decode('utf-8')
with open("metadata.json", 'w') as f:
    json.dump(metadata, f)

print("commiting to local git...")
os.system("git add .")
os.system('git commit -m "auto commit"')
no_upload = input("Everything has been prepared. Upload (Y/n)?") != 'Y'
if no_upload:
    exit()
auto_upload()
