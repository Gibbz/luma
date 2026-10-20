/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Reuse the production view suite's widget helpers and isolated artwork. */
#define main upstream_view_main
#include "test-luma-view.c"
#undef main

static void capture (GtkWidget *window, const char *name)
{
  const char *out = g_getenv ("LUMA_BORDER_TEST_OUT");
  if (!out) return;
  g_autoptr (GdkPaintable) paintable = gtk_widget_paintable_new (window);
  GtkSnapshot *snapshot = gtk_snapshot_new ();
  int width = gtk_widget_get_width (window), height = gtk_widget_get_height (window);
  gdk_paintable_snapshot (paintable, GDK_SNAPSHOT (snapshot), width, height);
  g_autoptr (GskRenderNode) node = gtk_snapshot_free_to_node (snapshot);
  graphene_rect_t bounds = GRAPHENE_RECT_INIT (0, 0, width, height);
  g_autoptr (GdkTexture) texture = gsk_renderer_render_texture (
    gtk_native_get_renderer (GTK_NATIVE (window)), node, &bounds);
  g_autofree char *path = g_build_filename (out, name, NULL);
  g_assert_true (gdk_texture_save_to_png (texture, path));
}

static void border_controls (void)
{
  g_autofree char *dir = asset_fixture ();
  g_autofree char *json = g_build_filename (dir, "settings.json", NULL);
  g_autoptr (CcLumaFixture) assets = cc_luma_fixture_load (json, NULL);
  JsonObject *wifi = json_object_get_object_member (cc_luma_fixture_get_data (assets), "CFWIFI");
  const char *art = json_object_get_string_member (json_object_get_object_member (wifi, "share_codes"), "Studio North");
  const char *files[] = {"prism.png", "luma-v3-documents.svg", "luma-v3-browser.svg", "luma-v3-messages.svg"};
  for (guint i = 0; i < G_N_ELEMENTS (files); i++)
    {
      g_autofree char *path = g_build_filename (dir, files[i], NULL);
      g_assert_true (g_file_set_contents (path, art, -1, NULL));
    }
  const int widths[] = {1180, 390};
  for (guint i = 0; i < G_N_ELEMENTS (widths); i++)
    {
      g_autoptr (CcLumaFixture) model = cc_luma_fixture_load (json, NULL);
      JsonObject *settings = cc_luma_fixture_get_settings (model);
      json_object_set_boolean_member (settings, "windowBorder", TRUE);
      json_object_set_int_member (settings, "windowBorderSize", 14);
      cc_luma_fixture_publish_boolean (model, "tile", TRUE);
      json_object_set_boolean_member (settings, "resizeTogether", FALSE);
      GtkWidget *window = gtk_window_new ();
      GtkWidget *view = cc_luma_view_new (model, "windows", NULL);
      g_assert_nonnull (view);
      gtk_window_set_child (GTK_WINDOW (window), view);
      luma_layer_host_install (GTK_WINDOW (window));
      gtk_window_set_default_size (GTK_WINDOW (window), widths[i], 900);
      gtk_window_present (GTK_WINDOW (window));
      wait_ms (200);
      g_assert_true (has_text (view, "Leave space around maximized windows"));
      GtkWidget *range = find_name (view, "cf-windowBorderSize");
      g_assert_true (GTK_IS_RANGE (range));
      capture (window, i ? "border-phone.png" : "border-desktop.png");
      g_assert_cmpint (gtk_widget_get_width (range), >=, 96);
      g_assert_true (gtk_widget_is_sensitive (range));
      g_assert_cmpfloat (gtk_range_get_value (GTK_RANGE (range)), ==, 14);
      gtk_range_set_value (GTK_RANGE (range), 32);
      drain ();
      g_assert_true (has_text (view, "32 px"));
      g_assert_true (range == find_name (view, "cf-windowBorderSize"));
      GtkWidget *gap_range = find_name (view, "cf-gap");
      g_assert_true (GTK_IS_RANGE (gap_range));
      g_assert_cmpint (gtk_range_get_round_digits (GTK_RANGE (range)), ==, 0);
      g_assert_cmpint (gtk_range_get_round_digits (GTK_RANGE (gap_range)), ==, 0);
      gboolean handled = FALSE;
      g_signal_emit_by_name (gap_range, "change-value", GTK_SCROLL_JUMP, 4.6, &handled);
      g_assert_cmpfloat (gtk_range_get_value (GTK_RANGE (gap_range)), ==, 5);
      drain ();
      g_assert_cmpint (json_node_get_int (cc_luma_fixture_get (model, "gap")), ==, 5);
      for (int gap = 0; gap <= 24; gap++)
        {
          gtk_range_set_value (GTK_RANGE (gap_range), gap);
          wait_ms (20);
          g_assert_true (gap_range == find_name (view, "cf-gap"));
          g_assert_cmpint (json_node_get_int (cc_luma_fixture_get (model, "gap")), ==, gap);
          g_assert_cmpfloat (gtk_range_get_value (GTK_RANGE (gap_range)), ==, gap);
        }
      g_assert_true (has_text (view, "Resize neighboring tiles together"));
      set_switch (find_name (view, "cf-windowBorder"), FALSE);
      wait_ms (100);
      range = find_name (view, "cf-windowBorderSize");
      g_assert_false (gtk_widget_is_sensitive (range));
      g_assert_cmpfloat (gtk_range_get_value (GTK_RANGE (range)), ==, 32);
      set_switch (find_name (view, "cf-windowBorder"), TRUE);
      wait_ms (100);
      range = find_name (view, "cf-windowBorderSize");
      g_assert_true (gtk_widget_is_sensitive (range));
      g_assert_cmpfloat (gtk_range_get_value (GTK_RANGE (range)), ==, 32);
      g_assert_cmpfloat (gtk_widget_get_width (window), ==, widths[i]);
      g_assert_null (cc_luma_view_get_error (view));
      capture (window, i ? "border-phone.png" : "border-desktop.png");
      gpointer weak_view = view;
      g_object_add_weak_pointer (G_OBJECT (view), &weak_view);
      gtk_window_destroy (GTK_WINDOW (window));
      wait_ms (100);
      g_assert_null (weak_view);
    }
  for (guint i = 1; i < G_N_ELEMENTS (files); i++)
    {
      g_autofree char *path = g_build_filename (dir, files[i], NULL);
      g_assert_cmpint (g_remove (path), ==, 0);
    }
  remove_asset_fixture (dir);
}

