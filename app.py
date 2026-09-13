"""
Kalla Aspal - LPSE Monitor: Phase 1-4 + partial Phase 3/5/6/7 prototype.

A local-first Streamlit app for admin staff to check LPSE/SPSE tender
listings for new road-construction packages, twice a day.

Run with:  streamlit run app.py
(see README.md for full Windows setup instructions, or double-click
run_app.bat, which does this for you)

This app deliberately keeps TWO separate datasets/flows, per project
decision (see PROJECT_STATUS.md "2026-09-13" entry for why):

  1. "Cek Tender (Daftar Lengkap)" - the full /lelang tender list for the
     year (every status: open, closed, failed, ...). No deadline date.
  2. "Ringkasan Beranda"           - the region homepage's Tender / Non
     Tender summary, which DOES carry a registration deadline
     ("Akhir Pendaftaran") but only for what the homepage currently shows.

They use different scraper modules, different database tables, different
services, and different tabs below - never mixed together. The Excel tab
mirrors this split too: each dataset has its own file/sheet/column
configuration and exports independently (see services/excel_service.py).

Ordering convention used everywhere in this app: relevant packages are
listed EARLIEST first, LATEST last, using Package ID (Kode Lelang) as a
stand-in for upload order (see database/database.py's
_CHRONOLOGICAL_ORDER_SQL comment for why). Filtering/sorting controls in
each tab operate on top of that base order - see services/filter_service.py.
"""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

from database import database as db
from scraper.lpse_scraper import build_lelang_url
from scraper.lpse_homepage_scraper import build_homepage_url
from services.comparison_service import run_scrape_and_compare
from services.homepage_service import run_homepage_scrape_and_compare
from services import filter_service, calendar_service, excel_service
from ui import branding

st.set_page_config(**branding.PAGE_CONFIG_KWARGS)

db.init_db()
branding.inject_css()


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def format_rupiah(value) -> str:
    if value is None:
        return "-"
    return "Rp " + f"{value:,.0f}".replace(",", ".")


def latest_timestamp(*candidates) -> str:
    """Pick the most recent (max) of several possibly-None ISO timestamps,
    for display in the top metrics row."""
    valid = [c for c in candidates if c]
    return max(valid) if valid else None


def render_filter_controls(rows, key_prefix, status_field, status_label, kategori_field=None, kategori_label=None):
    """Shared filter/sort UI for both dataset tabs. Returns the FILTERED +
    SORTED rows, ready to display - the HPS sum shown next to it always
    comes from this same returned list so it recalculates with whatever
    filter is active."""
    wilayah_options = filter_service.distinct_values(rows, "region_identifier")
    status_options = filter_service.distinct_values(rows, status_field)
    kategori_options = filter_service.distinct_values(rows, kategori_field) if kategori_field else []

    n_cols = 4 if kategori_field else 3
    cols = st.columns(n_cols)
    wilayah_sel = cols[0].multiselect("Filter Wilayah", wilayah_options, key=f"{key_prefix}_f_wilayah")
    status_sel = cols[1].multiselect(f"Filter {status_label}", status_options, key=f"{key_prefix}_f_status")
    kategori_sel = None
    idx = 2
    if kategori_field:
        kategori_sel = cols[2].multiselect(f"Filter {kategori_label}", kategori_options, key=f"{key_prefix}_f_kategori")
        idx = 3
    sort_label = cols[idx].selectbox(
        "Urutkan", list(filter_service.SORT_OPTIONS.keys()), key=f"{key_prefix}_sort",
    )

    filtered = filter_service.filter_rows(
        rows, wilayah=wilayah_sel or None, status=status_sel or None, kategori=kategori_sel or None,
        status_field=status_field, kategori_field=kategori_field or "kategori",
    )
    sorted_rows = filter_service.sort_rows(filtered, sort_label)

    m1, m2 = st.columns(2)
    m1.metric("Jumlah Paket (sesuai filter)", len(sorted_rows))
    m2.metric("Total HPS (sesuai filter)", format_rupiah(filter_service.sum_hps(sorted_rows)))

    return sorted_rows


