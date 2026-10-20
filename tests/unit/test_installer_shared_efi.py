# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise native initial-deployment policy against a real OSTree repository."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scripts/install/atlas-iso"
spec = importlib.util.spec_from_file_location("runtime_anaconda", HERE / "prepare-runtime-anaconda.py")
PATCH = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PATCH)
UPSTREAM = (HERE / "upstream/anaconda-ostree-installation-44.30.py").read_bytes()


class InitialEFIDeployment(unittest.TestCase):
    def exercise(self, *, efi=True, policy=None, failure=False, patched=True):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "ostree/repo"
            repo.parent.mkdir()
            subprocess.run(["ostree", "init", "--repo=" + str(repo), "--mode=bare-user"], check=True)
            config = ["config", "--repo=" + str(repo)]
            if policy is not None:
                subprocess.run(["ostree", *config, "set", "sysroot.bootloader", policy], check=True)
            # Represent the existing vendor configuration outside Luma's boot
            # directory. The real VM covers actual EFI discovery and deployment.
            ubuntu = Path(directory) / "boot/efi/EFI/ubuntu/grub.cfg"
            ubuntu.parent.mkdir(parents=True)
            ubuntu.write_text("Ubuntu vendor config must survive\n")
            calls, deployment_policies = [], []
            def execute(command, args, **kwargs):
                calls.append(list(args))
                if args[0] == "admin":
                    if "deploy" in args:
                        value = subprocess.run(["ostree", *config, "get", "sysroot.bootloader"],
                                               capture_output=True, text=True)
                        current = value.stdout.strip() if value.returncode == 0 else "auto"
                        deployment_policies.append(current)
                        if failure or efi and current != "none":
                            return 1, "grub2-probe: cannot find a device for /"
                    return 0, ""
                result = subprocess.run([command, *args], capture_output=True, text=True)
                return result.returncode, result.stdout
            class Task:
                def report_progress(self, message):
                    pass
            tree = ast.parse(PATCH.patched_pull_source(UPSTREAM).decode() if patched else UPSTREAM.decode())
            tree.body = [node for node in tree.body if getattr(node, "name", "") in
                         ("safe_exec_program", "_luma_initial_efi_deploy", "DeployOSTreeTask")]
            namespace = dict(Task=Task, STORAGE=SimpleNamespace(get_proxy=lambda _: SimpleNamespace(IsEFI=lambda: efi)),
                             BOOTLOADER="bootloader", execProgram=execute, PayloadInstallationError=RuntimeError,
                             _=lambda text: text, _get_ref=lambda _: "test/ref", _get_stateroot=lambda _: "luma",
                             arch=SimpleNamespace(is_s390=lambda: False), log=SimpleNamespace(info=lambda *a: None))
            exec(compile(tree, "native-initial-deploy", "exec"), namespace)
            task = namespace["DeployOSTreeTask"](SimpleNamespace(is_container=lambda: False, remote="luma"), directory)
            error = None
            try:
                task.run()
            except RuntimeError as exc:
                error = exc
            after = subprocess.run(["ostree", *config, "get", "sysroot.bootloader"], capture_output=True, text=True)
            self.assertEqual(after.returncode, 1 if policy is None else 0)
            if policy is not None:
                self.assertEqual(after.stdout.strip(), policy)
            self.assertEqual(ubuntu.read_text(), "Ubuntu vendor config must survive\n")
            return error, deployment_policies, calls

    def test_native_initial_efi_deploy_defers_probe_and_restores_absent_policy(self):
        old, _, _ = self.exercise(patched=False)
        self.assertIn("grub2-probe", str(old))
        error, policies, _ = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(policies, ["none"])

    def test_explicit_policies_are_restored_even_when_deployment_fails(self):
        for policy in (None, "auto", "grub2", "none"):
            with self.subTest(policy=policy):
                error, policies, _ = self.exercise(policy=policy, failure=True)
                self.assertIn("grub2-probe", str(error))
                self.assertEqual(policies, ["none"])

    def test_bios_and_explicit_none_do_not_change_bootloader_policy(self):
        for options in ({"efi": False}, {"policy": "none"}):
            error, _, calls = self.exercise(**options)
            self.assertIsNone(error)
            self.assertFalse(any("set" in call and "sysroot.bootloader" in call for call in calls))


if __name__ == "__main__":
    unittest.main()
