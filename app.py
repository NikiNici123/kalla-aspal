"""
LPSE Monitor - Phase 1-4 + partial Phase 3/5/6/7 prototype.

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
services, and different tabs below - never mixed together.

Ordering convention used everywhere in this app: relevant packages are
listed EARLIEST first, LATEST last, using Package ID (Kode Lelang) as a
stand-in for upload order (see database/database.py's
_CHRONOLOGICAL_ORDER_SQL comment for why). Filtering/sorting controls in
each tab operate on top of that base order - see services/filter_service.py.

Tabs: Cek Tender, Ringkasan Beranda (+ built-in deadline calendar), Kata
Kunci (Phase 5), Excel (Phase 6), Wilayah LPSE (Phase 4).
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from database import database as db
from scraper.lpse_scraper import build_lelang_url
from scraper.lpse_homepage_scraper import build_homepage_url
from services.comparison_service import run_scrape_and_compare
from services.homepage_service import run_homepage_scrape_and_compare
from services import filter_service, calendar_service, excel_service

st.set_page_config(page_title="LPSE Monitor", page_icon="\U0001F6E3", layout="wide")

db.init_db()


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
    SORTED rows, ready to display - the HPS sum shown next to it should
    always be computed from this same returned list so it recalculates
    with whatever filter is active (per Nikol's request)."""
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

    hps_total = filter_service.sum_hps(sorted_rows)
    m1, m2 = st.columns(2)
    m1.metric("Jumlah Paket (sesuai filter)", len(sorted_rows))
    m2.metric("Total HPS (sesuai filter)", format_rupiah(hps_total))

    return sorted_rows


# ---------------------------------------------------------------------------
# Dashboard header (shared across both datasets)
# ---------------------------------------------------------------------------

