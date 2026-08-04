"""
Re-run SPEC v4 §16.2's direct-indexing vs pointer-table crossover sweep
against REAL zsdcc, replacing the stock-SDCC-4.2.0 stand-in the spec's
table was measured with.

Conditions mirror §16.2 as written: T-states, zsdcc-compiled C, a single
indexed field access, AoS.

Method: compile each variant, link at a known org, then measure the
access function in the `z80` emulator by raising ticks_to_stop until PC
reaches a NOP placed at the return address. run() only stops once the
in-flight instruction completes, so that minimum is (T_func + 1); the
trailing NOP is what makes the correction a constant instead of varying
with whatever the function's last instruction happens to be.
"""
import os
import re
import subprocess
import z80

BIN = "/home/claude/tools/zsdcc-src/sdcc/bin"
WORK = "/tmp/crossover"
CODE_LOC = 0x8000
RET_ADDR = 0x7000        # a NOP we place here; function returns into it
STACK = 0xDFF0

SIZES = [2, 8, 16, 21, 32, 64]


def make_source(size, mode):
    """A struct padded to exactly `size` bytes, an Instances array, and a
    parallel Registry of pointers into it. Both arrays are const so they
    land in ROM and need no crt0 initializer copy (--nostdlib)."""
    pad = size - 1
    pad_decl = f"    unsigned char pad[{pad}];\n" if pad > 0 else ""
    access = ("Instances[i].field" if mode == "direct" else "Registry[i]->field")
    return f"""
typedef struct {{
    unsigned char field;
{pad_decl}}} Item;

const Item Instances[4] = {{ {{1}}, {{2}}, {{3}}, {{4}} }};
const Item *const Registry[4] = {{
    &Instances[0], &Instances[1], &Instances[2], &Instances[3]
}};

unsigned char access(unsigned char i);
unsigned char access(unsigned char i) {{ return {access}; }}
"""


def build(size, mode):
    os.makedirs(WORK, exist_ok=True)
    stem = f"{mode}_{size}"
    c = os.path.join(WORK, stem + ".c")
    ihx = os.path.join(WORK, stem + ".ihx")
    binf = os.path.join(WORK, stem + ".bin")
    with open(c, "w") as fh:
        fh.write(make_source(size, mode))

    env = dict(os.environ, PATH=BIN + ":" + os.environ["PATH"])
    r = subprocess.run(
        ["sdcc", "-mz80", "--no-std-crt0", "--nostdlib",
         f"--code-loc", hex(CODE_LOC), "--data-loc", "0xC000",
         c, "-o", ihx],
        cwd=WORK, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"sdcc failed for {stem}:\n{r.stderr}")

    subprocess.run(["makebin", "-s", "65536", ihx, binf],
                   cwd=WORK, env=env, capture_output=True, text=True, check=True)

    # symbol address for _access out of the .map
    addr = None
    with open(os.path.join(WORK, stem + ".map")) as fh:
        for line in fh:
            m = re.search(r"([0-9A-Fa-f]{4})\s+_access\b", line)
            if m:
                addr = int(m.group(1), 16)
                break
    if addr is None:
        raise RuntimeError(f"no _access symbol in {stem}.map")
    return binf, addr


def measure(binf, entry, index=2):
    image = open(binf, "rb").read()
    for ticks in range(1, 4000):
        m = z80.Z80Machine()
        m.set_memory_block(0, image)
        m.set_memory_block(RET_ADDR, bytes([0x00]))   # trailing NOP
        # emulate a call: return address on top of stack, arg above it
        m.set_memory_block(STACK, bytes([RET_ADDR & 0xFF, RET_ADDR >> 8, index]))
        m.sp = STACK
        m.pc = entry
        m.ticks_to_stop = ticks
        m.run()
        if m.pc == RET_ADDR + 1:
            return ticks - 1, m.l
    return None, None


SPEC_TABLE = {2: (73, 114), 8: (95, 114), 16: (106, 114),
              21: (136, 114), 32: (117, 114), 64: (128, 114)}

print("SPEC §16.2 crossover sweep, re-measured against real zsdcc")
print(f"{'sizeof':>7} | {'direct':>18} | {'table':>18} | cheaper")
print(f"{'':>7} | {'real':>7} {'spec':>5} {'Δ':>4} | {'real':>7} {'spec':>5} {'Δ':>4} |")
print("-" * 70)

results = {}
for size in SIZES:
    row = {}
    for mode in ("direct", "table"):
        binf, entry = build(size, mode)
        t, ret = measure(binf, entry)
        row[mode] = t
        assert ret == 3, f"{mode}/{size}: wrong field value {ret}, expected 3"
    results[size] = row
    sd, st = SPEC_TABLE[size]
    cheaper = "direct" if row["direct"] < row["table"] else "table"
    print(f"{size:>7} | {row['direct']:>7} {sd:>5} {row['direct']-sd:>+4} |"
          f" {row['table']:>7} {st:>5} {row['table']-st:>+4} | {cheaper}")

print()
prev = None
for size in SIZES:
    c = "direct" if results[size]["direct"] < results[size]["table"] else "table"
    if prev and c != prev[1]:
        print(f"Crossover: between {prev[0]} and {size} bytes "
              f"({prev[1]} cheaper at {prev[0]}, {c} cheaper at {size}).")
    prev = (size, c)
