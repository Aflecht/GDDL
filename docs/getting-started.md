# Getting Started

This page assumes you have already installed Python on your computer (following whatever instructions you used to do that), and nothing else. You don't need to know anything about Python itself. GDDL's compiler is a plain Python program with no extra pieces to install, so once Python itself is working, everything below is just typing commands.

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

## 3. Set up a folder for your own game data

Create a separate folder for your own project, outside the `GDDL` folder.

Inside it, create `items.gddl`:

```gddl
define Item
	power = u16

Item Sword
	power = 42
```

## 4. Run the compiler

From a terminal in your project folder, run:

```
python3 /path/to/GDDL/compiler-python/gddl/export_cpp.py items.gddl -o items_output
```

(On Windows, the path looks more like `C:\path\to\GDDL\compiler-python\gddl\export_cpp.py`.)

If it worked, you'll see:

```
wrote items_output.h and items_output.cpp
```

`export_cpp.py` is one of five exporters, one per target, all living in the same `compiler-python/gddl/` folder:

- `export_cpp.py`: modern C++17
- `export_6502.py`: 6502 (ACME, KickAssembler, 64tass)
- `export_z80.py`: Z80 (SjASMPlus, z88dk)
- `export_68000.py`: 68000 (C89 via vbcc), for Amiga and Atari ST
- `export_binary.py`: a standalone binary data file your game loads at runtime

Each one accepts `--help` for its full flag list; they don't all accept the same flags. The language itself, everything you can actually write in a `.gddl` file, is documented in full in [`SPEC.md`](../SPEC.md).

## Troubleshooting

**"python3 is not recognized" (or "python" isn't either).** Python isn't actually installed correctly, or your terminal can't find it. This is a Python installation issue, not a GDDL one; revisit whatever instructions you used to install Python.

**"can't open file '...export_cpp.py': No such file or directory."** The path you typed to `export_cpp.py` doesn't match where you actually put GDDL. Double-check the path, especially on Windows, where backslashes (`\`) are used instead of forward slashes (`/`).

**"unrecognized arguments."** Different exporters accept different flags; not every flag shown in an example elsewhere applies to every exporter. Run the exporter you're using with `--help` to see exactly what it supports.