def render_result_banner(result_state, new_label):
    """Shared "N PAKET BARU DITEMUKAN" banner + region-by-region status
    block, used by both the Daftar Lengkap and Ringkasan Beranda check
    buttons - they render identically up to this point, then each tab
    displays its own new/updated package cards (different fields per
    package, so that part stays inline in each tab)."""
    for rr in result_state["region_results"]:
        if not rr["success"]:
            with st.expander(f"⚠️ Gagal mengambil data dari LPSE {rr['region_identifier']}."):
                st.error(rr["error_message"])
        else:
            st.caption(
                f"{rr['region_identifier']}: {rr['total_found']} paket ditemukan, "
                f"{rr['relevant_found']} relevan (terkait jalan)."
            )

    new_count = len(result_state["new"])
    if new_count > 0:
        st.success(f"## {new_count} {new_label}")
    else:
        st.info(f"## TIDAK ADA {new_label}")

    return result_state["new"], result_state["updated"]


# ---------------------------------------------------------------------------
# Dashboard header
# ---------------------------------------------------------------------------

branding.render_header()

with db.connect() as conn:
    active_regions = db.get_active_regions(conn)
    relevant_total = len(db.get_relevant_packages(conn))
    relevant_homepage_total = len(db.get_relevant_homepage_packages(conn))
    last_run = db.get_last_completed_run(conn)
    last_homepage_run = db.get_last_completed_homepage_run(conn)