static void add_device (JsonArray *devices, const char *id, const char *name)
{
  JsonObject *device = json_object_new ();
  json_object_set_string_member (device, "id", id);
  json_object_set_string_member (device, "n", name);
  json_object_set_string_member (device, "i", "bluetooth");
  json_object_set_string_member (device, "kind", "Headphones");
  json_array_add_object_element (devices, device);
}

static void bluetooth_discovery (void)
{
  g_autoptr (CcLumaFixture) model = load ();
  cc_luma_fixture_publish_boolean (model, "bt", TRUE);
  JsonArray *devices = json_array_new ();
  add_device (devices, "hash", "AA:BB:CC:DD:EE:FF");
  add_device (devices, "device-airpods", "AirPods");
  add_device (devices, "device-keyboard", "Keyboard");
  json_object_set_array_member (cc_luma_fixture_get_data (model), "CFNEAR", devices);
  g_setenv ("LUMA_SETTINGS_NEAR", "30", TRUE);
  GtkWidget *window = gtk_window_new ();
  GtkWidget *view = cc_luma_view_new (model, "bluetooth", NULL);
  View *v = g_object_get_data (G_OBJECT (view), "cf-view");
  v->near_count = 30;
  cc_luma_view_queue_refresh (v);
  gtk_window_set_child (GTK_WINDOW (window), view);
  luma_layer_host_install (GTK_WINDOW (window));
  gtk_window_set_default_size (GTK_WINDOW (window), 1180, 900);
  gtk_window_present (GTK_WINDOW (window));
  wait_ms (150);
  GtkWidget *list = find_name (view, "cf-bt-nearby");
  GtkWidget *airpods = find_name (view, "cf-pair-device-airpods");
  GtkWidget *keyboard = find_name (view, "cf-pair-device-keyboard");
  GtkWidget *hash = find_name (view, "cf-pair-hash");
  g_assert_nonnull (list);
  g_assert_nonnull (airpods);
  g_assert_nonnull (keyboard);
  g_assert_nonnull (hash);
  g_assert_true (gtk_widget_get_next_sibling (airpods) == keyboard);
  g_assert_true (gtk_widget_get_first_child (list) != hash);
  g_assert_true (has_text (list, "Nearby devices"));
  g_assert_true (gtk_widget_get_next_sibling (keyboard) != hash);
  GtkWidget *search = find_name (view, "cf-bt-search");
  gtk_editable_set_text (GTK_EDITABLE (search), "airp");
  wait_ms (250);
  g_assert_true (gtk_widget_get_visible (airpods));
  g_assert_false (gtk_widget_get_visible (keyboard));
  gtk_widget_grab_focus (search);
  add_device (devices, "device-speaker", "Speaker");
  cc_luma_view_queue_refresh (v);
  wait_ms (150);
  g_assert_true (search == find_name (view, "cf-bt-search"));
  g_assert_cmpstr (gtk_editable_get_text (GTK_EDITABLE (search)), ==, "airp");
  g_assert_true (airpods == find_name (view, "cf-pair-device-airpods"));
  g_assert_false (gtk_widget_get_visible (find_name (view, "cf-pair-device-speaker")));
  gtk_editable_set_text (GTK_EDITABLE (search), "");
  wait_ms (250);
  g_assert_true (gtk_widget_get_next_sibling (airpods) == keyboard);
  g_assert_true (gtk_widget_get_next_sibling (keyboard) == find_name (view, "cf-pair-device-speaker"));
  capture (window, "bluetooth-desktop.png");
  gtk_window_destroy (GTK_WINDOW (window));
  wait_ms (100);
  g_unsetenv ("LUMA_SETTINGS_NEAR");
}

int main (int argc, char **argv)
{
  g_test_init (&argc, &argv, NULL);
  gtk_init ();
  load_settings_style ();
  g_test_add_func ("/settings/view/window-border", border_controls);
  g_test_add_func ("/settings/view/bluetooth-discovery", bluetooth_discovery);
  return g_test_run ();
}
