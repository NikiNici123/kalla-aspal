"""
LPSE Monitor - Phase 1 + 2 + partial Phase 4 prototype.

A local-first Streamlit app for admin staff to check LPSE/SPSE tender
listings for new road-construction packages, twice a day.

Run with:  streamlit run app.py
(see README.md for full Windows setup instructions)

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
_CHRONOLOGICAL_ORDER_SQL comment for why).

Not yet built (later phases): keyword management UI, Excel export,
scheduling/notifications, package detail/history pages. Those all have
working logic underneath already reachable via database/services modules -
only their UI pages are still to come.
"""

from __future__ import annotations

import streamlit as st

from database import database as db
from scraper.lpse_scraper import build_lelang_url
from scraper.lpse_homepage_scraper import build_homepage_url
from services.comparison_service import run_scrape_and_compare
from services.homepage_service import run_homepage_scrape_and_compare

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

tab_lelang, tab_beranda, tab_wilayah = st.tabs(
    ["\U0001F50D Cek Tender (Daftar Lengkap)", "\U0001F4C5 Ringkasan Beranda (Akhir Pendaftaran)", "\U0001F5FA Wilayah LPSE"]
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
    st.subheader("Paket Relevan Tersimpan - Daftar Lengkap (urut: paling lama → paling baru)")
    with db.connect() as conn:
        rows = db.get_relevant_packages(conn)

    if not rows:
        st.caption("Belum ada data. Klik \"CEK TENDER\" di atas untuk mulai memeriksa.")
    else:
        st.dataframe(
            [
                {
                    "Kode Lelang": r["package_id"] or "-",
                    "Nama Paket": r["nama_paket"],
                    "Wilayah": r["region_identifier"],
                    "Status": r["tahapan"],
                    "HPS": r["hps_text"],
                    "Pertama Ditemukan": r["first_seen_at"],
                    "Terakhir Diperbarui": r["last_updated_at"],
                }
                for r in rows
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
    st.subheader("Paket Relevan Tersimpan - Ringkasan Beranda (urut: paling lama → paling baru)")
    with db.connect() as conn:
        hp_rows = db.get_relevant_homepage_packages(conn)

    if not hp_rows:
        st.caption("Belum ada data. Klik \"CEK RINGKASAN BERANDA\" di atas untuk mulai memeriksa.")
    else:
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
                for r in hp_rows
            ],
            use_container_width=True, hide_index=True,
        )

# ---------------------------------------------------------------------------
# TAB 3: region ("Wilayah LPSE") management
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
