#define _GNU_SOURCE
#define HAVE_LIBARCHIVE 1
#include <gio/gio.h>
#include <glib/gstdio.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdarg.h>
#include <archive.h>
#include <archive_entry.h>
static gboolean glnx_throw(GError **e, const char *fmt, ...) { va_list ap; va_start(ap,fmt); char *msg=g_strdup_vprintf(fmt,ap); va_end(ap); g_set_error_literal(e,G_IO_ERROR,G_IO_ERROR_FAILED,msg); g_free(msg); return FALSE; }
static gboolean glnx_throw_errno_prefix(GError **e, const char *msg) { g_set_error(e,G_IO_ERROR,g_io_error_from_errno(errno),"%s: %s",msg,g_strerror(errno)); return FALSE; }
static gboolean
aboot_safe_absolute_path (const char *path)
{
  if (!path || path[0] != '/' || path[1] == '\0') return FALSE;
  g_auto (GStrv) parts = g_strsplit (path + 1, "/", -1);
  for (char **part = parts; *part; part++)
    if (!**part || g_str_equal (*part, ".") || g_str_equal (*part, "..")) return FALSE;
  return TRUE;
}

static char *
aboot_bls_host_path (const char *sysroot, const char *path)
{
  /* BLS paths may include /boot when OSTree's bootprefix is enabled. */
  return g_build_filename (sysroot, g_str_has_prefix (path, "/boot/") ? "" : "boot",
                           path, NULL);
}

/* rpm-ostree appends its tracked-/etc cpio as the final BLS overlay. Check
 * the actual archive, not a sibling /etc file or an unbound status list. */
static gboolean
aboot_verify_recipient_overlay (const char *sysroot, const char *deployment,
                                 char **overlays, GError **error)
{
  g_autofree char *expected_path = g_build_filename (
      deployment, "usr/lib/luma/fp6-firmware-manifest.sha256", NULL);
  struct stat st;
  if (lstat (expected_path, &st) < 0)
    {
      if (errno == ENOENT) return TRUE; /* Generic aboot; FP6 deploy guard requires it. */
      return glnx_throw_errno_prefix (error, "aboot: firmware requirement");
    }
  if (!S_ISREG (st.st_mode) || st.st_size != 65)
    return glnx_throw (error, "aboot: invalid immutable firmware requirement");
  g_autofree char *expected = NULL;
  gsize expected_size = 0;
  if (!g_file_get_contents (expected_path, &expected, &expected_size, error)) return FALSE;
  if (expected_size != 65 || expected[64] != '\n')
    return glnx_throw (error, "aboot: invalid firmware digest encoding");
  for (int i = 0; i < 64; i++)
    if (!(g_ascii_isdigit (expected[i]) || (expected[i] >= 'a' && expected[i] <= 'f')))
      return glnx_throw (error, "aboot: invalid firmware digest");
  if (!overlays || !*overlays)
    return glnx_throw (error, "aboot: recipient firmware requires tracked initrd overlay");
#ifndef HAVE_LIBARCHIVE
  return glnx_throw (error, "aboot: firmware overlay validation requires libarchive");
#else
  g_autofree char *path = aboot_bls_host_path (sysroot, overlays[g_strv_length (overlays) - 1]);
  struct archive *archive = archive_read_new ();
  if (!archive) return glnx_throw (error, "aboot: cannot allocate archive reader");
  archive_read_support_filter_all (archive);
  archive_read_support_format_cpio (archive);
  gboolean valid = FALSE;
  guint anchors = 0;
  if (archive_read_open_filename (archive, path, 65536) != ARCHIVE_OK) goto out;
  struct archive_entry *entry;
  int status;
  while ((status = archive_read_next_header (archive, &entry)) == ARCHIVE_OK)
    {
      const char *name = archive_entry_pathname (entry);
      if (!name || name[0] == '/') goto out;
      const char *relative = g_str_has_prefix (name, "./") ? name + 2 : name;
      if (strstr (relative, "../") || g_str_has_suffix (relative, "/..")
          || strstr (relative, "//") || strstr (relative, "/./")) goto out;
      if (g_str_equal (name, "etc/luma-fp6-firmware-manifest.sha256")
          || g_str_equal (name, "./etc/luma-fp6-firmware-manifest.sha256"))
        {
          if (++anchors != 1 || archive_entry_filetype (entry) != AE_IFREG
              || archive_entry_uid (entry) != 0 || archive_entry_gid (entry) != 0
              || archive_entry_perm (entry) != 0644 || archive_entry_size (entry) != 65
              || archive_entry_hardlink (entry) || archive_entry_symlink (entry)) goto out;
          char data[66];
          size_t total = 0;
          while (total < 65)
            {
              la_ssize_t bytes = archive_read_data (archive, data + total, 65 - total);
              if (bytes <= 0) goto out;
              total += bytes;
            }
          if (memcmp (data, expected, 65) != 0 || archive_read_data (archive, data, 1) != 0)
            goto out;
        }
      else if (archive_read_data_skip (archive) != ARCHIVE_OK) goto out;
    }
  valid = status == ARCHIVE_EOF && anchors == 1;
 out:
  if (archive_read_close (archive) != ARCHIVE_OK) valid = FALSE;
  archive_read_free (archive);
  if (!valid) return glnx_throw (error, "aboot: final tracked initrd lacks the exact recipient firmware anchor");
  return TRUE;
#endif
}

int main(int argc,char **argv) { if(argc<3)return 2; for(int i=3;i<argc;i++)if(!aboot_safe_absolute_path(argv[i]))return 1; GError *error=NULL; if(!aboot_verify_recipient_overlay(argv[1],argv[2],argv+3,&error)){g_printerr("%s\n",error->message);g_error_free(error);return 1;}return 0; }