last_check = latest_timestamp(
    last_run["finished_at"] if last_run else None,
    last_homepage_run["finished_at"] if last_homepage_run else None,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Terakhir Cek", last_check[:16].replace("T", " ") if last_check else "Belum pernah")
col2.metric("Wilayah Aktif", len(active_regions))
col3.metric("Paket Relevan - Daftar Lengkap", relevant_total)
col4.metric("Paket Relevan - Ringkasan Beranda", relevant_homepage_total)

if not active_regions:
    st.warning(
        "Belum ada wilayah LPSE yang aktif. Buka tab **Wilayah LPSE** di bawah untuk menambahkannya "
        "terlebih dahulu, baru kedua tombol cek tender di bawah bisa dipakai."
    )

st.divider()

tab_lelang, tab_beranda, tab_kata_kunci, tab_excel, tab_wilayah = st.tabs(
    [
        "\U0001F50D Cek Tender (Daftar Lengkap)",
        "\U0001F4C5 Ringkasan Beranda (Akhir Pendaftaran)",
        "\U0001F511 Kata Kunci",
        "\U0001F4D7 Excel",
        "\U0001F5FA Wilayah LPSE",
    ]
)

# ---------------------------------------------------------------------------
# TAB 1: full /lelang list check
# ---------------------------------------------------------------------------

with tab_lelang:
    st.caption(
        "Mengambil SELURUH paket tender tahun ini dari /lelang tiap wilayah aktif, "
        "menyaring yang terkait jalan, lalu membandingkan dengan data sebelumnya. "
        "Tidak ada tanggal akhir pendaftaran di sini - untuk itu lihat tab Ringkasan Beranda."
    )

    if active_regions:
        st.caption("Wilayah yang akan diperiksa: " + ", ".join(r["region_identifier"] for r in active_regions))

    check_clicked = st.button(
        "\U0001F50D CEK TENDER (Wilayah Aktif)", type="primary", use_container_width=True,
        disabled=not active_regions, key="btn_cek_lelang",
    )

    if check_clicked:
        region_ids = [r["region_identifier"] for r in active_regions]
        with st.status("Memeriksa LPSE...", expanded=True) as status:
            with db.connect() as conn:
                for rid in region_ids:
                    st.write(f"Memeriksa {rid} ({build_lelang_url(rid)}) ...")
                st.write("Mengambil data dan menyaring paket terkait jalan...")
                summary = run_scrape_and_compare(conn, region_ids)
                st.write("Membandingkan dengan data sebelumnya...")
            status.update(label="PEMERIKSAAN SELESAI", state="complete")

        st.session_state["last_summary_lelang"] = {
            "new": summary.new_packages,
            "updated": summary.updated_packages,
            "existing": summary.existing_packages,
            "region_results": [
                {
                    "region_identifier": r.region_identifier, "success": r.success,
                    "error_message": r.error_message, "total_found": r.total_found,
                    "relevant_found": r.relevant_found,
                }
                for r in summary.region_results
            ],
        }
        st.rerun()

    lelang_result = st.session_state.get("last_summary_lelang")
    if lelang_result:
        render_result_banner(lelang_result, "PAKET BARU DITEMUKAN")
        new_pkgs, updated_pkgs = lelang_result["new"], lelang_result["updated"]

        if new_pkgs:
            st.markdown("### \U0001F195 Paket Baru")
            for pkg in new_pkgs:
                with st.container(border=True):
                    st.markdown(f"**{pkg['nama_paket']}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Wilayah:** {pkg['region_identifier']}")
                    c2.write(f"**Status:** {pkg['tahapan']}")
                    c3.write(f"**HPS:** {pkg['hps_text'] or '-'}")
                    c4.write(f"**Ditemukan:** {pkg['scraped_at']}")
                    if pkg.get("package_url"):
                        st.markdown(f"[Buka di LPSE]({pkg['package_url']})")

        if updated_pkgs:
            st.markdown("### \U0001F501 Paket Diperbarui")
            for pkg in updated_pkgs:
                st.write(f"- **{pkg['nama_paket']}** ({pkg['region_identifier']}): {pkg.get('_change_summary', '')}")

    st.divider()
    st.subheader("Paket Relevan Tersimpan - Daftar Lengkap")
    st.caption("Urutan dasar: paling lama → paling baru. Gunakan filter/urutkan di bawah untuk menyesuaikan tampilan.")
    with db.connect() as conn:
        lelang_rows = db.get_relevant_packages(conn)

    if not lelang_rows:
        st.caption("Belum ada data. Klik \"CEK TENDER\" di atas untuk mulai memeriksa.")
    else:
        display_rows = render_filter_controls(
            lelang_rows, key_prefix="lelang", status_field="tahapan", status_label="Status",
            kategori_field="jenis_pengadaan", kategori_label="Jenis Pengadaan",
        )
        st.dataframe(
            [
                {
                    "Kode Lelang": r["package_id"] or "-",
                    "Nama Paket": r["nama_paket"],
                    "Wilayah": r["region_identifier"],
                    "Status": r["tahapan"],
                    "Jenis Pengadaan": r["jenis_pengadaan"],
                    "HPS": r["hps_text"],
                    "Pertama Ditemukan": r["first_seen_at"],
                    "Terakhir Diperbarui": r["last_updated_at"],
                }
                for r in display_rows
            ],
            use_container_width=True, hide_index=True,
        )

# ---------------------------------------------------------------------------
# TAB 2: homepage ("Beranda") summary check - has Akhir Pendaftaran dates
# ---------------------------------------------------------------------------

with tab_beranda:
    st.caption(
        "Mengambil ringkasan dari halaman BERANDA tiap wilayah aktif (bagian Tender + Non Tender), "
        "yang memuat tanggal Akhir Pendaftaran. Dataset ini TERPISAH dari Daftar Lengkap di tab "
        "sebelumnya - lihat PROJECT_STATUS.md untuk alasannya."
    )

    if active_regions:
        st.caption("Wilayah yang akan diperiksa: " + ", ".join(r["region_identifier"] for r in active_regions))

    check_beranda_clicked = st.button(
        "\U0001F4C5 CEK RINGKASAN BERANDA (Wilayah Aktif)", type="primary", use_container_width=True,
        disabled=not active_regions, key="btn_cek_beranda",
    )

    if check_beranda_clicked:
        region_ids = [r["region_identifier"] for r in active_regions]
        with st.status("Memeriksa beranda LPSE...", expanded=True) as status:
            with db.connect() as conn:
                for rid in region_ids:
                    st.write(f"Memeriksa {rid} ({build_homepage_url(rid)}) ...")
                st.write("Menyaring paket terkait jalan...")
                hp_summary = run_homepage_scrape_and_compare(conn, region_ids)
                st.write("Membandingkan dengan data sebelumnya...")
            status.update(label="PEMERIKSAAN SELESAI", state="complete")

        st.session_state["last_summary_beranda"] = {
            "new": hp_summary.new_packages,
            "updated": hp_summary.updated_packages,
            "existing": hp_summary.existing_packages,
            "region_results": [
                {
                    "region_identifier": r.region_identifier, "success": r.success,
                    "error_message": r.error_message, "total_found": r.total_found,
                    "relevant_found": r.relevant_found,
                }
                for r in hp_summary.region_results
            ],
        }
        st.rerun()

    beranda_result = st.session_state.get("last_summary_beranda")
    if beranda_result:
        render_result_banner(beranda_result, "PAKET BARU DITEMUKAN (BERANDA)")
        new_hp_pkgs, updated_hp_pkgs = beranda_result["new"], beranda_result["updated"]

        if new_hp_pkgs:
            st.markdown("### \U0001F195 Paket Baru")
            for pkg in new_hp_pkgs:
                with st.container(border=True):
                    st.markdown(f"**{pkg['nama_paket']}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Wilayah:** {pkg['region_identifier']}")
                    c2.write(f"**Bagian:** {pkg['section']} / {pkg['kategori']}")
                    c3.write(f"**HPS:** {pkg['hps_text'] or '-'}")
                    c4.write(f"**Akhir Pendaftaran:** {pkg['akhir_pendaftaran_text'] or '-'}")
                    if pkg.get("package_url"):
                        st.markdown(f"[Buka di LPSE]({pkg['package_url']})")

        if updated_hp_pkgs:
            st.markdown("### \U0001F501 Paket Diperbarui")
            for pkg in updated_hp_pkgs:
                st.write(f"- **{pkg['nama_paket']}** ({pkg['region_identifier']}): {pkg.get('_change_summary', '')}")

    st.divider()
    st.subheader("Kalender Akhir Pendaftaran")
    with db.connect() as conn:
        hp_rows_all = db.get_relevant_homepage_packages(conn)

    grouped = {}  # always defined, even if the calendar itself isn't rendered below
    if not hp_rows_all:
        st.caption("Belum ada data. Klik \"CEK RINGKASAN BERANDA\" di atas untuk mulai memeriksa.")
    else:
        today = date.today()
        st.session_state.setdefault("cal_year", today.year)
        st.session_state.setdefault("cal_month", today.month)
        st.session_state.setdefault("cal_selected_date", None)

        # Narrower, centered column + a scoped container (see
        # ui/branding.py's CALENDAR_CONTAINER_KEY) - keeps the calendar
        # compact instead of stretching full-width, per Nikol's request.
        _, cal_mid, _ = st.columns([1, 2, 1])
        with cal_mid:
            with st.container(key=branding.CALENDAR_CONTAINER_KEY):
                nav1, nav2, nav3 = st.columns([1, 2, 1])
                if nav1.button("←", key="cal_prev", use_container_width=True):
                    y, m = calendar_service.add_months(st.session_state["cal_year"], st.session_state["cal_month"], -1)
                    st.session_state["cal_year"], st.session_state["cal_month"] = y, m
                    st.rerun()
                nav2.markdown(
                    f"<h6 style='text-align:center'>{calendar_service.MONTH_NAMES_ID[st.session_state['cal_month']]} "
                    f"{st.session_state['cal_year']}</h6>",
                    unsafe_allow_html=True,
                )
                if nav3.button("→", key="cal_next", use_container_width=True):
                    y, m = calendar_service.add_months(st.session_state["cal_year"], st.session_state["cal_month"], 1)
                    st.session_state["cal_year"], st.session_state["cal_month"] = y, m
                    st.rerun()

                grouped = calendar_service.group_by_deadline_date(hp_rows_all)
                grid = calendar_service.build_month_grid(st.session_state["cal_year"], st.session_state["cal_month"])

                header_cols = st.columns(7, gap="small")
                for i, wd in enumerate(calendar_service.WEEKDAY_NAMES_ID):
                    header_cols[i].markdown(f"<div style='text-align:center;font-size:0.72rem'><b>{wd}</b></div>", unsafe_allow_html=True)

                for week in grid:
                    week_cols = st.columns(7, gap="small")
                    for i, day in enumerate(week):
                        with week_cols[i]:
                            if day is None:
                                st.write("")
                                continue
                            day_key = day.isoformat()
                            day_pkgs = grouped.get(day_key, [])
                            label = f"{day.day}" + (" •" if day_pkgs else "")
                            help_text = None
                            if day_pkgs:
                                names = "\n".join(f"- {p['nama_paket']}" for p in day_pkgs[:5])
                                help_text = f"{len(day_pkgs)} paket jatuh tempo:\n{names}"
                            if st.button(label, key=f"cal_day_{day_key}", help=help_text, use_container_width=True):
                                st.session_state["cal_selected_date"] = day_key
                                st.rerun()

        selected = st.session_state.get("cal_selected_date")
        if selected and selected in grouped:
            st.markdown(f"**Paket dengan Akhir Pendaftaran {selected}:**")
            for p in grouped[selected]:
                with st.container(border=True):
                    st.markdown(f"**{p['nama_paket']}**")
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Wilayah:** {p['region_identifier']}")
                    c2.write(f"**Bagian:** {p['section']} / {p['kategori']}")
                    c3.write(f"**HPS:** {p['hps_text'] or '-'}")
                    if p["package_url"]:
                        st.markdown(f"[Buka di LPSE]({p['package_url']})")
        elif selected:
            st.session_state["cal_selected_date"] = None

    st.divider()
    st.subheader("Paket Relevan Tersimpan - Ringkasan Beranda")
    st.caption("Urutan dasar: paling lama → paling baru. Gunakan filter/urutkan di bawah untuk menyesuaikan tampilan.")

    if hp_rows_all:
        display_hp_rows = render_filter_controls(
            hp_rows_all, key_prefix="beranda", status_field="section", status_label="Bagian",
            kategori_field="kategori", kategori_label="Kategori",
        )
        st.dataframe(
            [
                {
                    "Kode Lelang": r["package_id"] or "-",
                    "Nama Paket": r["nama_paket"],
                    "Wilayah": r["region_identifier"],
                    "Bagian": r["section"],
                    "Kategori": r["kategori"],
                    "HPS": r["hps_text"],
                    "Akhir Pendaftaran": r["akhir_pendaftaran_text"],
                    "Pertama Ditemukan": r["first_seen_at"],
                }
                for r in display_hp_rows
            ],
            use_container_width=True, hide_index=True,
        )

# ---------------------------------------------------------------------------
# TAB 3: keyword ("Kata Kunci") management - Phase 5
# ---------------------------------------------------------------------------

with tab_kata_kunci:
    st.caption(
        "Kata kunci menentukan paket mana yang dianggap 'terkait jalan' di kedua tab di atas. "
        "Pencocokan tidak peka huruf besar/kecil dan boleh berupa bagian kata (contoh: kata kunci "
        "'jalan' akan cocok dengan 'Peningkatan Jalan Raya'). Kata kunci yang di-nonaktifkan tidak "
        "dipakai saat menyaring, tapi tetap tersimpan."
    )

    with st.form("form_tambah_kata_kunci", clear_on_submit=True):
        st.markdown("**Tambah Kata Kunci Baru**")
        new_keyword = st.text_input("Kata Kunci", placeholder="Contoh: jembatan")
        submitted_kw = st.form_submit_button("Tambah", type="primary")

    if submitted_kw:
        if not new_keyword.strip():
            st.error("Kata kunci tidak boleh kosong.")
        else:
            with db.connect() as conn:
                ok, msg = db.add_keyword(conn, new_keyword)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.markdown("**Daftar Kata Kunci**")

    with db.connect() as conn:
        all_keywords = db.get_all_keywords(conn)

    if not all_keywords:
        st.caption("Belum ada kata kunci. Tambahkan menggunakan form di atas.")
    else:
        header = st.columns([4, 1, 1, 1])
        header[0].markdown("**Kata Kunci**")
        header[1].markdown("**Ubah**")
        header[2].markdown("**Aktif**")
        header[3].markdown("**Hapus**")

        for kw in all_keywords:
            row = st.columns([4, 1, 1, 1])
            row[0].write(kw["keyword"])

            # A popover with its own explicit "Simpan" button - NOT a plain
            # text_input bound directly to this row, which would otherwise
            # save (and rerun) on every single keystroke while typing.
            with row[1].popover("\u270f\ufe0f", use_container_width=True):
                with st.form(f"form_rename_kw_{kw['id']}"):
                    renamed = st.text_input("Kata kunci baru", value=kw["keyword"])
                    if st.form_submit_button("Simpan", type="primary"):
                        with db.connect() as conn:
                            ok, msg = db.update_keyword_text(conn, kw["id"], renamed)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)

            is_enabled = row[2].checkbox(
                "Aktif", value=bool(kw["is_enabled"]), key=f"kw_active_{kw['id']}", label_visibility="collapsed",
            )
            if is_enabled != bool(kw["is_enabled"]):
                with db.connect() as conn:
                    db.set_keyword_enabled(conn, kw["id"], is_enabled)
                st.rerun()

            if row[3].button("\U0001F5D1️", key=f"kw_delete_{kw['id']}", help="Hapus kata kunci ini"):
                with db.connect() as conn:
                    db.delete_keyword(conn, kw["id"])
                st.rerun()

