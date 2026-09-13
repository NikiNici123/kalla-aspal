"""
LPSE Monitor - Phase 1 + Phase 2 prototype.

A local-first Streamlit app for admin staff to check LPSE/SPSE tender
listings for new road-construction packages, twice a day.

Run with:  streamlit run app.py
(see README.md for full Windows setup instructions)

Scope of THIS version (per the phased development plan):
  Phase 1 - scrape a region, filter by keyword, show results.
  Phase 2 - remember results in SQLite, detect new/updated/existing.
Not yet built (later phases): region management UI, keyword management UI,
Excel export, scheduling/notifications, package detail/history pages.
Those all have working logic underneath already reachable via
database/services modules - only their UI pages are still to come.
"""

from __future__ import annotations

import json

import streamlit as st

from database import database as db
from services.comparison_service import run_scrape_and_compare
from scraper.lpse_scraper import build_lelang_url

st.set_page_config(page_title="LPSE Monitor", page_icon="\U0001F6E3", layout="wide")

db.init_db()


def format_rupiah(value) -> str:
    if value is None:
        return "-"
    return "Rp " + f"{value:,.0f}".replace(",", ".")


def region_identifiers_input() -> list:
    raw = st.session_state.get("region_input", "singkawangkota")
    return [r.strip() for r in raw.split(",") if r.strip()]


# ---------------------------------------------------------------------------
# Dashboard header
# ---------------------------------------------------------------------------

st.title("LPSE MONITOR")

with db.connect() as conn:
    active_regions = db.get_active_regions(conn)
    relevant_total = len(db.get_relevant_packages(conn))
    last_run = db.get_last_completed_run(conn)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Terakhir Cek", last_run["finished_at"][:16].replace("T", " ") if last_run else "Belum pernah")
col2.metric("Wilayah Aktif", len(active_regions))
col3.metric("Paket Relevan (Jalan)", relevant_total)
col4.metric("Paket Baru (Cek Terakhir)", last_run["new_packages_found"] if last_run else 0)

st.divider()

# ---------------------------------------------------------------------------
# Region input + scrape trigger
# ---------------------------------------------------------------------------

st.subheader("Cek Tender")
st.text_input(
    "Region Identifier LPSE (pisahkan dengan koma untuk lebih dari satu wilayah)",
    value="singkawangkota",
    key="region_input",
    help="Contoh: singkawangkota, atau pontianakkota. Ini adalah bagian URL "
    "LPSE, misalnya https://spse.inaproc.id/singkawangkota/lelang",
)

region_ids_preview = region_identifiers_input()
if region_ids_preview:
    st.caption("URL yang akan diperiksa: " + ", ".join(build_lelang_url(r) for r in region_ids_preview))

check_clicked = st.button("\U0001F50D CEK TENDER", type="primary", use_container_width=True)

if check_clicked:
    region_ids = region_identifiers_input()
    if not region_ids:
        st.warning("Masukkan minimal satu Region Identifier terlebih dahulu.")
    else:
        with st.status("Memeriksa LPSE...", expanded=True) as status:
            with db.connect() as conn:
                for rid in region_ids:
                    st.write(f"Memeriksa {rid} ({build_lelang_url(rid)}) ...")
                    db.upsert_region(conn, region_name=rid, region_identifier=rid, base_url=build_lelang_url(rid))

                st.write("Mengambil data dan menyaring paket terkait jalan...")
                summary = run_scrape_and_compare(conn, region_ids)
                st.write("Membandingkan dengan data sebelumnya...")

            status.update(label="PEMERIKSAAN SELESAI", state="complete")

        st.session_state["last_summary"] = {
            "new": summary.new_packages,
            "updated": summary.updated_packages,
            "existing": summary.existing_packages,
            "region_results": [
                {
                    "region_identifier": r.region_identifier,
                    "success": r.success,
                    "error_message": r.error_message,
                    "total_found": r.total_found,
                    "relevant_found": r.relevant_found,
                }
                for r in summary.region_results
            ],
        }
        st.rerun()

# ---------------------------------------------------------------------------
# Results of the most recent check (persisted in session so it survives the
# rerun triggered above, and stays visible until the next check)
# ---------------------------------------------------------------------------

summary = st.session_state.get("last_summary")

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

# ---------------------------------------------------------------------------
# All currently known relevant packages (simple preview of what's stored;
# the full searchable/sortable "Data Tender" page is a later phase)
# ---------------------------------------------------------------------------

st.subheader("Paket Relevan Tersimpan (Semua Wilayah)")
with db.connect() as conn:
    rows = db.get_relevant_packages(conn)

if not rows:
    st.caption("Belum ada data. Klik \"CEK TENDER\" di atas untuk mulai memeriksa.")
else:
    table_data = [
        {
            "Nama Paket": r["nama_paket"],
            "Wilayah": r["region_identifier"],
            "Status": r["tahapan"],
            "HPS": r["hps_text"],
            "Pertama Ditemukan": r["first_seen_at"],
            "Terakhir Diperbarui": r["last_updated_at"],
        }
        for r in rows
    ]
    st.dataframe(table_data, use_container_width=True, hide_index=True)