st.title("LPSE MONITOR")

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

    summary = st.session_state.get("last_summary_lelang")
    if summary:
        for rr in summary["region_results"]:
            if not rr["success"]:
                with st.expander(f"⚠️ Gagal mengambil data dari LPSE {rr['region_identifier']}."):
                    st.error(rr["error_message"])
            else:
                st.caption(
                    f"{rr['region_identifier']}: {rr['total_found']} paket ditemukan, "
                    f"{rr['relevant_found']} relevan (terkait jalan)."
                )

        new_count = len(summary["new"])
        if new_count > 0:
            st.success(f"## {new_count} PAKET BARU DITEMUKAN")
        else:
            st.info("## TIDAK ADA PAKET BARU")

        if summary["new"]:
            st.markdown("### \U0001F195 Paket Baru")
            for pkg in summary["new"]:
                with st.container(border=True):
                    st.markdown(f"**{pkg['nama_paket']}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Wilayah:** {pkg['region_identifier']}")
                    c2.write(f"**Status:** {pkg['tahapan']}")
                    c3.write(f"**HPS:** {pkg['hps_text'] or '-'}")
                    c4.write(f"**Ditemukan:** {pkg['scraped_at']}")
                    if pkg.get("package_url"):
                        st.markdown(f"[Buka di LPSE]({pkg['package_url']})")

        if summary["updated"]:
            st.markdown("### \U0001F501 Paket Diperbarui")
            for pkg in summary["updated"]:
                st.write(f"- **{pkg['nama_paket']}** ({pkg['region_identifier']}): {pkg.get('_change_summary', '')}")

    st.divider()
    st.subheader("Paket Relevan Tersimpan - Daftar Lengkap")
    st.caption("Urutan dasar: paling lama → paling baru. Gunakan filter/urutkan di bawah untuk menyesuaikan tampilan.")
    with db.connect() as conn:
        rows = db.get_relevant_packages(conn)

    if not rows:
        st.caption("Belum ada data. Klik \"CEK TENDER\" di atas untuk mulai memeriksa.")
    else:
        display_rows = render_filter_controls(
            rows, key_prefix="lelang", status_field="tahapan", status_label="Status",
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

    hp_summary = st.session_state.get("last_summary_beranda")
    if hp_summary:
        for rr in hp_summary["region_results"]:
            if not rr["success"]:
                with st.expander(f"⚠️ Gagal mengambil beranda LPSE {rr['region_identifier']}."):
                    st.error(rr["error_message"])
            else:
                st.caption(
                    f"{rr['region_identifier']}: {rr['total_found']} paket ditemukan, "
                    f"{rr['relevant_found']} relevan (terkait jalan)."
                )

        new_count = len(hp_summary["new"])
        if new_count > 0:
            st.success(f"## {new_count} PAKET BARU DITEMUKAN (BERANDA)")
        else:
            st.info("## TIDAK ADA PAKET BARU (BERANDA)")

        if hp_summary["new"]:
            st.markdown("### \U0001F195 Paket Baru")
            for pkg in hp_summary["new"]:
                with st.container(border=True):
                    st.markdown(f"**{pkg['nama_paket']}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Wilayah:** {pkg['region_identifier']}")
                    c2.write(f"**Bagian:** {pkg['section']} / {pkg['kategori']}")
                    c3.write(f"**HPS:** {pkg['hps_text'] or '-'}")
                    c4.write(f"**Akhir Pendaftaran:** {pkg['akhir_pendaftaran_text'] or '-'}")
                    if pkg.get("package_url"):
                        st.markdown(f"[Buka di LPSE]({pkg['package_url']})")

        if hp_summary["updated"]:
            st.markdown("### \U0001F501 Paket Diperbarui")
            for pkg in hp_summary["updated"]:
                st.write(f"- **{pkg['nama_paket']}** ({pkg['region_identifier']}): {pkg.get('_change_summary', '')}")

    st.divider()
    st.subheader("Kalender Akhir Pendaftaran")
    with db.connect() as conn:
        hp_rows_all = db.get_relevant_homepage_packages(conn)

    if not hp_rows_all:
        st.caption("Belum ada data. Klik \"CEK RINGKASAN BERANDA\" di atas untuk mulai memeriksa.")
    else:
        today = date.today()
        if "cal_year" not in st.session_state:
            st.session_state["cal_year"] = today.year
        if "cal_month" not in st.session_state:
            st.session_state["cal_month"] = today.month
        if "cal_selected_date" not in st.session_state:
            st.session_state["cal_selected_date"] = None

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        if nav1.button("← Bulan Sebelumnya", key="cal_prev"):
            y, m = calendar_service.add_months(st.session_state["cal_year"], st.session_state["cal_month"], -1)
            st.session_state["cal_year"], st.session_state["cal_month"] = y, m
            st.rerun()
        nav2.markdown(
            f"<h4 style='text-align:center'>{calendar_service.MONTH_NAMES_ID[st.session_state['cal_month']]} "
            f"{st.session_state['cal_year']}</h4>",
            unsafe_allow_html=True,
        )
        if nav3.button("Bulan Berikutnya →", key="cal_next"):
            y, m = calendar_service.add_months(st.session_state["cal_year"], st.session_state["cal_month"], 1)
            st.session_state["cal_year"], st.session_state["cal_month"] = y, m
            st.rerun()

        grouped = calendar_service.group_by_deadline_date(hp_rows_all)
        grid = calendar_service.build_month_grid(st.session_state["cal_year"], st.session_state["cal_month"])

        header_cols = st.columns(7)
        for i, wd in enumerate(calendar_service.WEEKDAY_NAMES_ID):
            header_cols[i].markdown(f"<div style='text-align:center'><b>{wd}</b></div>", unsafe_allow_html=True)

        for week in grid:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day is None:
                        st.write("")
                        continue
                    day_key = day.isoformat()
                    day_pkgs = grouped.get(day_key, [])
                    label = f"{day.day}" + (" \U0001F534" if day_pkgs else "")
                    if day_pkgs:
                        names = "\n".join(f"- {p['nama_paket']}" for p in day_pkgs[:5])
                        help_text = f"{len(day_pkgs)} paket jatuh tempo:\n{names}"
                    else:
                        help_text = None
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

    if not hp_rows_all:
        pass
    else:
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
        header = st.columns([4, 1, 1])
        header[0].markdown("**Kata Kunci**")
        header[1].markdown("**Aktif**")
        header[2].markdown("**Hapus**")

        for kw in all_keywords:
            row = st.columns([4, 1, 1])
            edited_text = row[0].text_input(
                "Kata Kunci", value=kw["keyword"], key=f"kw_text_{kw['id']}", label_visibility="collapsed",
            )
            if edited_text.strip() and edited_text.strip() != kw["keyword"]:
                with db.connect() as conn:
                    db.update_keyword_text(conn, kw["id"], edited_text)
                st.rerun()

            is_enabled = row[1].checkbox(
                "Aktif", value=bool(kw["is_enabled"]), key=f"kw_active_{kw['id']}", label_visibility="collapsed",
            )
            if is_enabled != bool(kw["is_enabled"]):
                with db.connect() as conn:
                    db.set_keyword_enabled(conn, kw["id"], is_enabled)
                st.rerun()

            if row[2].button("\U0001F5D1️", key=f"kw_delete_{kw['id']}", help="Hapus kata kunci ini"):
                with db.connect() as conn:
                    db.delete_keyword(conn, kw["id"])
                st.rerun()

# ---------------------------------------------------------------------------
# TAB 4: Excel export - Phase 6
# ---------------------------------------------------------------------------

with tab_excel:
    st.caption(
        "Ekspor paket relevan (Daftar Lengkap) ke SATU file Excel yang sudah dipakai kantor, bukan "
        "membuat file baru setiap kali. File akan DI-BACKUP OTOMATIS setiap kali sebelum ditulis "
        "(lihat folder `backups/`), dan sheet/sel lain di file tersebut tidak akan diubah."
    )

    with db.connect() as conn:
        excel_cfg_row = db.get_excel_config(conn)

    current_file_path = excel_cfg_row["file_path"] if excel_cfg_row else ""
    current_sheet = excel_cfg_row["sheet_name"] if excel_cfg_row else "Data LPSE"
    current_cell = excel_cfg_row["start_cell"] if excel_cfg_row else "A5"
    current_mode = excel_cfg_row["mode"] if excel_cfg_row else "replace"
    import json as _json
    current_columns = (
        _json.loads(excel_cfg_row["enabled_columns"])
        if excel_cfg_row and excel_cfg_row["enabled_columns"]
        else excel_service.DEFAULT_COLUMN_ORDER
    )

    st.markdown("**Pengaturan File Excel**")
    file_path_input = st.text_input(
        "Lokasi File Excel (path lengkap di komputer ini)",
        value=current_file_path or "",
        placeholder=r"Contoh: D:\Dokumen\LPSE_Monitoring.xlsx",
    )
    c1, c2, c3 = st.columns(3)
    sheet_name_input = c1.text_input("Nama Sheet", value=current_sheet)
    start_cell_input = c2.text_input("Sel Awal Data", value=current_cell, help="Contoh: A5 - baris di atasnya (A4) dianggap header dan tidak akan disentuh.")
    mode_input = c3.selectbox(
        "Mode Ekspor", ["replace", "append_new"], index=["replace", "append_new"].index(current_mode),
        format_func=lambda m: "Ganti Semua (Replace)" if m == "replace" else "Tambah Baru Saja (Append New)",
    )
    st.caption(
        "**Ganti Semua**: setiap ekspor menulis ulang seluruh daftar paket relevan terbaru (hanya baris "
        "yang PERNAH ditulis app ini yang dihapus dulu). **Tambah Baru Saja**: baris lama dibiarkan apa "
        "adanya, hanya paket yang belum pernah diekspor yang ditambahkan di bawahnya."
    )

    columns_input = st.multiselect(
        "Kolom yang Diekspor (urutan sesuai pilihan)",
        options=list(excel_service.COLUMN_LABELS.keys()),
        default=current_columns,
        format_func=lambda k: excel_service.COLUMN_LABELS.get(k, k),
    )

    save_col, create_col, export_col = st.columns(3)

    if save_col.button("\U0001F4BE Simpan Pengaturan", use_container_width=True):
        with db.connect() as conn:
            db.save_excel_config(
                conn, file_path_input.strip(), sheet_name_input.strip() or "Data LPSE",
                start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMN_ORDER,
                mode_input,
            )
        st.success("Pengaturan Excel disimpan.")
        st.rerun()

    if create_col.button("\U0001F195 Buat File Baru", use_container_width=True, help="Hanya jika file di atas belum ada."):
        if not file_path_input.strip():
            st.error("Isi lokasi file terlebih dahulu.")
        else:
            try:
                from pathlib import Path
                excel_service.create_new_excel_file(
                    Path(file_path_input.strip()), sheet_name_input.strip() or "Data LPSE",
                    start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMN_ORDER,
                )
                st.success(f"File baru dibuat: {file_path_input.strip()}")
            except excel_service.ExcelServiceError as exc:
                st.error(exc.user_message)

    if export_col.button("\U0001F4E4 Ekspor Sekarang", type="primary", use_container_width=True):
        with db.connect() as conn:
            db.save_excel_config(
                conn, file_path_input.strip(), sheet_name_input.strip() or "Data LPSE",
                start_cell_input.strip() or "A5", columns_input or excel_service.DEFAULT_COLUMN_ORDER,
                mode_input,
            )
            config = {
                "file_path": file_path_input.strip(), "sheet_name": sheet_name_input.strip() or "Data LPSE",
                "start_cell": start_cell_input.strip() or "A5",
                "enabled_columns": columns_input or excel_service.DEFAULT_COLUMN_ORDER, "mode": mode_input,
            }
            packages_to_export = db.get_relevant_packages(conn)
            try:
                result = excel_service.export_packages(conn, packages_to_export, config)
                st.success(
                    f"Berhasil! {result.rows_written} baris ditulis ke '{result.sheet_name}' "
                    f"(mode: {result.mode}). Backup dibuat di: {result.backup_path}"
                )
            except excel_service.ExcelServiceError as exc:
                st.error(exc.user_message)
                if exc.technical_detail != exc.user_message:
                    with st.expander("Detail Error"):
                        st.code(exc.technical_detail)

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