# ---------------------------------------------------------------------------
# TAB 4: Excel export - Phase 6 (two datasets, exported separately)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=5)
def _cached_discover_excel_files():
    """Walking the project folder on every single rerun (which Streamlit
    triggers on almost any widget interaction, anywhere in the app) is
    wasted work when the folder's contents rarely change - a short cache
    keeps the Excel tab snappy without needing a manual "refresh" button.
    Safe to cache: the return value is a plain list of strings, not
    database rows, so there's no staleness risk beyond "a file dropped in
    less than 5 seconds ago might not show up yet" - reload the tab if so."""
    return excel_service.discover_excel_files()


def render_excel_export_panel(dataset: str, rows_getter):
    """One full export panel (file picker, sheet/cell/column/mode
    settings, create/save/export buttons) for a single dataset. Called
    once per dataset below, so Daftar Lengkap and Ringkasan Beranda each
    get their own independent configuration and their own export button -
    per Nikol's request to keep the two exports separate."""
    dataset_label = excel_service.DATASET_LABELS[dataset]

    with db.connect() as conn:
        cfg_row = db.get_excel_config(conn, dataset)

    current_file = cfg_row["file_path"] if cfg_row else ""
    current_sheet = cfg_row["sheet_name"] if cfg_row else excel_service.DEFAULT_SHEET_NAMES[dataset]
    current_cell = cfg_row["start_cell"] if cfg_row else "A5"
    current_mode = cfg_row["mode"] if cfg_row else "replace"
    current_use_table = bool(cfg_row["use_excel_table"]) if cfg_row else True
    current_columns = (
        json.loads(cfg_row["enabled_columns"])
        if cfg_row and cfg_row["enabled_columns"]
        else excel_service.DEFAULT_COLUMNS[dataset]
    )

    file_key = f"{dataset}_excel_file_path"
    st.session_state.setdefault(file_key, current_file or "")

    discovered = _cached_discover_excel_files()
    if discovered:
        st.caption("File .xlsx terdeteksi di dalam folder proyek ini - klik untuk memakainya langsung:")
        pick_cols = st.columns(min(len(discovered), 4))
        for i, rel_path in enumerate(discovered[:4]):
            if pick_cols[i % len(pick_cols)].button(rel_path, key=f"{dataset}_pick_{i}", use_container_width=True):
                st.session_state[file_key] = str(excel_service.PROJECT_ROOT / rel_path)
                st.rerun()

    file_path_input = st.text_input(
        "Lokasi File Excel (path lengkap di komputer ini)", key=file_key,
        placeholder=r"Contoh: D:\Dokumen\LPSE_Monitoring.xlsx",
    )

    c1, c2, c3 = st.columns(3)
    sheet_name_input = c1.text_input("Nama Sheet", value=current_sheet, key=f"{dataset}_sheet")
    start_cell_input = c2.text_input(
        "Sel Awal Data", value=current_cell, key=f"{dataset}_cell",
        help="Contoh: A5 - baris di atasnya (A4) dianggap header dan tidak akan disentuh.",
    )
    mode_input = c3.selectbox(
        "Mode Ekspor", ["replace", "append_new"], index=["replace", "append_new"].index(current_mode),
        key=f"{dataset}_mode",
        format_func=lambda m: "Ganti Semua (Replace)" if m == "replace" else "Tambah Baru Saja (Append New)",
    )
    st.caption(
        "**Ganti Semua**: setiap ekspor menulis ulang seluruh daftar paket relevan terbaru (hanya baris "
        "yang PERNAH ditulis app ini yang dihapus dulu). **Tambah Baru Saja**: baris lama dibiarkan apa "
        "adanya, hanya paket yang belum pernah diekspor yang ditambahkan di bawahnya."
    )

    columns_input = st.multiselect(
        "Kolom yang Diekspor (urutan sesuai pilihan)",
        options=excel_service.AVAILABLE_COLUMNS[dataset],
        default=[c for c in current_columns if c in excel_service.AVAILABLE_COLUMNS[dataset]],
        format_func=lambda k: excel_service.COLUMN_LABELS.get(k, k),
        key=f"{dataset}_columns",
    )

    use_table_input = st.checkbox(
        "Jadikan Tabel Excel (disarankan) - baris bergaris-garis + tombol filter otomatis",
        value=current_use_table, key=f"{dataset}_use_table",
        help="Jika sel header ada yang kosong, atau kamu sudah membuat Tabel Excel sendiri di sel yang "
             "sama, bagian ini otomatis dilewati dan data tetap ditulis sebagai nilai biasa.",
    )

    save_col, create_col, export_col = st.columns(3)

    if save_col.button("\U0001F4BE Simpan Pengaturan", use_container_width=True, key=f"{dataset}_save"):
        with db.connect() as conn:
            db.save_excel_config(
                conn, dataset, file_path_input.strip(), sheet_name_input.strip() or dataset_label,
                start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMNS[dataset],
                mode_input, use_table_input,
            )
        st.success("Pengaturan Excel disimpan.")
        st.rerun()

    if create_col.button("\U0001F195 Buat File Baru", use_container_width=True, key=f"{dataset}_create", help="Hanya jika file di atas belum ada."):
        if not file_path_input.strip():
            st.error("Isi lokasi file terlebih dahulu.")
        else:
            try:
                from pathlib import Path
                excel_service.create_new_excel_file(
                    Path(file_path_input.strip()), sheet_name_input.strip() or dataset_label,
                    start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMNS[dataset],
                )
                st.success(f"File baru dibuat: {file_path_input.strip()}")
            except excel_service.ExcelServiceError as exc:
                st.error(exc.user_message)

    if export_col.button("\U0001F4E4 Ekspor Sekarang", type="primary", use_container_width=True, key=f"{dataset}_export"):
        with db.connect() as conn:
            db.save_excel_config(
                conn, dataset, file_path_input.strip(), sheet_name_input.strip() or dataset_label,
                start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMNS[dataset],
                mode_input, use_table_input,
            )
            config = {
                "file_path": file_path_input.strip(), "sheet_name": sheet_name_input.strip() or dataset_label,
                "start_cell": start_cell_input.strip() or "A5",
                "enabled_columns": columns_input or excel_service.DEFAULT_COLUMNS[dataset],
                "mode": mode_input, "use_excel_table": use_table_input,
            }
            rows_to_export = rows_getter(conn)
            try:
                result = excel_service.export_packages(conn, rows_to_export, config, dataset=dataset)
                st.success(
                    f"Berhasil! {result.rows_written} baris ditulis ke '{result.sheet_name}' "
                    f"(mode: {result.mode}). Backup dibuat di: {result.backup_path}"
                )
                if result.table_applied:
                    st.caption("✅ Data ditulis sebagai Tabel Excel (baris bergaris-garis + tombol filter).")
                elif result.table_skip_reason:
                    st.caption(f"ℹ️ {result.table_skip_reason}")
            except excel_service.ExcelServiceError as exc:
                st.error(exc.user_message)
                if exc.technical_detail != exc.user_message:
                    with st.expander("Detail Error"):
                        st.code(exc.technical_detail)


