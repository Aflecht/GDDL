# Getting Started

This page assumes you have already installed Python on your computer (following whatever instructions you used to do that), and nothing else. You don't need to know anything about Python itself.

## 1. Check Python actually works

Open a terminal. On Windows, that's **Command Prompt** or **PowerShell**; on Mac, that's **Terminal**. Type:

```
python3 --version
```

If that prints something like `Python 3.11.4`, you're set. Use `python3` in every command below.

**If instead you see an error** like "command not found" or "not recognized," try this instead:

```
python --version
```

This happens because Windows installs of Python often use the plain name `python` rather than `python3`, while Mac and Linux almost always use `python3`. Whichever command just printed a real version number is the one to use for everything below. If it was `python`, mentally replace every `python3` in this guide with `python`.

## 2. Get GDDL

Clone or download the source from [github.com/Aflecht/GDDL](https://github.com/Aflecht/GDDL). The `compiler-python` folder inside it is the compiler itself; nothing needs to be built.

## 3. Install the compiler

GDDL's compiler is a real installable Python package. Install it once, pointing at the `compiler-python` folder inside wherever you put GDDL:

```
python3 -m pip install -e /path/to/GDDL/compiler-python
```

(On Windows, the path looks more like `C:\path\to\GDDL\compiler-python`.)

The `-e` (editable) flag links the installed package back to your GDDL folder instead of copying it, so if you later update GDDL (`git pull`, or downloading a newer copy over the old one), the change takes effect immediately, no reinstall needed.

This is a one-time step. Once it's done, the five commands below work from any folder on your computer, not just from inside GDDL.

**If `pip install` prints a warning about scripts "not on PATH":** this is normal and doesn't mean the install failed. It means the `gddl-export-*` commands from step 5 won't be found by name until you either add the mentioned folder to your PATH, or use the `python3 -m gddl.export_cpp` form shown as a fallback in that step.

## 4. Set up a folder for your own game data

Create a separate folder for your own project, outside the `GDDL` folder.

Inside it, create `items.gddl`:

```gddl
define Item
	power = u16

Item Sword
	power = 42
```

## 5. Run the compiler

From a terminal in your project folder, run:

```
gddl-export-cpp items.gddl -o items_output
```

If it worked, you'll see:

```
wrote items_output.h and items_output.cpp
```

**If `gddl-export-cpp` isn't recognized** (see the PATH note in step 3), use this equivalent form instead, which always works once the install itself succeeded:

```
python3 -m gddl.export_cpp items.gddl -o items_output
```

`gddl-export-cpp` is one of five exporter commands, one per target:

- `gddl-export-cpp`: modern C++17
- `gddl-export-6502`: 6502 (ACME, KickAssembler, 64tass)
- `gddl-export-z80`: Z80 (SjASMPlus, z88dk)
- `gddl-export-68000`: 68000 (C89 via vbcc), for Amiga and Atari ST
- `gddl-export-binary`: a standalone binary data file your game loads at runtime

(For the `python3 -m` fallback form, swap in the matching module name: `gddl.export_6502`, `gddl.export_z80`, `gddl.export_68000`, `gddl.export_binary`.)

Each one accepts `--help` for its full flag list; they don't all accept the same flags. The language itself, everything you can actually write in a `.gddl` file, is documented in full in [`SPEC.md`](../SPEC.md).

## Troubleshooting

**"python3 is not recognized" (or "python" isn't either).** Python isn't actually installed correctly, or your terminal can't find it. This is a Python installation issue, not a GDDL one; revisit whatever instructions you used to install Python.

**"pip install" fails, or `pip` isn't recognized.** Some Python installs don't put `pip` on PATH by default. Try `python3 -m pip install -e /path/to/GDDL/compiler-python` (note `python3 -m pip`, not bare `pip`) exactly as shown in step 3; this works even when the plain `pip` command doesn't.

**"gddl-export-cpp is not recognized" (or any of the other four).** Either the install in step 3 hasn't been run yet, or the folder pip installs commands into isn't on your PATH (pip usually warns about this at install time). Use the `python3 -m gddl.export_cpp` fallback form shown in step 5, which doesn't depend on PATH at all.

**"No module named gddl."** The install in step 3 either wasn't run, or was run pointing at the wrong folder. Re-run `python3 -m pip install -e /path/to/GDDL/compiler-python`, double-checking the path actually points at the `compiler-python` folder (not the `GDDL` folder itself, and not some other location).

**"unrecognized arguments."** Different exporters accept different flags; not every flag shown in an example elsewhere applies to every exporter. Run the exporter you're using with `--help` to see exactly what it supports.
