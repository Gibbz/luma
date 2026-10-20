// SPDX-License-Identifier: Apache-2.0

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

#define PHOC "/usr/bin/phoc"
/* Device packages put output settings (scale, modes) here; phosh-session
 * prefers it too, so the greeter and the session it hands off to match. */
#define PHOC_INI_DEVICE "/etc/phosh/phoc.ini"
#define PHOC_INI "/usr/share/phosh/phoc.ini"

int main(void) {
  if (umask(0007) == (mode_t)-1) {
    perror("luma-presence-compositor: umask");
    return 1;
  }
  if (setenv("XDG_RUNTIME_DIR", "/run/luma-display", 1) != 0) {
    perror("luma-presence-compositor: setenv");
    return 1;
  }

  const char *ini = access(PHOC_INI_DEVICE, R_OK) == 0 ? PHOC_INI_DEVICE : PHOC_INI;

  execl(PHOC, "phoc", "--persistent", "--handoff-app-id",
        "org.projectluma.Greeter", "--socket", "wayland-0", "-S", "-C",
        ini, "-E", "/usr/libexec/luma-greeter-session",
        (char *)NULL);
  perror("luma-presence-compositor: exec phoc");
  return 127;
}