with tab_excel:
    st.caption(
        "Ekspor paket relevan ke file Excel yang sudah dipakai kantor, bukan membuat file baru setiap "
        "kali. File akan DI-BACKUP OTOMATIS setiap kali sebelum ditulis (lihat folder `backups/`), dan "
        "sheet/sel lain di file tersebut tidak akan diubah. Kedua dataset diekspor TERPISAH - atur "
        "masing-masing di sub-tab-nya sendiri."
    )

    sub_lelang, sub_beranda = st.tabs(["Daftar Lengkap", "Ringkasan Beranda"])
    with sub_lelang:
        render_excel_export_panel(excel_service.DATASET_LELANG, db.get_relevant_packages)
    with sub_beranda:
        render_excel_export_panel(excel_service.DATASET_BERANDA, db.get_relevant_homepage_packages)

# ---------------------------------------------------------------------------
# TAB 5: region ("Wilayah LPSE") management
# ---------------------------------------------------------------------------

with tab_wilayah:
    st.caption(
        "Tambahkan semua wilayah LPSE yang ingin dipantau di sini. Kedua tombol cek tender di tab "
        "lain akan otomatis memeriksa SEMUA wilayah berstatus Aktif - tidak perlu mengetik ulang "
        "setiap kali."
    )

    with st.form("form_tambah_wilayah", clear_on_submit=True):
        st.markdown("**Tambah Wilayah Baru**")
        c1, c2 = st.columns(2)
        new_region_name = c1.text_input("Nama Wilayah", placeholder="Contoh: Kota Singkawang")
        new_region_id = c2.text_input("Region Identifier", placeholder="Contoh: singkawangkota")
        st.caption(
            "Region Identifier adalah bagian URL LPSE wilayah tersebut, misalnya "
            "https://spse.inaproc.id/**singkawangkota**/lelang atau "
            "https://spse.inaproc.id/**kalbarprov**/ untuk provinsi."
        )
        submitted = st.form_submit_button("Tambah Wilayah", type="primary")

    if submitted:
        if not new_region_id.strip():
            st.error("Region Identifier tidak boleh kosong.")
        else:
            with db.connect() as conn:
                ok, msg = db.add_region(
                    conn,
                    region_name=new_region_name or new_region_id,
                    region_identifier=new_region_id.strip(),
                    base_url=build_lelang_url(new_region_id.strip()),
                )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.markdown("**Daftar Wilayah**")

    with db.connect() as conn:
        all_regions = db.get_all_regions(conn)

    if not all_regions:
        st.caption("Belum ada wilayah. Tambahkan menggunakan form di atas.")
    else:
        header = st.columns([3, 2, 4, 1, 1])
        header[0].markdown("**Nama Wilayah**")
        header[1].markdown("**Identifier**")
        header[2].markdown("**URL**")
        header[3].markdown("**Aktif**")
        header[4].markdown("**Hapus**")

        for region in all_regions:
            row = st.columns([3, 2, 4, 1, 1])
            row[0].write(region["region_name"])
            row[1].write(region["region_identifier"])
            row[2].markdown(f"[{region['base_url']}]({region['base_url']})")

            is_active = row[3].checkbox(
                "Aktif", value=bool(region["is_active"]), key=f"active_{region['id']}", label_visibility="collapsed",
            )
            if is_active != bool(region["is_active"]):
                with db.connect() as conn:
                    db.set_region_active(conn, region["id"], is_active)
                st.rerun()

            if row[4].button("\U0001F5D1️", key=f"delete_{region['id']}", help="Hapus wilayah ini"):
                with db.connect() as conn:
                    db.delete_region(conn, region["id"])
                st.rerun()
