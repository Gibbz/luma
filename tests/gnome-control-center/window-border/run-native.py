#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the production border writer and view using a matching Settings build."""
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys

if len(sys.argv) != 4:
    raise SystemExit("Usage: run-native.py PATCHED_SETTINGS_SOURCE MATCHING_BUILD OUTPUT")
source, build, output = (Path(value).resolve() for value in sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parents[3]
version = json.loads(subprocess.check_output(
    ["meson", "introspect", "--projectinfo", str(build)], text=True))["version"]
for key, value in {"RPM_ARCH": platform.machine(), "RPM_PACKAGE_NAME": "gnome-control-center",
                   "RPM_PACKAGE_VERSION": version, "RPM_PACKAGE_RELEASE": "native-check"}.items():
    os.environ.setdefault(key, value)

# Compile the focused test against the same native view objects and dependencies.
commands = subprocess.check_output(
    ["ninja", "-t", "commands", "shell/test-luma-view"], cwd=build, text=True).splitlines()
compile_command = next(shlex.split(command) for command in commands
                       if "../shell/test-luma-view.c" in command and " -c " in command)
compile_command[compile_command.index("-o") + 1] = str(output / "border-view.o")
compile_command[compile_command.index("-MF") + 1] = str(output / "border-view.d")
compile_command[compile_command.index("-c") + 1] = str(Path(__file__).with_name("test-native-view.c"))
subprocess.run(compile_command, cwd=build, check=True)
link_command = shlex.split(commands[-1])
link_command[link_command.index("-o") + 1] = str(output / "test-border-view")
link_command = [str(output / "border-view.o") if argument ==
                "shell/test-luma-view.p/test-luma-view.c.o" else argument for argument in link_command]
subprocess.run(link_command, cwd=build, check=True)

flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "gtk4", "json-glib-1.0", "gio-unix-2.0"], text=True))
qualification = repo / "tests/gnome-control-center/native-actions/qualification-tests"
subprocess.run(["gcc", "-g", "-O0", "-Wall", "-Wno-deprecated-declarations",
                "-I" + str(source / "shell"), str(qualification / "test-native-windows.c"),
                str(source / "shell/cc-luma-live-gsettings.c"),
                str(source / "shell/cc-luma-fixture.c"), "-o", str(output / "test-border-backend")]
               + flags + ["-lm"], check=True)
schemas = output / "data/gnome-shell/extensions/tilingshell@ferrarodomenico.com/schemas"
schemas.mkdir(parents=True, exist_ok=True)
xml = (qualification / "run.sh").read_text().split("<<'EOF'\n", 1)[1].split("\nEOF", 1)[0]
(schemas / "test.gschema.xml").write_text(xml)
subprocess.run(["glib-compile-schemas", "--strict", str(schemas)], check=True)
for name in ("config", "cache", "runtime"):
    (output / name).mkdir(mode=0o700, exist_ok=True)
os.environ.update(GSETTINGS_SCHEMA_DIR=str(schemas), GSETTINGS_BACKEND="memory",
                  XDG_DATA_HOME=str(output / "data"), XDG_CONFIG_HOME=str(output / "config"),
                  XDG_CACHE_HOME=str(output / "cache"), XDG_RUNTIME_DIR=str(output / "runtime"),
                  DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(output / "no-system-bus"),
                  G_DEBUG="fatal-warnings")
subprocess.run(["dbus-run-session", "--", str(output / "test-border-backend")], check=True)
os.environ.update(LUMA_SETTINGS_TEST_FIXTURE=str(repo / "tests/fixtures/settings-v70.json"),
                  LUMA_BORDER_TEST_OUT=str(output), G_DEBUG="fatal-criticals", GTK_A11Y="none",
                  GSK_RENDERER="cairo", GIO_USE_VFS="local")
os.environ.pop("WAYLAND_DISPLAY", None)
subprocess.run(["xvfb-run", "-a", "--server-args=-screen 0 1600x1200x24",
                "dbus-run-session", "--", str(output / "test-border-view")], check=True)
